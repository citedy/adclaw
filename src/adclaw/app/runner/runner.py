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
from .session import SafeJSONSession, sanitize_filename
from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.model_factory import create_model_and_formatter
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
from ...envs import load_envs_into_environ

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

_STALE_SESSION_BAD_REQUEST_MARKERS = (
    "invalid_parameter",
    "invalid api parameter",
)

_HOST_AI_LIMIT_MARKERS = (
    "adclaw_host_ai_limit_reached",
    "host_ai_limit_reached",
)
_HOST_AI_TRANSIENT_MARKERS = (
    "host_ai_output_budget_exhausted",
    "host_ai_no_visible_output",
)

_TRUTHY_ENV_VALUES = ("1", "true", "yes", "on")
_MANAGED_QUERY_ENV_KEYS = (
    "ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS",
    "ADCLAW_HOST_AI_MAX_OUTPUT_TOKENS",
    "ADCLAW_HOST_AI_MAX_TOKENS",
    "ADCLAW_LLM_TOOL_RESULT_MAX_CHARS",
    "ADCLAW_HOST_AI_TOOL_RESULT_TRUNCATION",
)


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


def _model_client_timeout_seconds(
    query_timeout_seconds: float,
    configured_timeout_seconds: float | None = None,
) -> float | None:
    """Return a provider-client timeout bounded by the user query timeout.

    The outer async stream timeout is not enough when a provider SDK blocks
    while waiting for the first streamed token. In hosted mode we set the HTTP
    client timeout slightly below the whole-query timeout so the runner can
    surface a safe failure instead of leaving the chat request open forever.
    """
    configured = (
        float(configured_timeout_seconds)
        if configured_timeout_seconds is not None
        and configured_timeout_seconds > 0
        else None
    )
    if query_timeout_seconds <= 0:
        return configured

    query_cap = max(1.0, float(query_timeout_seconds) - 1.0)
    if configured is None:
        return query_cap
    return min(configured, query_cap)


def _refresh_persisted_envs_for_query() -> None:
    """Load envs.json values that may have been bootstrapped after startup.

    Hosted AdClaw writes managed secrets and runtime guardrails into
    ``working.secret/envs.json`` from outside the Python process. A warm app
    process may have imported before that file existed, so query-time refresh is
    required for values like ``ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS``.
    """
    try:
        envs = load_envs_into_environ()
        for key in _MANAGED_QUERY_ENV_KEYS:
            value = envs.get(key)
            if value is not None:
                os.environ[key] = value
    except Exception:
        logger.warning(
            "Failed to refresh persisted env vars before agent query",
            exc_info=True,
        )


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


def _is_stale_session_bad_request(exc: Exception) -> bool:
    """Return True if a provider rejected stale formatted session history."""
    err_str = str(exc).lower()
    return any(marker in err_str for marker in _STALE_SESSION_BAD_REQUEST_MARKERS)


def _exception_search_text(exc: Exception) -> str:
    """Collect safe exception text for provider error classification."""
    parts = [str(exc)]
    body = getattr(exc, "body", None)
    if body is not None:
        parts.append(repr(body))
    response = getattr(exc, "response", None)
    response_text = getattr(response, "text", None)
    if response_text:
        parts.append(str(response_text))
    return "\n".join(parts).lower()


def _is_host_ai_limit_error(exc: Exception) -> bool:
    """Return True when the managed Host AI quota gate rejected the call."""
    text = _exception_search_text(exc)
    if any(marker in text for marker in _HOST_AI_LIMIT_MARKERS):
        return True
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    return status_code == 429 and "host ai" in text and "limit" in text


def _is_host_ai_transient_error(exc: Exception) -> bool:
    """Return true when managed Host AI failed to produce usable output."""
    text = _exception_search_text(exc)
    return any(marker in text for marker in _HOST_AI_TRANSIENT_MARKERS)


