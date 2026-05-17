# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from agentscope.pipeline import stream_printing_messages
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from dotenv import load_dotenv

from .query_error_dump import write_query_error_dump
from .session import SafeJSONSession
from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.persona_manager import PersonaManager
from ...agents.react_agent import AdClawAgent
from ...config import load_config
from ...constant import (
    MEMORY_COMPACT_RATIO,
    WORKING_DIR,
)
from ...memory_agent.shared_persona import (
    build_shared_persona_memory_context,
    capture_chat_memory,
    extract_visible_text,
)

if TYPE_CHECKING:
    from ...agents.memory import MemoryManager

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

_TRUTHY_ENV_VALUES = ("1", "true", "yes", "on")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in _TRUTHY_ENV_VALUES


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in _TRUTHY_ENV_VALUES


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, value, default)
        return default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %.2f", name, value, default)
        return default


class _MemoryManagerBootMetrics:
    """Small wall/CPU timer for ReMe startup logs."""

    def __init__(self) -> None:
        self._wall = time.perf_counter()
        self._cpu = time.process_time()

    def mark(self, phase: str) -> None:
        wall_now = time.perf_counter()
        cpu_now = time.process_time()
        logger.info(
            "MemoryManager boot phase=%s wall=%.3fs cpu=%.3fs",
            phase,
            wall_now - self._wall,
            cpu_now - self._cpu,
        )
        self._wall = wall_now
        self._cpu = cpu_now


