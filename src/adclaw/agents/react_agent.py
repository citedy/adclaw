# -*- coding: utf-8 -*-
"""AdClaw Agent - Main agent implementation.

This module provides the main AdClawAgent class built on ReActAgent,
with integrated tools, skills, and memory management.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Literal, Optional, Type

from agentscope.agent import ReActAgent
from agentscope.mcp import HttpStatefulClient, StdIOStatefulClient
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import Toolkit
from anyio import ClosedResourceError
from pydantic import BaseModel

# BaseExceptionGroup is a builtin in 3.11+; on 3.10 we use the
# `exceptiongroup` backport (declared in pyproject.toml only for 3.10).
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup  # noqa: F401

from .command_handler import CommandHandler
from .hooks import BootstrapHook, MemoryCompactionHook
from .model_factory import create_model_and_formatter
from .prompt import (
    CachedPromptBuilder,
    DynamicContext,
    PersonaPromptPool,
)
from .skills_manager import (
    ensure_skills_initialized,
    get_working_skills_dir,
    list_available_skills,
)
from .tools import (
    browser_use,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    send_email,
    write_file,
    create_memory_search_tool,
)
from .tools.aom_query import create_aom_query_tool
from .tools.skill_patcher import patch_skill_script, TOOL_SPEC as _PATCHER_TOOL_SPEC
from .utils import process_file_and_media_blocks_in_message
from ..agents.memory import MemoryManager
from ..config import load_config
from ..constant import (
    MEMORY_COMPACT_KEEP_RECENT,
    MEMORY_COMPACT_RATIO,
    WORKING_DIR,
)

logger = logging.getLogger(__name__)

# Valid namesake strategies for tool registration
NamesakeStrategy = Literal["override", "skip", "raise", "rename"]


def normalize_reasoning_tool_choice(
    tool_choice: Literal["auto", "none", "required"] | None,
    has_tools: bool,
) -> Literal["auto", "none", "required"] | None:
    """Normalize tool_choice for reasoning to reduce provider variance."""
    if tool_choice is None and has_tools:
        return "auto"
    return tool_choice


class AdClawAgent(ReActAgent):
    """AdClaw Agent with integrated tools, skills, and memory management.

    This agent extends ReActAgent with:
    - Built-in tools (shell, file operations, browser, etc.)
    - Dynamic skill loading from working directory
    - Memory management with auto-compaction
    - Bootstrap guidance for first-time setup
    - System command handling (/compact, /new, etc.)
    """

    def __init__(
        self,
        env_context: Optional[str] = None,
        enable_memory_manager: bool = True,
        mcp_clients: Optional[List[Any]] = None,
        memory_manager: MemoryManager | None = None,
        aom_manager: Optional[Any] = None,
        max_iters: int = 50,
        max_input_length: int = 128 * 1024,  # 128K = 131072 tokens
        namesake_strategy: NamesakeStrategy = "skip",
        persona=None,
        team_summary: str = "",
        model=None,
        formatter=None,
        timeout_seconds: Optional[int] = None,
    ):
        """Initialize AdClawAgent.

        Args:
            env_context: Optional environment context to prepend to
                system prompt
            enable_memory_manager: Whether to enable memory manager
            mcp_clients: Optional list of MCP clients for tool
                integration
            memory_manager: Optional memory manager instance
            max_iters: Maximum number of reasoning-acting iterations
                (default: 50)
            max_input_length: Maximum input length in tokens for model
                context window (default: 128K = 131072)
            namesake_strategy: Strategy to handle namesake tool functions.
                Options: "override", "skip", "raise", "rename"
                (default: "skip")
            persona: Optional PersonaConfig with soul_md override
            team_summary: Optional team summary for multi-agent awareness
        """
        self._persona = persona
        self._team_summary = team_summary
        self._heal_events: list = []

        self._prompt_pool = PersonaPromptPool(working_dir=Path(WORKING_DIR))
        self._prompt_builder = self._prompt_pool.get(persona)
        self._env_context = env_context
        self._max_input_length = max_input_length
        self._mcp_clients = mcp_clients or []
        self._namesake_strategy = namesake_strategy
        self._aom_manager = aom_manager
        self._aom_capture_hook = None

        # Memory compaction threshold: configurable ratio of max_input_length
        self._memory_compact_threshold = int(
            max_input_length * MEMORY_COMPACT_RATIO,
        )

        # Initialize toolkit with built-in tools
        toolkit = self._create_toolkit(namesake_strategy=namesake_strategy)

        # Load and register skills
        self._register_skills(toolkit)

        # Build system prompt
        sys_prompt = self._build_sys_prompt()

        # Create model and formatter using factory method (unless injected)
        if (model is None) != (formatter is None):
            raise ValueError(
                "model and formatter must both be provided or both be None",
            )
        if model is None:
            model, formatter = create_model_and_formatter(
                timeout_seconds=timeout_seconds,
            )

        # Initialize parent ReActAgent
        super().__init__(
            name="Friday",
            model=model,
            sys_prompt=sys_prompt,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            formatter=formatter,
            max_iters=max_iters,
        )

        # Setup memory manager
        self._setup_memory_manager(
            enable_memory_manager,
            memory_manager,
            namesake_strategy,
        )

        # Setup AOM integration
        self._setup_aom(namesake_strategy)

        # Setup command handler
        self.command_handler = CommandHandler(
            agent_name=self.name,
            memory=self.memory,
            memory_manager=self.memory_manager,
            enable_memory_manager=self._enable_memory_manager,
        )

        # Register hooks
        self._register_hooks()

    def _create_toolkit(
        self,
        namesake_strategy: NamesakeStrategy = "skip",
    ) -> Toolkit:
        """Create and populate toolkit with built-in tools.

        Args:
            namesake_strategy: Strategy to handle namesake tool functions.
                Options: "override", "skip", "raise", "rename"
                (default: "skip")

        Returns:
            Configured toolkit instance
        """
        toolkit = Toolkit()

        # Register built-in tools
        toolkit.register_tool_function(
            execute_shell_command,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            read_file,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            write_file,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            edit_file,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            browser_use,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            desktop_screenshot,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            send_file_to_user,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            send_email,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            get_current_time,
            namesake_strategy=namesake_strategy,
        )
        toolkit.register_tool_function(
            patch_skill_script,
            namesake_strategy=namesake_strategy,
        )

        return toolkit

    def _register_skills(self, toolkit: Toolkit) -> None:
        """Load and register skills from working directory.

        Args:
            toolkit: Toolkit to register skills to
        """
        # Check skills initialization
        ensure_skills_initialized()

        working_skills_dir = get_working_skills_dir()
        available_skills = list_available_skills()

        self._broken_skills = []
        for skill_name in available_skills:
            skill_dir = working_skills_dir / skill_name
            if skill_dir.exists():
                try:
                    toolkit.register_agent_skill(str(skill_dir))
                    logger.debug("Registered skill: %s", skill_name)
                except Exception as e:
                    logger.error(
                        "Failed to register skill '%s': %s",
                        skill_name,
                        e,
                    )
                    self._broken_skills.append(
                        (skill_name, skill_dir, str(e))
                    )

    def _build_sys_prompt(self) -> str:
        """Build system prompt using CachedPromptBuilder (v2).

        Static sections (AGENTS.md, SOUL.md, PROFILE.md) are cached via hash.
        Dynamic sections (env context, team summary) are rebuilt per-call.

        Returns:
            Complete system prompt string
        """
        dynamic = DynamicContext(
            env_context=self._env_context or "",
            team_summary=self._team_summary or "",
        )
        return self._prompt_builder.build(dynamic=dynamic)

    def _setup_memory_manager(
        self,
        enable_memory_manager: bool,
        memory_manager: MemoryManager | None,
        namesake_strategy: NamesakeStrategy,
    ) -> None:
        """Setup memory manager and register memory search tool if enabled.

        Args:
            enable_memory_manager: Whether to enable memory manager
            memory_manager: Optional memory manager instance
            namesake_strategy: Strategy to handle namesake tool functions
        """
        # Check env var: if ENABLE_MEMORY_MANAGER=false, disable memory manager
        env_enable_mm = os.getenv("ENABLE_MEMORY_MANAGER", "")
        if env_enable_mm.lower() == "false":
            enable_memory_manager = False

        self._enable_memory_manager: bool = enable_memory_manager
        self.memory_manager = memory_manager

        # Register memory_search tool if enabled and available
        if self._enable_memory_manager and self.memory_manager is not None:
            # update memory manager
            self.memory_manager.chat_model = self.model
            self.memory_manager.formatter = self.formatter
            memory_toolkit = Toolkit()
            memory_toolkit.register_tool_function(
                read_file,
                namesake_strategy=self._namesake_strategy,
            )
            memory_toolkit.register_tool_function(
                write_file,
                namesake_strategy=self._namesake_strategy,
            )
            memory_toolkit.register_tool_function(
                edit_file,
                namesake_strategy=self._namesake_strategy,
            )
            self.memory_manager.toolkit = memory_toolkit
            self.memory_manager.update_config_params()

            self.memory = self.memory_manager.get_in_memory_memory()

            # Register memory_search as a tool function
            self.toolkit.register_tool_function(
                create_memory_search_tool(self.memory_manager),
                namesake_strategy=namesake_strategy,
            )
            logger.debug("Registered memory_search tool")

    def _setup_aom(self, namesake_strategy: NamesakeStrategy) -> None:
        """Setup Always-On Memory integration if AOM manager is available."""
        if self._aom_manager is None or not self._aom_manager.is_running:
            return

        # Register query_long_term_memory tool
        if self._aom_manager.query_agent is not None:
            try:
                tool_fn = create_aom_query_tool(self._aom_manager.query_agent)
                self.toolkit.register_tool_function(
                    tool_fn,
                    namesake_strategy=namesake_strategy,
                )
                logger.debug("Registered query_long_term_memory tool")
            except Exception as exc:
                logger.warning("Failed to register AOM query tool: %s", exc)

        # Setup capture hook for auto-ingesting tool results
        if self._aom_manager.ingest_agent is not None:
            try:
                from .hooks.aom_capture import AOMCaptureHook

                config = load_config()
                aom_config = config.agents.always_on_memory
                self._aom_capture_hook = AOMCaptureHook(
                    ingest_agent=self._aom_manager.ingest_agent,
                    capture_mcp=aom_config.auto_capture_mcp,
                    capture_skills=aom_config.auto_capture_skills,
                )
                logger.debug("AOM capture hook configured")
            except Exception as exc:
                logger.warning("Failed to setup AOM capture hook: %s", exc)

    def _register_hooks(self) -> None:
        """Register pre-reasoning hooks for bootstrap and memory compaction."""
        # Bootstrap hook - checks BOOTSTRAP.md on first interaction
        config = load_config()
        bootstrap_hook = BootstrapHook(
            working_dir=WORKING_DIR,
            language=config.agents.language,
        )
        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="bootstrap_hook",
            hook=bootstrap_hook.__call__,
        )
        logger.debug("Registered bootstrap hook")

        # Memory compaction hook - auto-compact when context is full
        if self._enable_memory_manager and self.memory_manager is not None:
            memory_compact_hook = MemoryCompactionHook(
                memory_manager=self.memory_manager,
                memory_compact_threshold=self._memory_compact_threshold,
                keep_recent=MEMORY_COMPACT_KEEP_RECENT,
            )
            self.register_instance_hook(
                hook_type="pre_reasoning",
                hook_name="memory_compact_hook",
                hook=memory_compact_hook.__call__,
            )
            logger.debug("Registered memory compaction hook")

    def rebuild_sys_prompt(self) -> None:
        """Rebuild the system prompt using CachedPromptBuilder.

        Static sections (AGENTS.md, SOUL.md, PROFILE.md) are cached --
        only re-read when file content hash changes.
        Dynamic sections (env context, team summary) are rebuilt every call.
        """
        self._sys_prompt = self._build_sys_prompt()
        logger.debug(
            "Prompt rebuilt (len=%d)",
            len(self._sys_prompt),
        )

        for msg, _marks in self.memory.content:
            if msg.role == "system":
                msg.content = self.sys_prompt
            break

    async def register_mcp_clients(
        self,
        namesake_strategy: NamesakeStrategy = "skip",
    ) -> None:
        """Register MCP clients on this agent's toolkit after construction.

        Args:
            namesake_strategy: Strategy to handle namesake tool functions.
                Options: "override", "skip", "raise", "rename"
                (default: "skip")
        """
        for i, client in enumerate(self._mcp_clients):
            client_name = getattr(client, "name", repr(client))
            try:
                await self.toolkit.register_mcp_client(
                    client,
                    namesake_strategy=namesake_strategy,
                )
            except (ClosedResourceError, asyncio.CancelledError) as error:
                if self._should_propagate_cancelled_error(error):
                    raise
                logger.warning(
                    "MCP client '%s' session interrupted while listing tools; "
                    "trying recovery",
                    client_name,
                )
                recovered_client = await self._recover_mcp_client(client)
                if recovered_client is not None:
                    self._mcp_clients[i] = recovered_client
                    try:
                        await self.toolkit.register_mcp_client(
                            recovered_client,
                            namesake_strategy=namesake_strategy,
                        )
                        continue
                    except asyncio.CancelledError as recover_error:
                        if self._should_propagate_cancelled_error(
                            recover_error,
                        ):
                            raise
                        logger.warning(
                            "MCP client '%s' registration cancelled after "
                            "recovery, skipping",
                            client_name,
                        )
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning(
                            "MCP client '%s' still unavailable after "
                            "recovery, skipping: %s",
                            client_name,
                            e,
                        )
                else:
                    logger.warning(
                        "MCP client '%s' recovery failed, skipping",
                        client_name,
                    )
            except BaseExceptionGroup as eg:
                # anyio TaskGroup teardown (e.g. MCP HTTP 401) raises
                # BaseExceptionGroup which is NOT a subclass of Exception
                # in Python 3.11+ — handle explicitly so one broken client
                # never crashes the whole agent. ExceptionGroup is a
                # subclass of BaseExceptionGroup so this catches both.
                logger.warning(
                    "MCP client '%s' unavailable (TaskGroup error), "
                    "skipping (agent will run without its tools): %s",
                    client_name,
                    eg,
                    exc_info=True,
                )
                continue
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "MCP client '%s' unavailable, skipping "
                    "(agent will run without its tools): %s",
                    client_name,
                    e,
                    exc_info=True,
                )
                continue

        # Auto-heal broken skills (async context available here)
        if getattr(self, "_broken_skills", None):
            await self._heal_broken_skills()

    async def _heal_broken_skills(self) -> None:
        """Attempt to auto-heal broken skills using LLM."""
        from .skill_healer import heal_skill

        async def llm_caller(prompt: str) -> str:
            model, _ = create_model_and_formatter()
            r = await model([{"role": "user", "content": prompt}])
            if hasattr(r, "__aiter__"):
                last_text = ""
                async for chunk in r:
                    c = getattr(chunk, "content", None)
                    if isinstance(c, list):
                        for b in c:
                            if isinstance(b, dict) \
                                    and b.get("type") == "text":
                                last_text = b.get("text", "")
                    elif isinstance(c, str):
                        last_text = c
                return last_text
            c = getattr(r, "content", str(r))
            if isinstance(c, list):
                return "".join(
                    b.get("text", "") if isinstance(b, dict)
                    else str(b) for b in c
                )
            return str(c)

        for skill_name, skill_dir, error_msg in self._broken_skills:
            try:
                result = await heal_skill(skill_dir, error_msg, llm_caller)
                if result.healed:
                    try:
                        self.toolkit.register_agent_skill(str(skill_dir))
                        self._heal_events.append({
                            "skill": skill_name,
                            "error": error_msg[:100],
                        })
                        logger.info(
                            "Self-healed skill '%s': %s",
                            skill_name, result.message,
                        )
                    except Exception as retry_err:
                        logger.error(
                            "Skill '%s' still broken after heal: %s",
                            skill_name, retry_err,
                        )
                else:
                    logger.warning(
                        "Could not heal skill '%s': %s",
                        skill_name, result.message,
                    )
            except Exception as heal_err:
                logger.warning(
                    "Self-heal failed for '%s': %s",
                    skill_name, heal_err,
                )

    async def _recover_mcp_client(self, client: Any) -> Any | None:
        """Recover MCP client from broken session and return healthy client."""
        if await self._reconnect_mcp_client(client):
            return client

        rebuilt_client = self._rebuild_mcp_client(client)
        if rebuilt_client is None:
            return None

        if await self._reconnect_mcp_client(rebuilt_client):
            return self._reuse_shared_client_reference(
                original_client=client,
                rebuilt_client=rebuilt_client,
            )

        return None

    @staticmethod
    def _reuse_shared_client_reference(
        original_client: Any,
        rebuilt_client: Any,
    ) -> Any:
        """Keep manager-shared client reference stable after rebuild."""
        original_dict = getattr(original_client, "__dict__", None)
        rebuilt_dict = getattr(rebuilt_client, "__dict__", None)
        if isinstance(original_dict, dict) and isinstance(rebuilt_dict, dict):
            original_dict.update(rebuilt_dict)
            return original_client
        return rebuilt_client

    @staticmethod
    def _should_propagate_cancelled_error(error: BaseException) -> bool:
        """Only swallow MCP-internal cancellations, not task cancellation."""
        if not isinstance(error, asyncio.CancelledError):
            return False

        task = asyncio.current_task()
        if task is None:
            return False

        cancelling = getattr(task, "cancelling", None)
        if callable(cancelling):
            return cancelling() > 0

        # Python < 3.11: Task.cancelling() is unavailable.
        # Fall back to propagating CancelledError to avoid swallowing
        # genuine task cancellations when we cannot inspect the state.
        return True

    @staticmethod
    async def _reconnect_mcp_client(
        client: Any,
        timeout: float = 60.0,
    ) -> bool:
        """Best-effort reconnect for stateful MCP clients."""
        close_fn = getattr(client, "close", None)
        if callable(close_fn):
            try:
                await close_fn()
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise
            except Exception:  # pylint: disable=broad-except
                pass

        connect_fn = getattr(client, "connect", None)
        if not callable(connect_fn):
            return False

        try:
            await asyncio.wait_for(connect_fn(), timeout=timeout)
            return True
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except asyncio.TimeoutError:
            return False
        except Exception:  # pylint: disable=broad-except
            return False

    @staticmethod
    def _rebuild_mcp_client(client: Any) -> Any | None:
        """Rebuild a fresh MCP client instance from stored config metadata."""
        rebuild_info = getattr(client, "_adclaw_rebuild_info", None)
        if not isinstance(rebuild_info, dict):
            return None

        transport = rebuild_info.get("transport")
        name = rebuild_info.get("name")

        try:
            if transport == "stdio":
                rebuilt_client = StdIOStatefulClient(
                    name=name,
                    command=rebuild_info.get("command"),
                    args=rebuild_info.get("args", []),
                    env=rebuild_info.get("env", {}),
                    cwd=rebuild_info.get("cwd"),
                )
                setattr(rebuilt_client, "_adclaw_rebuild_info", rebuild_info)
                return rebuilt_client

            rebuilt_client = HttpStatefulClient(
                name=name,
                transport=transport,
                url=rebuild_info.get("url"),
                headers=rebuild_info.get("headers"),
            )
            setattr(rebuilt_client, "_adclaw_rebuild_info", rebuild_info)
            return rebuilt_client
        except Exception:  # pylint: disable=broad-except
            return None

    async def _reasoning(
        self,
        tool_choice: Literal["auto", "none", "required"] | None = None,
    ) -> Msg:
        """Ensure a stable default tool-choice behavior across providers."""
        tool_choice = normalize_reasoning_tool_choice(
            tool_choice=tool_choice,
            has_tools=bool(self.toolkit.get_json_schemas()),
        )

        return await super()._reasoning(tool_choice=tool_choice)

    async def reply(
        self,
        msg: Msg | list[Msg] | None = None,
        structured_model: Type[BaseModel] | None = None,
    ) -> Msg:
        """Override reply to process file blocks and handle commands.

        Args:
            msg: Input message(s) from user
            structured_model: Optional pydantic model for structured output

        Returns:
            Response message
        """
        # Process file and media blocks in messages
        if msg is not None:
            await process_file_and_media_blocks_in_message(msg)

        # Check if message is a system command
        last_msg = msg[-1] if isinstance(msg, list) else msg
        query = (
            last_msg.get_text_content() if isinstance(last_msg, Msg) else None
        )

        if self.command_handler.is_command(query):
            logger.info(f"Received command: {query}")
            msg = await self.command_handler.handle_command(query)
            await self.print(msg)
            return msg

        # Normal message processing
        return await super().reply(msg=msg, structured_model=structured_model)
