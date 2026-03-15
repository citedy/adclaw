# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
from pathlib import Path

from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from dotenv import load_dotenv

from .query_error_dump import write_query_error_dump
from .session import SafeJSONSession
from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.memory import MemoryManager
from ...agents.model_factory import create_model_and_formatter
from ...agents.persona_manager import PersonaManager
from ...agents.react_agent import AdClawAgent
from ...agents.tools import read_file, write_file, edit_file
from ...agents.utils.token_counting import _get_token_counter
from ...config import load_config
from ...constant import (
    MEMORY_COMPACT_RATIO,
    WORKING_DIR,
)

logger = logging.getLogger(__name__)


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._mcp_manager = None  # MCP client manager for hot-reload
        self._aom_manager = None  # Always-On Memory manager

        self.memory_manager: MemoryManager | None = None
        self._session_persona_map: dict[str, str] = {}  # sticky persona routing

    def set_chat_manager(self, chat_manager):
        """Set chat manager for auto-registration.

        Args:
            chat_manager: ChatManager instance
        """
        self._chat_manager = chat_manager

    def set_mcp_manager(self, mcp_manager):
        """Set MCP client manager for hot-reload support.

        Args:
            mcp_manager: MCPClientManager instance
        """
        self._mcp_manager = mcp_manager

    def set_aom_manager(self, aom_manager):
        """Set AOM manager for long-term memory support.

        Args:
            aom_manager: AOMManager instance
        """
        self._aom_manager = aom_manager

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """
        Handle agent query.
        """

        agent = None
        chat = None
        session_state_loaded = False

        try:
            session_id = request.session_id
            user_id = request.user_id
            channel = getattr(request, "channel", DEFAULT_CHANNEL)

            logger.info(
                "Handle agent query:\n%s",
                json.dumps(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "channel": channel,
                        "msgs_len": len(msgs) if msgs else 0,
                        "msgs_str": str(msgs)[:300] + "...",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            env_context = build_env_context(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )

            # Get MCP clients from manager (hot-reloadable)
            mcp_clients = []
            if self._mcp_manager is not None:
                mcp_clients = await self._mcp_manager.get_clients()

            config = load_config()
            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length

            # --- Persona routing ---
            persona_mgr = PersonaManager(
                working_dir=str(WORKING_DIR),
                personas=getattr(config.agents, "personas", []),
            )
            persona_mgr.ensure_dirs()

            # Resolve persona from first message text
            msg_text = ""
            if msgs and len(msgs) > 0:
                msg_text = msgs[0].get_text_content() or ""

            persona_id = persona_mgr.resolve_tag(msg_text)
            persona = None

            if persona_id:
                persona = persona_mgr.get_persona(persona_id)
                # Strip @tag from message text
                if msgs and len(msgs) > 0:
                    original_text = msgs[0].get_text_content() or ""
                    stripped = persona_mgr.strip_tag(original_text)
                    msgs[0].content = stripped
            elif request.session_id in self._session_persona_map:
                # Sticky routing: reuse last persona for this session
                persona = persona_mgr.get_persona(self._session_persona_map[request.session_id])
            elif persona_mgr.get_coordinator():
                persona = persona_mgr.get_coordinator()
            # else: no personas configured, use default behavior

            # Scope session_id per persona
            if persona:
                self._session_persona_map[request.session_id] = persona.id
                session_id = f"{persona.id}::{session_id}"

            agent = AdClawAgent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                memory_manager=self.memory_manager,
                aom_manager=self._aom_manager,
                max_iters=max_iters,
                max_input_length=max_input_length,
                persona=persona,
                team_summary=persona_mgr.get_team_summary() if persona_mgr.all_personas else "",
            )
            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)

            logger.debug(
                f"Agent Query msgs {msgs}",
            )

            name = "New Chat"
            if len(msgs) > 0:
                content = msgs[0].get_text_content()
                if content:
                    name = msgs[0].get_text_content()[:10]
                else:
                    name = "Media Message"

            if self._chat_manager is not None:
                chat = await self._chat_manager.get_or_create_chat(
                    session_id,
                    user_id,
                    channel,
                    name=name,
                )

            await self.session.load_session_state(
                session_id=session_id,
                user_id=user_id,
                agent=agent,
            )
            session_state_loaded = True

            # Rebuild system prompt so it always reflects the latest
            # AGENTS.md / SOUL.md / PROFILE.md, not the stale one saved
            # in the session state.
            agent.rebuild_sys_prompt()

            try:
                async for msg, last in stream_printing_messages(
                    agents=[agent],
                    coroutine_task=agent(msgs),
                ):
                    yield msg, last
            except Exception as first_err:
                # Only retry on specific LLM rejection errors (BadRequestError
                # from openai SDK), not on arbitrary 400s or other exceptions.
                from openai import BadRequestError as _OAIBadRequest

                if not isinstance(first_err, _OAIBadRequest):
                    raise

                err_str = str(first_err).lower()
                if "invalid_parameter" not in err_str:
                    raise

                logger.warning(
                    "LLM rejected request (likely stale session), "
                    "clearing history and retrying: %s",
                    first_err,
                )
                # Clear the agent's conversation memory
                if hasattr(agent, "memory") and hasattr(
                    agent.memory, "clear"
                ):
                    agent.memory.clear()
                elif hasattr(agent, "memory") and hasattr(
                    agent.memory, "content"
                ):
                    agent.memory.content.clear()

                # Notify user that session was reset
                from agentscope.message import Msg
                reset_msg = Msg(
                    name="system",
                    role="assistant",
                    content="⚠️ Session history was cleared due to a provider error. Continuing with fresh context.",
                )
                yield reset_msg, False

                # Retry with clean context
                async for msg, last in stream_printing_messages(
                    agents=[agent],
                    coroutine_task=agent(msgs),
                ):
                    yield msg, last

        except asyncio.CancelledError:
            if agent is not None:
                await agent.interrupt()
            raise
        except Exception as e:
            debug_dump_path = write_query_error_dump(
                request=request,
                exc=e,
                locals_=locals(),
            )
            path_hint = (
                f"\n(Details:  {debug_dump_path})" if debug_dump_path else ""
            )
            logger.exception(f"Error in query handler: {e}{path_hint}")
            if debug_dump_path:
                setattr(e, "debug_dump_path", debug_dump_path)
                if hasattr(e, "add_note"):
                    e.add_note(
                        f"(Details:  {debug_dump_path})",
                    )
                suffix = f"\n(Details:  {debug_dump_path})"
                e.args = (
                    (f"{e.args[0]}{suffix}" if e.args else suffix.strip()),
                ) + e.args[1:]
            raise
        finally:
            if agent is not None and session_state_loaded:
                await self.session.save_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )

            if self._chat_manager is not None and chat is not None:
                await self._chat_manager.update_chat(chat)

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        # Load environment variables from .env file
        env_path = Path(__file__).resolve().parents[4] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded environment variables from {env_path}")
        else:
            logger.debug(
                f".env file not found at {env_path}, "
                "using existing environment variables",
            )

        session_dir = str(WORKING_DIR / "sessions")
        self.session = SafeJSONSession(save_dir=session_dir)

        try:
            if self.memory_manager is None:
                # Get config for memory manager
                config = load_config()
                max_input_length = config.agents.running.max_input_length

                # Create model and formatter
                chat_model, formatter = create_model_and_formatter()

                # Get token counter
                token_counter = _get_token_counter()

                # Create toolkit for memory manager
                toolkit = Toolkit()
                toolkit.register_tool_function(read_file)
                toolkit.register_tool_function(write_file)
                toolkit.register_tool_function(edit_file)

                # Initialize MemoryManager with new parameters
                self.memory_manager = MemoryManager(
                    working_dir=str(WORKING_DIR),
                    chat_model=chat_model,
                    formatter=formatter,
                    token_counter=token_counter,
                    toolkit=toolkit,
                    max_input_length=max_input_length,
                    memory_compact_ratio=MEMORY_COMPACT_RATIO,
                )
            await self.memory_manager.start()
        except Exception as e:
            logger.exception(f"MemoryManager start failed: {e}")

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        try:
            await self.memory_manager.close()
        except Exception as e:
            logger.warning(f"MemoryManager stop failed: {e}")
