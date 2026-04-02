# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
import traceback
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

# Error types that indicate corrupt session state rather than infra failure.
_SESSION_STATE_ERROR_TYPES = (
    ValueError, KeyError, FileNotFoundError, TypeError, AttributeError,
)

# Traceback markers that confirm the error came from session/formatter path.
_SESSION_STATE_TB_MARKERS = (
    "formatter", "memory_compaction", "state_dict",
    "_strip_missing", "_format", "load_state", "TemporaryMemory",
    "_openai_formatter", "_to_openai_image_url",
)


def _clear_agent_memory(agent) -> None:
    """Clear agent memory using whichever API is available."""
    if hasattr(agent, "memory") and hasattr(agent.memory, "clear"):
        agent.memory.clear()
    elif hasattr(agent, "memory") and hasattr(agent.memory, "content"):
        agent.memory.content.clear()


def _is_session_state_error(exc: Exception) -> bool:
    """Return True if the exception is likely caused by corrupt session state.

    These errors can be fixed by clearing the agent's memory and retrying
    with a fresh context window.
    """
    if not isinstance(exc, _SESSION_STATE_ERROR_TYPES):
        return False
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return any(marker in tb_text for marker in _SESSION_STATE_TB_MARKERS)


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._mcp_manager = None  # MCP client manager for hot-reload
        self._aom_manager = None  # Always-On Memory manager

        self.memory_manager: MemoryManager | None = None
        self.error_tracker = None  # Set by _app.py after init
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

            # Check if this session is in a crash loop (after persona scoping
            # so the session_id matches what record_failure/success use).
            if self.error_tracker and self.error_tracker.is_tripped(session_id):
                from agentscope.message import Msg
                trip_msg = Msg(
                    name="system",
                    role="assistant",
                    content=(
                        "This conversation hit repeated errors. "
                        "Send /new to start a fresh session, "
                        "or wait 2 minutes for auto-retry."
                    ),
                )
                yield trip_msg, True
                return

            # Resolve timeout from fallback config
            from ...providers.store import get_fallback_config
            fallback_cfg = get_fallback_config()
            _timeout = (
                fallback_cfg.timeout_seconds
                if fallback_cfg.enabled
                else None
            )

            agent = AdClawAgent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                memory_manager=self.memory_manager,
                aom_manager=self._aom_manager,
                max_iters=max_iters,
                max_input_length=max_input_length,
                persona=persona,
                team_summary=persona_mgr.get_team_summary() if persona_mgr.all_personas else "",
                timeout_seconds=_timeout,
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
                from openai import (
                    APIConnectionError as _OAIConnErr,
                    APITimeoutError as _OAITimeout,
                    AuthenticationError as _OAIAuthErr,
                    BadRequestError as _OAIBadRequest,
                    RateLimitError as _OAIRateLimit,
                )

                # --- Retry on stale-session BadRequestError ---
                if isinstance(first_err, _OAIBadRequest):
                    err_str = str(first_err).lower()
                    if "invalid_parameter" in err_str:
                        logger.warning(
                            "LLM rejected request (likely stale session), "
                            "clearing history and retrying: %s",
                            first_err,
                        )
                        _clear_agent_memory(agent)

                        from agentscope.message import Msg
                        reset_msg = Msg(
                            name="system",
                            role="assistant",
                            content="⚠️ Session history was cleared due to a provider error. Continuing with fresh context.",
                        )
                        yield reset_msg, False

                        async for msg, last in stream_printing_messages(
                            agents=[agent],
                            coroutine_task=agent(msgs),
                        ):
                            yield msg, last
                        return  # done, no fallback needed

                # --- Fallback chain logic ---
                _fallback_errors = (
                    _OAITimeout, _OAIRateLimit, _OAIAuthErr, _OAIConnErr,
                )
                if not isinstance(first_err, _fallback_errors):
                    raise

                from ...providers.store import (
                    get_fallback_config,
                    resolve_fallback_chain,
                )
                fallback_cfg = get_fallback_config()
                if not fallback_cfg.enabled:
                    raise

                resolved_chain = resolve_fallback_chain()
                if not resolved_chain:
                    raise

                primary_model = (
                    agent.model.model_name
                    if hasattr(agent, "model")
                    and hasattr(agent.model, "model_name")
                    else "primary model"
                )
                err_type = type(first_err).__name__
                logger.warning(
                    "Primary LLM (%s) failed with %s, "
                    "trying fallback chain (%d candidates)",
                    primary_model, err_type, len(resolved_chain),
                )

                from agentscope.message import Msg

                for fb_cfg in resolved_chain:
                    try:
                        fb_model, fb_formatter = create_model_and_formatter(
                            fb_cfg,
                            timeout_seconds=fallback_cfg.timeout_seconds,
                        )

                        notify_msg = Msg(
                            name="system",
                            role="assistant",
                            content=(
                                f"⚠️ {primary_model} unavailable ({err_type}). "
                                f"Switching to {fb_cfg.model}..."
                            ),
                        )
                        yield notify_msg, False

                        # Fallback agent is created without loading session
                        # state. This is intentional: loading the same history
                        # that may have caused the primary failure could trigger
                        # the same error on the fallback provider.
                        fb_agent = AdClawAgent(
                            env_context=getattr(agent, "_env_context", None),
                            mcp_clients=getattr(agent, "_mcp_clients", []),
                            memory_manager=self.memory_manager,
                            aom_manager=self._aom_manager,
                            max_iters=max_iters,
                            max_input_length=max_input_length,
                            namesake_strategy=getattr(agent, "_namesake_strategy", "skip"),
                            persona=getattr(agent, "_persona", None),
                            team_summary=getattr(agent, "_team_summary", ""),
                            model=fb_model,
                            formatter=fb_formatter,
                        )
                        await fb_agent.register_mcp_clients()
                        fb_agent.set_console_output_enabled(enabled=False)

                        async for msg, last in stream_printing_messages(
                            agents=[fb_agent],
                            coroutine_task=fb_agent(msgs),
                        ):
                            yield msg, last
                        return  # success
                    except (
                        _OAITimeout, _OAIRateLimit, _OAIAuthErr, _OAIConnErr,
                    ) as fb_err:
                        logger.warning(
                            "Fallback model %s failed with LLM error: %s",
                            fb_cfg.model, fb_err,
                        )
                        continue
                    except Exception as fb_err:
                        logger.error(
                            "Fallback model %s failed with unexpected error: %s",
                            fb_cfg.model, fb_err,
                            exc_info=True,
                        )
                        continue

                # All fallbacks exhausted — notify user and re-raise
                exhausted_msg = Msg(
                    name="system",
                    role="assistant",
                    content=(
                        f"All {len(resolved_chain)} fallback model(s) "
                        "also failed. Please check your provider configurations."
                    ),
                )
                yield exhausted_msg, False
                raise first_err

            # If we reach here without exception, processing succeeded
            if self.error_tracker:
                self.error_tracker.record_success(session_id)

        except asyncio.CancelledError:
            if agent is not None:
                await agent.interrupt()
            raise
        except Exception as e:
            # --- Auto-recovery: retry with clean session for state errors ---
            if (
                session_state_loaded
                and agent is not None
                and _is_session_state_error(e)
            ):
                logger.warning(
                    "Session state caused crash, clearing memory and retrying: %s",
                    e,
                )
                try:
                    _clear_agent_memory(agent)

                    from agentscope.message import Msg
                    heal_msg = Msg(
                        name="system",
                        role="assistant",
                        content=(
                            "Session history was corrupted and has been "
                            "reset. Continuing with fresh context."
                        ),
                    )
                    yield heal_msg, False

                    async for msg, last in stream_printing_messages(
                        agents=[agent],
                        coroutine_task=agent(msgs),
                    ):
                        yield msg, last
                    if self.error_tracker:
                        self.error_tracker.record_success(session_id)
                    return
                except Exception as retry_err:
                    logger.exception(
                        "Retry after session reset also failed: %s",
                        retry_err,
                    )
                    # Fall through to normal error handling

            if self.error_tracker:
                self.error_tracker.record_failure(session_id)

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