class _ApproxTokenCounter:
    """Cheap fallback counter for ReMe startup on small VPS instances."""

    async def count(self, messages, tools=None, **kwargs) -> int:
        del kwargs
        text = json.dumps(messages, ensure_ascii=False, default=str)
        if tools:
            text = f"{text}\n{json.dumps(tools, ensure_ascii=False, default=str)}"
        return max(1, len(text) // 4)


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

        self.memory_manager: "MemoryManager | None" = None
        self._memory_manager_start_task: asyncio.Task | None = None
        self.memory_manager_status = "not_started"
        self.memory_manager_status_detail: str | None = None
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

    def _set_memory_manager_status(self, state: str, detail: str | None = None) -> None:
        self.memory_manager_status = state
        self.memory_manager_status_detail = detail

    async def _build_shared_persona_memory_context(
        self,
        *,
        base_session_id: str,
        user_id: str,
        current_persona_id: str,
    ) -> str:
        """Build prompt context from persistent chat memories across personas."""
        return await build_shared_persona_memory_context(
            self._aom_manager,
            base_session_id=base_session_id,
            user_id=user_id,
            current_persona_id=current_persona_id,
        )

    async def _capture_chat_memory(
        self,
        *,
        base_session_id: str,
        scoped_session_id: str,
        user_id: str,
        channel: str,
        persona_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Persist a completed chat turn into shared AOM."""
        await capture_chat_memory(
            self._aom_manager,
            base_session_id=base_session_id,
            scoped_session_id=scoped_session_id,
            user_id=user_id,
            channel=channel,
            persona_id=persona_id,
            user_text=user_text,
            assistant_text=assistant_text,
        )

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
        assistant_text = ""
        user_text = ""
        base_session_id = ""
        persona_id_for_memory = "default"

        try:
            session_id = request.session_id
            base_session_id = request.session_id
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
                user_text = msg_text

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
                persona_id_for_memory = persona.id
                session_id = f"{persona.id}::{session_id}"

            shared_memory_context = await self._build_shared_persona_memory_context(
                base_session_id=base_session_id,
                user_id=user_id,
                current_persona_id=persona_id_for_memory,
            )
            env_context = build_env_context(
                session_id=base_session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )
            if shared_memory_context:
                env_context = f"{env_context}\n\n{shared_memory_context}"

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
                    text = extract_visible_text(msg)
                    if getattr(msg, "role", None) == "assistant" and text:
                        assistant_text = text
                    yield msg, last
            except Exception as first_err:
                from openai import (
                    APIConnectionError as _OAIConnErr,
                    APIError as _OAIAPIError,
                    APITimeoutError as _OAITimeout,
                    AuthenticationError as _OAIAuthErr,
                    BadRequestError as _OAIBadRequest,
                    RateLimitError as _OAIRateLimit,
                    UnprocessableEntityError as _OAIUnprocessable,
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

                        try:
                            async for msg, last in stream_printing_messages(
                                agents=[agent],
                                coroutine_task=agent(msgs),
                            ):
                                text = extract_visible_text(msg)
                                if getattr(msg, "role", None) == "assistant" and text:
                                    assistant_text = text
                                yield msg, last
                            if self.error_tracker:
                                self.error_tracker.record_success(session_id)
                            return  # done, no fallback needed
                        except _OAIAPIError as retry_err:
                            logger.warning(
                                "Stale-session retry also failed: %s, "
                                "falling through to fallback chain",
                                retry_err,
                            )
                            first_err = retry_err
                            # Fall through to fallback logic below

                # --- Fallback chain logic ---
                # Fallback on any OpenAI API error (500, 429, timeout,
                # auth, connection) EXCEPT BadRequest (broken request,
                # not provider issue). Non-API errors (TypeError,
                # KeyError etc.) propagate immediately — they indicate
                # code bugs, not provider failures.
                if not isinstance(first_err, _OAIAPIError):
                    raise first_err  # not a provider error — propagate
                if isinstance(first_err, (_OAIBadRequest, _OAIUnprocessable)):
                    raise first_err  # request itself is broken

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
                            text = extract_visible_text(msg)
                            if getattr(msg, "role", None) == "assistant" and text:
                                assistant_text = text
                            yield msg, last
                        if self.error_tracker:
                            self.error_tracker.record_success(session_id)
                        return  # success
                    except (_OAIBadRequest, _OAIUnprocessable) as fb_err:
                        # Request is broken — no point trying more providers
                        logger.warning(
                            "Fallback model %s: request error: %s",
                            fb_cfg.model, fb_err,
                        )
                        raise
                    except _OAIAPIError as fb_err:
                        logger.warning(
                            "Fallback model %s failed with API error: %s",
                            fb_cfg.model, fb_err,
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
                        text = extract_visible_text(msg)
                        if getattr(msg, "role", None) == "assistant" and text:
                            assistant_text = text
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

            if self.error_tracker and session_state_loaded:
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
                await self._capture_chat_memory(
                    base_session_id=base_session_id,
                    scoped_session_id=session_id,
                    user_id=user_id,
                    channel=channel,
                    persona_id=persona_id_for_memory,
                    user_text=user_text,
                    assistant_text=assistant_text,
                )

            if self._chat_manager is not None and chat is not None:
                await self._chat_manager.update_chat(chat)

    def _apply_memory_manager_safe_defaults(self) -> None:
        """Keep ReMe startup on the cheapest local path unless configured."""
        os.environ.setdefault("MEMORY_STORE_BACKEND", "sqlite")
        os.environ.setdefault("FTS_ENABLED", "true")

        # ReMe's vector mode uses an OpenAI-compatible embedding API. Without
        # both values it falls back to file/FTS memory, avoiding background
        # ChromaDB and network embedding work on small VPS instances.
        has_embedding_api = bool(os.environ.get("EMBEDDING_API_KEY"))
        has_embedding_model = bool(os.environ.get("EMBEDDING_MODEL_NAME"))
        if not (has_embedding_api and has_embedding_model):
            os.environ.setdefault("EMBEDDING_API_KEY", "")
            os.environ.setdefault("EMBEDDING_MODEL_NAME", "")

    def _memory_manager_load_too_high(self) -> bool:
        max_load = _env_float("ADCLAW_MEMORY_MANAGER_MAX_LOADAVG", 0.0)
        if max_load <= 0:
            return False
        try:
            load_1m = os.getloadavg()[0]
        except OSError:
            return False
        if load_1m <= max_load:
            return False
        detail = f"loadavg {load_1m:.2f} exceeds {max_load:.2f}"
        logger.warning(
            "MemoryManager startup skipped: %s",
            detail,
        )
        self._set_memory_manager_status("skipped", detail)
        return True

    def _build_memory_manager(self, metrics: _MemoryManagerBootMetrics):
        """Build the ReMe MemoryManager lazily after disable/load guards."""
        self._set_memory_manager_status("starting", "imports")
        from agentscope.tool import Toolkit

        from ...agents.memory import MemoryManager
        from ...agents.model_factory import create_model_and_formatter
        from ...agents.tools import edit_file, read_file, write_file

        metrics.mark("imports")
        self._set_memory_manager_status("starting", "load_config")
        config = load_config()
        max_input_length = config.agents.running.max_input_length
        metrics.mark("load_config")

        self._set_memory_manager_status("starting", "model_factory")
        chat_model, formatter = create_model_and_formatter()
        metrics.mark("model_factory")

        if _env_bool("ADCLAW_REME_LIGHT_TOKEN_COUNTER", True):
            token_counter = _ApproxTokenCounter()
            metrics.mark("light_token_counter")
        else:
            self._set_memory_manager_status("starting", "token_counter")
            from ...agents.utils.token_counting import _get_token_counter

            token_counter = _get_token_counter()
            metrics.mark("token_counter")

        self._set_memory_manager_status("starting", "toolkit")
        toolkit = Toolkit()
        toolkit.register_tool_function(read_file)
        toolkit.register_tool_function(write_file)
        toolkit.register_tool_function(edit_file)
        metrics.mark("toolkit")

        has_embedding_api = bool(os.environ.get("EMBEDDING_API_KEY"))
        has_embedding_model = bool(os.environ.get("EMBEDDING_MODEL_NAME"))
        vector_weight_default = (
            0.7 if has_embedding_api and has_embedding_model else 0.0
        )

        self._set_memory_manager_status("starting", "constructor")
        return MemoryManager(
            working_dir=str(WORKING_DIR),
            chat_model=chat_model,
            formatter=formatter,
            token_counter=token_counter,
            toolkit=toolkit,
            max_input_length=max_input_length,
            memory_compact_ratio=MEMORY_COMPACT_RATIO,
            vector_weight=_env_float(
                "ADCLAW_REME_VECTOR_WEIGHT",
                vector_weight_default,
            ),
            candidate_multiplier=_env_float(
                "ADCLAW_REME_CANDIDATE_MULTIPLIER",
                2.0,
            ),
            tool_result_threshold=_env_int(
                "ADCLAW_REME_TOOL_RESULT_THRESHOLD",
                1000,
            ),
            retention_days=_env_int("ADCLAW_REME_RETENTION_DAYS", 30),
        )

    async def _start_memory_manager(self) -> None:
        """Start ReMe with startup guards and leave the app usable on failure."""
        if self.memory_manager is not None:
            self._set_memory_manager_status("enabled", "already started")
            return
        if self._memory_manager_load_too_high():
            return

        self._apply_memory_manager_safe_defaults()
        metrics = _MemoryManagerBootMetrics()
        self._set_memory_manager_status("starting", "building")
        try:
            memory_manager = await asyncio.to_thread(
                self._build_memory_manager,
                metrics,
            )
            metrics.mark("constructor")

            start_timeout = _env_float(
                "ADCLAW_MEMORY_MANAGER_START_TIMEOUT_SECONDS",
                30.0,
            )
            self._set_memory_manager_status("starting", "starting")
            await asyncio.wait_for(memory_manager.start(), timeout=start_timeout)
            metrics.mark("start")
            self.memory_manager = memory_manager
            self._set_memory_manager_status("enabled", "started")
            logger.info("MemoryManager started")
        except asyncio.TimeoutError:
            logger.warning("MemoryManager startup timed out; continuing without ReMe")
            self.memory_manager = None
            self._set_memory_manager_status("timeout", "startup timed out")
        except Exception as exc:
            logger.exception("MemoryManager start failed: %s", exc)
            self.memory_manager = None
            self._set_memory_manager_status("error", str(exc))

    async def _start_memory_manager_background(self) -> None:
        try:
            delay = _env_float("ADCLAW_MEMORY_MANAGER_BACKGROUND_DELAY_SECONDS", 5.0)
            if delay > 0:
                self._set_memory_manager_status(
                    "scheduled",
                    f"background delay {delay:.1f}s",
                )
                await asyncio.sleep(delay)
            await self._start_memory_manager()
        finally:
            self._memory_manager_start_task = None

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

        if _env_truthy("ADCLAW_DISABLE_MEMORY_MANAGER"):
            logger.warning(
                "MemoryManager disabled by ADCLAW_DISABLE_MEMORY_MANAGER",
            )
            self.memory_manager = None
            self._set_memory_manager_status(
                "disabled",
                "ADCLAW_DISABLE_MEMORY_MANAGER",
            )
            return

        if not _env_truthy("ADCLAW_ENABLE_REME"):
            self.memory_manager = None
            self._set_memory_manager_status(
                "disabled",
                "ADCLAW_ENABLE_REME not set",
            )
            return

        start_mode = os.environ.get(
            "ADCLAW_MEMORY_MANAGER_START_MODE",
            "background",
        ).lower()
        if start_mode in ("disabled", "off", "manual"):
            self.memory_manager = None
            self._set_memory_manager_status(
                "disabled",
                f"ADCLAW_MEMORY_MANAGER_START_MODE={start_mode}",
            )
            return

        if start_mode == "background":
            if self._memory_manager_start_task is None:
                logger.info("MemoryManager scheduled for background startup")
                self._set_memory_manager_status("scheduled", "background")
                self._memory_manager_start_task = asyncio.create_task(
                    self._start_memory_manager_background(),
                )
            return

        await self._start_memory_manager()

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        try:
            if self._memory_manager_start_task is not None:
                self._memory_manager_start_task.cancel()
                self._memory_manager_start_task = None
            if self.memory_manager is not None:
                await self.memory_manager.close()
        except Exception as e:
            logger.error(
                "MemoryManager stop failed: %s", e, exc_info=True,
            )