def _active_provider_is_host_ai() -> bool:
    """Return true when the active model slot is managed AdClaw Host AI."""
    try:
        from ...providers.store import get_active_llm_config

        return (
            getattr(get_active_llm_config(), "provider_id", "")
            == "adclaw-host-ai"
        )
    except (KeyError, ValueError, AttributeError):
        return False


def _host_ai_limit_message() -> str:
    """Customer-facing copy for the hosted monthly Host AI cap."""
    return (
        "Included AdClaw Host AI messages for this billing period are used. "
        "Connect your own LLM key in Settings -> Models to continue now, "
        "or wait for the next billing period when the included messages reset."
    )


def _host_ai_transient_message() -> str:
    """Customer-facing copy for managed Host AI empty/truncated answers."""
    return (
        "Included AdClaw Host AI could not finish a visible answer. "
        "Retry once with a shorter request, or connect your own LLM key "
        "in Settings -> Models if it repeats."
    )


class AgentQueryTimeoutError(TimeoutError):
    """Raised when a single user-facing agent query exceeds the safe limit."""


QUERY_TIMEOUT_EPSILON_SECONDS = 0.05


def _agent_query_timeout_message(timeout_seconds: float) -> str:
    """Return customer-safe copy for a stopped long-running request."""
    seconds = int(timeout_seconds)
    return (
        f"This request took longer than {seconds} seconds, so I stopped it "
        "safely instead of leaving the chat hanging. Try a shorter request, "
        "or start a fresh task if this keeps happening."
    )


def _persona_mcp_client_keys(persona):
    """Return selected MCP client keys, preserving legacy all-client defaults."""
    selected_mcp_clients = getattr(persona, "mcp_clients", None)
    return selected_mcp_clients or None


async def _raise_agent_query_timeout(agent, stream, timeout_seconds: float, exc):
    """Stop a query stream and raise a customer-safe timeout error."""
    try:
        await stream.aclose()
    except Exception:
        logger.debug("Agent stream close failed after query timeout", exc_info=True)

    try:
        await agent.interrupt()
    except Exception:
        logger.warning("Agent interrupt failed after query timeout", exc_info=True)

    raise AgentQueryTimeoutError(
        _agent_query_timeout_message(timeout_seconds),
    ) from exc


async def _stream_agent_messages(agent, msgs, *, timeout_seconds: float):
    """Stream AgentScope messages with an optional whole-query timeout."""

    stream = stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    )

    if timeout_seconds <= 0:
        async for item in stream:
            yield item
        return

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            await _raise_agent_query_timeout(
                agent,
                stream,
                timeout_seconds,
                TimeoutError(),
            )

        try:
            item = await asyncio.wait_for(stream.__anext__(), timeout=remaining)
        except StopAsyncIteration:
            return
        except TimeoutError as exc:
            if loop.time() >= deadline - QUERY_TIMEOUT_EPSILON_SECONDS:
                await _raise_agent_query_timeout(
                    agent,
                    stream,
                    timeout_seconds,
                    exc,
                )
            raise

        yield item


def _same_model_slot(candidate, primary) -> bool:
    """Return True when a fallback slot points at the current provider/model."""
    if candidate is None or primary is None:
        return False
    candidate_provider = getattr(candidate, "provider_id", "")
    primary_provider = getattr(primary, "provider_id", "")
    candidate_model = getattr(candidate, "model", "")
    primary_model = getattr(primary, "model", "")
    return bool(
        candidate_provider
        and primary_provider
        and candidate_model
        and primary_model
        and candidate_provider == primary_provider
        and candidate_model == primary_model
    )


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
        query_timeout_seconds = 0.0

        try:
            session_id = request.session_id
            base_session_id = request.session_id
            user_id = request.user_id
            channel = getattr(request, "channel", DEFAULT_CHANNEL)
            _refresh_persisted_envs_for_query()

            logger.info(
                "Handle agent query:\n%s",
                json.dumps(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "channel": channel,
                        "msgs_len": len(msgs) if msgs else 0,
                        "msgs_redacted": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            config = load_config()
            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length
            query_timeout_seconds = _env_float(
                "ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS",
                0.0,
            )

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
                session_id = sanitize_filename(f"{persona.id}::{session_id}")

            # Get only the MCP clients selected for the routed persona. This
            # keeps hosted chat prompts small and prevents one persona from
            # seeing tools that belong to another persona.
            mcp_clients = []
            if self._mcp_manager is not None:
                if persona is not None:
                    mcp_clients = await self._mcp_manager.get_clients(
                        _persona_mcp_client_keys(persona),
                    )
                else:
                    mcp_clients = await self._mcp_manager.get_clients()

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
            model_timeout_seconds = _model_client_timeout_seconds(
                query_timeout_seconds,
                fallback_cfg.timeout_seconds
                if fallback_cfg.enabled
                else None,
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
                persona_manager=persona_mgr,
                timeout_seconds=model_timeout_seconds,
            )
            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)

            logger.debug(
                "Agent Query messages redacted: count=%s",
                len(msgs) if msgs else 0,
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
                async for msg, last in _stream_agent_messages(
                    agent,
                    msgs,
                    timeout_seconds=query_timeout_seconds,
                ):
                    text = extract_visible_text(msg)
                    if getattr(msg, "role", None) == "assistant" and text:
                        assistant_text = text
                    yield msg, last
            except Exception as first_err:
                if isinstance(first_err, AgentQueryTimeoutError):
                    from agentscope.message import Msg
                    assistant_text = str(first_err)
                    session_state_loaded = False
                    if self.error_tracker:
                        self.error_tracker.record_failure(session_id)
                    yield Msg(
                        name="system",
                        role="assistant",
                        content=assistant_text,
                    ), True
                    return

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
                    if _is_stale_session_bad_request(first_err):
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
                            async for msg, last in _stream_agent_messages(
                                agent,
                                msgs,
                                timeout_seconds=query_timeout_seconds,
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
                    get_active_llm_config,
                    get_fallback_config,
                    resolve_fallback_chain,
                )
                from agentscope.message import Msg

                fallback_cfg = get_fallback_config()
                if (
                    not fallback_cfg.enabled
                    and query_timeout_seconds > 0
                    and isinstance(first_err, _OAITimeout)
                    and _active_provider_is_host_ai()
                ):
                    assistant_text = _agent_query_timeout_message(
                        query_timeout_seconds,
                    )
                    yield Msg(
                        name="system",
                        role="assistant",
                        content=assistant_text,
                    ), True
                    return

                host_ai_limit_reached = _is_host_ai_limit_error(first_err)
                host_ai_transient_seen = _is_host_ai_transient_error(first_err)
                non_host_provider_error_seen = not (
                    host_ai_limit_reached or host_ai_transient_seen
                )

                def _yield_host_ai_limit_msg():
                    return Msg(
                        name="system",
                        role="assistant",
                        content=_host_ai_limit_message(),
                    )

                def _yield_host_ai_transient_msg():
                    return Msg(
                        name="system",
                        role="assistant",
                        content=_host_ai_transient_message(),
                    )

                if not fallback_cfg.enabled:
                    if host_ai_limit_reached:
                        assistant_text = _host_ai_limit_message()
                        yield _yield_host_ai_limit_msg(), True
                        return
                    if host_ai_transient_seen:
                        assistant_text = _host_ai_transient_message()
                        yield _yield_host_ai_transient_msg(), True
                        return
                    raise

                resolved_chain = resolve_fallback_chain()
                if not resolved_chain:
                    if host_ai_limit_reached:
                        assistant_text = _host_ai_limit_message()
                        yield _yield_host_ai_limit_msg(), True
                        return
                    if host_ai_transient_seen:
                        assistant_text = _host_ai_transient_message()
                        yield _yield_host_ai_transient_msg(), True
                        return
                    raise

                try:
                    primary_cfg = get_active_llm_config()
                except (KeyError, ValueError, AttributeError) as cfg_err:
                    logger.debug(
                        "Could not resolve active LLM for fallback de-dupe: %s",
                        cfg_err,
                    )
                    primary_cfg = None

                original_fallback_count = len(resolved_chain)
                resolved_chain = [
                    cfg for cfg in resolved_chain
                    if not _same_model_slot(cfg, primary_cfg)
                ]
                skipped_same_slot_count = original_fallback_count - len(resolved_chain)
                if skipped_same_slot_count:
                    logger.warning(
                        "Skipped %d fallback slot(s) matching the active LLM",
                        skipped_same_slot_count,
                    )
                if not resolved_chain:
                    if host_ai_limit_reached:
                        assistant_text = _host_ai_limit_message()
                        yield _yield_host_ai_limit_msg(), True
                        return
                    if host_ai_transient_seen:
                        assistant_text = _host_ai_transient_message()
                        yield _yield_host_ai_transient_msg(), True
                        return
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

                for fb_cfg in resolved_chain:
                    try:
                        fallback_timeout_seconds = _model_client_timeout_seconds(
                            query_timeout_seconds,
                            fallback_cfg.timeout_seconds,
                        )
                        fb_model, fb_formatter = create_model_and_formatter(
                            fb_cfg,
                            timeout_seconds=fallback_timeout_seconds,
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
                            persona_manager=getattr(agent, "_persona_manager", None),
                            model=fb_model,
                            formatter=fb_formatter,
                        )
                        await fb_agent.register_mcp_clients()
                        fb_agent.set_console_output_enabled(enabled=False)

                        async for msg, last in _stream_agent_messages(
                            fb_agent,
                            msgs,
                            timeout_seconds=query_timeout_seconds,
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
                        fb_host_ai_limit_reached = _is_host_ai_limit_error(fb_err)
                        fb_host_ai_transient_seen = _is_host_ai_transient_error(
                            fb_err,
                        )
                        host_ai_limit_reached = (
                            host_ai_limit_reached
                            or fb_host_ai_limit_reached
                        )
                        host_ai_transient_seen = (
                            host_ai_transient_seen
                            or fb_host_ai_transient_seen
                        )
                        if not (
                            fb_host_ai_limit_reached
                            or fb_host_ai_transient_seen
                        ):
                            non_host_provider_error_seen = True
                        logger.warning(
                            "Fallback model %s failed with API error: %s",
                            fb_cfg.model, fb_err,
                        )
                        continue

                # All fallbacks exhausted — notify user and re-raise
                exhausted_content = (
                    _host_ai_limit_message()
                    if host_ai_limit_reached and not non_host_provider_error_seen
                    else _host_ai_transient_message()
                    if host_ai_transient_seen and not non_host_provider_error_seen
                    else (
                        f"All {len(resolved_chain)} fallback model(s) "
                        "also failed. Please check your provider configurations."
                    )
                )
                exhausted_msg = Msg(
                    name="system",
                    role="assistant",
                    content=exhausted_content,
                )
                assistant_text = exhausted_content
                yield exhausted_msg, False
                raise first_err

            # If we reach here without exception, processing succeeded
            if self.error_tracker:
                self.error_tracker.record_success(session_id)

        except asyncio.CancelledError:
            session_state_loaded = False
            if agent is not None:
                await agent.interrupt()
            raise
        except Exception as e:
            if isinstance(e, AgentQueryTimeoutError):
                from agentscope.message import Msg
                assistant_text = str(e)
                session_state_loaded = False
                if self.error_tracker:
                    self.error_tracker.record_failure(session_id)
                yield Msg(
                    name="system",
                    role="assistant",
                    content=assistant_text,
                ), True
                return

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

                    async for msg, last in _stream_agent_messages(
                        agent,
                        msgs,
                        timeout_seconds=query_timeout_seconds,
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
