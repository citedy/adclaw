# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,unused-argument
import asyncio
import json
import mimetypes
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentResponse,
    Message,
    MessageType,
    SequenceNumberGenerator,
    TextContent,
)

from .runner import AgentRunner
from .runner.runner import _agent_query_timeout_message
from ..agents.persona_manager import PersonaManager
from ..config import (  # pylint: disable=no-name-in-module
    load_config,
    update_last_dispatch,
    ConfigWatcher,
)
from ..config.utils import get_jobs_path, get_chats_path, get_config_path
from ..constant import DOCS_ENABLED, LOG_LEVEL_ENV, CORS_ORIGINS, WORKING_DIR
from ..__version__ import __version__
from ..utils.logging import setup_logger
from .channels import ChannelManager  # pylint: disable=no-name-in-module
from .channels.utils import make_process_from_runner
from .mcp import MCPClientManager, MCPConfigWatcher  # MCP hot-reload support
from ..memory_agent.manager import AOMManager
from ..memory_agent.models import AOMConfig as AOMConfigModel
from .runner.repo.json_repo import JsonChatRepository
from .crons.repo.json_repo import JsonJobRepository
from .crons.manager import CronManager
from .runner.manager import ChatManager
from .routers import router as api_router
from ..envs import load_envs_into_environ

# BaseExceptionGroup is a builtin in 3.11+; on 3.10 we use the
# `exceptiongroup` backport (declared in pyproject.toml only for 3.10).
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup  # noqa: F401

# Apply log level on load so reload child process gets same level as CLI.
logger = setup_logger(os.environ.get(LOG_LEVEL_ENV, "info"))

# Ensure static assets are served with browser-compatible MIME types across
# platforms (notably Windows may miss .js/.mjs mappings).
mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/wasm", ".wasm")

# Load persisted env vars into os.environ at module import time
# so they are available before the lifespan starts.
load_envs_into_environ()

runner = AgentRunner()

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    runner=runner,
)


def _schedule_mcp_initialization(
    mcp_manager: MCPClientManager,
    mcp_config,
) -> asyncio.Task:
    """Initialize MCP clients without blocking FastAPI startup."""

    async def _init_mcp_clients() -> None:
        """Connect configured MCP clients in a background task."""
        try:
            await mcp_manager.init_from_config(mcp_config)
            logger.debug("MCP client manager initialized")
        except (Exception, BaseExceptionGroup):
            logger.exception("Failed to initialize MCP manager")

    return asyncio.create_task(_init_mcp_clients(), name="mcp_initial_config")


@asynccontextmanager
async def lifespan(app: FastAPI):  # pylint: disable=too-many-statements
    """Start and stop AdClaw app services around the FastAPI lifecycle."""
    await runner.start()

    # --- MCP client manager init (independent module, hot-reloadable) ---
    config = load_config()
    mcp_manager = MCPClientManager()
    mcp_disabled = os.environ.get("ADCLAW_DISABLE_MCP", "").lower() in (
        "1",
        "true",
        "yes",
    )
    # Defer scheduling until the try/finally below is active so startup aborts
    # cancel the background MCP connection task instead of orphaning it.
    mcp_initial_config = None
    mcp_init_task = None
    runner.set_mcp_manager(mcp_manager)
    if mcp_disabled:
        logger.warning("MCP disabled by ADCLAW_DISABLE_MCP")
    elif hasattr(config, "mcp"):
        mcp_initial_config = config.mcp
        logger.debug("MCP client manager initialization deferred")

    # --- Always-On Memory Agent init ---
    aom_manager = None
    aom_config = getattr(config.agents, "always_on_memory", None)
    if aom_config and aom_config.enabled:
        try:
            from ..constant import WORKING_DIR as _wd

            async def _aom_llm_caller(prompt: str) -> str:
                from ..agents.model_factory import create_model_and_formatter
                model, _fmt = create_model_and_formatter()
                # Disable streaming for AOM calls — we need the full response
                orig_stream = getattr(model, "stream", None)
                model.stream = False
                try:
                    resp = await model([{"role": "user", "content": prompt}])
                finally:
                    if orig_stream is not None:
                        model.stream = orig_stream
                # Extract text from ChatResponse.content (list of {type, text} dicts)
                content = resp.content if hasattr(resp, "content") else resp
                if isinstance(content, list):
                    parts = [
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in content
                    ]
                    return "".join(parts)
                return str(content)

            aom_manager = AOMManager(
                working_dir=_wd,
                config=AOMConfigModel(**aom_config.model_dump()),
                llm_caller=_aom_llm_caller,
            )
            await aom_manager.start()
            runner.set_aom_manager(aom_manager)
            logger.info("AOM Manager started")
        except Exception:
            logger.exception("Failed to start AOM Manager")
            aom_manager = None

    # --- channel connector init/start (from config.json) ---
    channel_manager = ChannelManager.from_config(
        process=make_process_from_runner(runner),
        config=config,
        on_last_dispatch=update_last_dispatch,
    )
    # Wire manager ↔ channels for force_clear and timeout
    from ..constant import WORKING_DIR
    channel_manager.set_session_dir(str(WORKING_DIR / "sessions"))
    for ch in channel_manager.channels:
        ch.set_channel_manager(channel_manager)

    await channel_manager.start_all()

    # --- cron init/start ---
    repo = JsonJobRepository(get_jobs_path())
    cron_manager = CronManager(
        repo=repo,
        runner=runner,
        channel_manager=channel_manager,
        timezone="UTC",
    )
    await cron_manager.start()

    # --- chat manager init and connect to runner.session ---
    chat_repo = JsonChatRepository(get_chats_path())
    chat_manager = ChatManager(
        repo=chat_repo,
    )

    runner.set_chat_manager(chat_manager)

    # --- config file watcher (channels + heartbeat hot-reload on change) ---
    config_watcher = ConfigWatcher(
        channel_manager=channel_manager,
        cron_manager=cron_manager,
    )
    await config_watcher.start()

    # --- MCP config watcher (auto-reload MCP clients on change) ---
    mcp_watcher = None
    if mcp_disabled:
        logger.warning("MCP watcher disabled by ADCLAW_DISABLE_MCP")
    elif hasattr(config, "mcp"):
        try:
            mcp_watcher = MCPConfigWatcher(
                mcp_manager=mcp_manager,
                config_loader=load_config,
                config_path=get_config_path(),
            )
            await mcp_watcher.start()
            logger.debug("MCP config watcher started")
        except Exception:
            logger.exception("Failed to start MCP watcher")

    # expose to endpoints
    app.state.runner = runner
    app.state.channel_manager = channel_manager
    app.state.cron_manager = cron_manager
    app.state.chat_manager = chat_manager
    app.state.config_watcher = config_watcher
    app.state.mcp_manager = mcp_manager
    app.state.mcp_watcher = mcp_watcher
    app.state.aom_manager = aom_manager

    # --- Agent watchdog (auto-restart on crash) ---
    from .watchdog import AgentWatchdog, SessionErrorTracker
    error_tracker = SessionErrorTracker(max_consecutive=3, cooldown_seconds=120)
    watchdog = AgentWatchdog(
        runner=runner, check_interval=60, max_restarts=5,
        error_tracker=error_tracker,
    )
    runner.error_tracker = error_tracker
    channel_manager.set_error_tracker(error_tracker)
    watchdog_task = asyncio.create_task(watchdog.start())
    app.state.watchdog = watchdog

    try:
        if mcp_initial_config is not None:
            mcp_init_task = _schedule_mcp_initialization(
                mcp_manager,
                mcp_initial_config,
            )
            logger.debug("MCP client manager initialization scheduled")
        yield
    finally:
        if hasattr(app.state, "watchdog"):
            app.state.watchdog.stop()
        # stop order: watchers -> cron -> channels -> mcp -> runner
        try:
            await config_watcher.stop()
        except Exception:
            pass
        if mcp_watcher:
            try:
                await mcp_watcher.stop()
            except Exception:
                pass
        if mcp_init_task and not mcp_init_task.done():
            mcp_init_task.cancel()
            try:
                await mcp_init_task
            except asyncio.CancelledError:
                pass
        try:
            await cron_manager.stop()
        finally:
            await channel_manager.stop_all()
            if mcp_manager:
                try:
                    await mcp_manager.close_all()
                except Exception:
                    pass
            if aom_manager:
                try:
                    await aom_manager.stop()
                except Exception:
                    pass
            await runner.stop()


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)

# Apply CORS middleware if CORS_ORIGINS is set
if CORS_ORIGINS:
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Console static dir: env, or adclaw package data (console), or cwd.
_CONSOLE_STATIC_ENV = "ADCLAW_CONSOLE_STATIC_DIR"


def _resolve_console_static_dir() -> str:
    if os.environ.get(_CONSOLE_STATIC_ENV):
        return os.environ[_CONSOLE_STATIC_ENV]
    # Shipped dist lives in adclaw package as static data (not a Python pkg).
    pkg_dir = Path(__file__).resolve().parent.parent
    candidate = pkg_dir / "console"
    if candidate.is_dir() and (candidate / "index.html").exists():
        return str(candidate)
    # the following code can be removed after next release,
    # because the console will be output to adclaw's
    # `src/adclaw/console/` directory directly by vite.
    cwd = Path(os.getcwd())
    for subdir in ("console/dist", "console_dist"):
        candidate = cwd / subdir
        if candidate.is_dir() and (candidate / "index.html").exists():
            return str(candidate)
    return str(cwd / "console" / "dist")


_CONSOLE_STATIC_DIR = _resolve_console_static_dir()
_CONSOLE_INDEX = (
    Path(_CONSOLE_STATIC_DIR) / "index.html" if _CONSOLE_STATIC_DIR else None
)
logger.info(f"STATIC_DIR: {_CONSOLE_STATIC_DIR}")


@app.get("/")
def read_root():
    if _CONSOLE_INDEX and _CONSOLE_INDEX.exists():
        return FileResponse(_CONSOLE_INDEX)
    return {
        "message": (
            "AdClaw Web Console is not available. "
            "If you installed AdClaw from source code, please run "
            "`npm ci && npm run build` in AdClaw's `console/` "
            "directory, and restart AdClaw to enable the web console."
        ),
    }


@app.get("/api/version")
def get_version():
    """Return the current AdClaw version."""
    return {"version": __version__}


_AGENT_PROCESS_TIMEOUT_ENV = "ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS"
_AGENT_PROCESS_HEARTBEAT_SECONDS = 10.0
_AGENT_PROCESS_CLEANUP_SECONDS = 2.0
_HOST_AI_DIRECT_CHAT_ENV = "ADCLAW_HOST_AI_DIRECT_CHAT"
_HOST_AI_PROVIDER_ID = "adclaw-host-ai"
_HOST_AI_DIRECT_HISTORY_LIMIT_ENV = "ADCLAW_HOST_AI_DIRECT_HISTORY_MESSAGES"
_HOST_AI_DIRECT_DEFAULT_HISTORY_LIMIT = 10
_HOST_AI_DIRECT_MAX_OUTPUT_ENV = "ADCLAW_HOST_AI_MAX_OUTPUT_TOKENS"
_HOST_AI_DIRECT_LEGACY_MAX_OUTPUT_ENV = "ADCLAW_HOST_AI_MAX_TOKENS"
_HOST_AI_DIRECT_DEFAULT_MAX_OUTPUT = 512
_HOST_AI_DIRECT_ALLOWED_HOSTS_ENV = "ADCLAW_HOST_AI_DIRECT_ALLOWED_HOSTS"
_HOST_AI_DIRECT_DEFAULT_ALLOWED_HOSTS = ("real.adclaw.app",)
_HOST_AI_DIRECT_DEFAULT_TIMEOUT_SECONDS = 55.0
_HOST_AI_TOKEN_PREFIX = "ach_"
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class _HostAiDirectConfig:
    """Resolved OpenAI-compatible Host AI config for hosted direct chat."""

    base_url: str
    api_key: str
    model: str


class _HostAiDirectCustomerError(Exception):
    """Customer-safe Host AI direct-chat failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _agent_process_timeout_seconds() -> float:
    """Return the hosted chat timeout from persisted env vars."""
    try:
        load_envs_into_environ()
    except Exception:
        logger.warning(
            "Failed to refresh persisted env vars before agent process",
            exc_info=True,
        )
    raw = os.environ.get(_AGENT_PROCESS_TIMEOUT_ENV, "0")
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning(
            "Invalid %s=%r; disabling endpoint timeout",
            _AGENT_PROCESS_TIMEOUT_ENV,
            raw,
        )
        return 0.0


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY_ENV_VALUES


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, value, default)
        return default


def _host_ai_direct_chat_enabled() -> bool:
    """Return true when hosted AdClaw should bypass AgentScope chat loop."""
    try:
        load_envs_into_environ()
    except Exception:
        logger.warning(
            "Failed to refresh persisted env vars before hosted direct chat",
            exc_info=True,
        )
    return _env_truthy(_HOST_AI_DIRECT_CHAT_ENV)


def _host_matches_allowed_pattern(hostname: str, pattern: str) -> bool:
    """Return true when hostname matches an exact or wildcard host pattern."""
    host = hostname.strip().lower()
    allowed = pattern.strip().lower()
    if not host or not allowed:
        return False
    if allowed.startswith("*."):
        suffix = allowed[1:]
        return host.endswith(suffix) and host != allowed[2:]
    return host == allowed


def _host_ai_direct_allowed_hosts() -> tuple[str, ...]:
    raw = os.environ.get(_HOST_AI_DIRECT_ALLOWED_HOSTS_ENV, "")
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    return values or _HOST_AI_DIRECT_DEFAULT_ALLOWED_HOSTS


def _host_ai_direct_base_url_allowed(base_url: str) -> bool:
    """Fail closed unless the direct Host AI endpoint is the managed origin."""
    try:
        parsed = urlsplit(base_url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.path.rstrip("/") != "/api/host-ai/v1":
        return False
    hostname = parsed.hostname or ""
    return any(
        _host_matches_allowed_pattern(hostname, allowed)
        for allowed in _host_ai_direct_allowed_hosts()
    )


def _active_host_ai_direct_config() -> _HostAiDirectConfig | None:
    """Resolve the active Host AI provider without exposing credentials."""
    try:
        from ..providers.store import get_active_llm_config

        cfg = get_active_llm_config()
    except (KeyError, ValueError, AttributeError):
        return None

    if getattr(cfg, "provider_id", "") != _HOST_AI_PROVIDER_ID:
        return None

    base_url = (getattr(cfg, "base_url", "") or "").strip()
    api_key = (getattr(cfg, "api_key", "") or "").strip()
    model = (getattr(cfg, "model", "") or "").strip()
    if not (base_url and api_key and model):
        return None
    if not api_key.startswith(_HOST_AI_TOKEN_PREFIX):
        logger.warning("Host AI direct chat skipped: unexpected token shape")
        return None
    if not _host_ai_direct_base_url_allowed(base_url):
        logger.warning("Host AI direct chat skipped: unmanaged base URL")
        return None
    return _HostAiDirectConfig(base_url=base_url, api_key=api_key, model=model)


def _request_text_from_content(content) -> str:
    """Extract visible text from AgentScope-runtime request content."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(part for part in parts if part).strip()


def _request_messages_for_host_ai(request: dict) -> list[dict[str, str]]:
    """Normalize console request history into OpenAI chat messages."""
    raw_messages = request.get("input")
    if not isinstance(raw_messages, list):
        return []

    messages: list[dict[str, str]] = []
    for raw in raw_messages:
        if not isinstance(raw, dict):
            continue
        role = raw.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = _request_text_from_content(raw.get("content"))
        if not text:
            continue
        messages.append({"role": role, "content": text})

    history_limit = max(
        1,
        _env_int(
            _HOST_AI_DIRECT_HISTORY_LIMIT_ENV,
            _HOST_AI_DIRECT_DEFAULT_HISTORY_LIMIT,
        ),
    )
    return messages[-history_limit:]


def _latest_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _host_ai_direct_max_output_tokens() -> int:
    if os.environ.get(_HOST_AI_DIRECT_MAX_OUTPUT_ENV) is not None:
        value = _env_int(
            _HOST_AI_DIRECT_MAX_OUTPUT_ENV,
            _HOST_AI_DIRECT_DEFAULT_MAX_OUTPUT,
        )
    else:
        value = _env_int(
            _HOST_AI_DIRECT_LEGACY_MAX_OUTPUT_ENV,
            _HOST_AI_DIRECT_DEFAULT_MAX_OUTPUT,
        )
    return max(64, min(value, 4096))


def _host_ai_persona_context(
    request: dict,
    messages: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]], str | None]:
    """Build hosted direct-chat system context and strip leading @tag."""
    latest_user_text = _latest_user_message(messages)
    persona = None
    persona_mgr = None
    resolved_persona_id = None

    try:
        config = load_config()
        persona_mgr = PersonaManager(
            working_dir=str(WORKING_DIR),
            personas=getattr(config.agents, "personas", []),
        )
    except Exception:
        persona_mgr = None

    if persona_mgr is not None:
        persona_id = persona_mgr.resolve_tag(latest_user_text)
        session_id = request.get("session_id")
        if persona_id:
            persona = persona_mgr.get_persona(persona_id)
            resolved_persona_id = persona_id if persona is not None else None
        elif session_id:
            try:
                sticky_id = runner._session_persona_map.get(session_id)
            except AttributeError:
                sticky_id = None
            if sticky_id:
                persona = persona_mgr.get_persona(sticky_id)
                resolved_persona_id = sticky_id if persona is not None else None
        if persona is None:
            persona = persona_mgr.get_coordinator()
            resolved_persona_id = getattr(persona, "id", None)

    normalized_messages = list(messages)
    if persona_mgr is not None and normalized_messages:
        for index in range(len(normalized_messages) - 1, -1, -1):
            if normalized_messages[index].get("role") == "user":
                normalized_messages[index] = {
                    **normalized_messages[index],
                    "content": persona_mgr.strip_tag(
                        normalized_messages[index]["content"],
                    ),
                }
                break

    lines = [
        "You are running inside AdClaw Host, a private AI marketing office.",
        "Answer as the selected marketing specialist.",
        "Keep responses concise, concrete, and useful for a customer dashboard chat.",
        "Do not claim that you executed local shell commands, browser actions, files, or MCP tools unless a tool result is explicitly present in the conversation.",
        "If the user asks for a handoff to another @persona, summarize the handoff and address the target persona by name.",
    ]
    if os.environ.get("CITEDY_API_KEY"):
        lines.append(
            "Citedy workspace connected: the customer has Citedy credits and Citedy tooling available in this hosted workspace.",
        )

    if persona is not None:
        lines.append(f"Selected persona: {persona.name} (@{persona.id}).")
        if getattr(persona, "soul_md", ""):
            lines.append(f"Persona profile:\n{persona.soul_md[:1600]}")
        skills = [s for s in getattr(persona, "skills", []) if s]
        if skills:
            lines.append("Enabled skill packs: " + ", ".join(skills[:8]) + ".")
        mcp_clients = [c for c in getattr(persona, "mcp_clients", []) if c]
        if mcp_clients:
            lines.append("Enabled MCP clients: " + ", ".join(mcp_clients[:8]) + ".")

    if persona_mgr is not None and persona_mgr.all_personas:
        lines.append(persona_mgr.get_team_summary()[:1600])

    return "\n\n".join(lines), normalized_messages, resolved_persona_id


async def _stream_host_ai_direct_completion(
    cfg: _HostAiDirectConfig,
    messages: list[dict[str, str]],
    timeout_seconds: float,
):
    """Stream text deltas from the OpenAI-compatible Host AI endpoint."""
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required for hosted direct chat") from exc

    url = f"{cfg.base_url.rstrip('/')}/chat/completions"
    timeout = httpx.Timeout(
        max(1.0, timeout_seconds) if timeout_seconds > 0 else 60.0,
        connect=10.0,
    )
    payload = {
        "model": cfg.model,
        "messages": messages,
        "stream": True,
        "max_tokens": _host_ai_direct_max_output_tokens(),
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            url,
            headers=headers,
            json=payload,
        ) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise await _host_ai_direct_customer_error(response) from exc
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                data = await response.aread()
                payload_json = json.loads(data.decode("utf-8"))
                choice = (payload_json.get("choices") or [{}])[0]
                content = (
                    choice.get("message", {}).get("content")
                    or choice.get("text")
                    or ""
                )
                if content:
                    yield str(content)
                return

            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    return
                try:
                    payload_json = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choice = (payload_json.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                content = (
                    delta.get("content")
                    or choice.get("text")
                    or payload_json.get("response")
                    or payload_json.get("text")
                    or ""
                )
                if content:
                    yield str(content)


async def _host_ai_direct_customer_error(response) -> _HostAiDirectCustomerError:
    """Map upstream Host AI failures to redacted customer-safe errors."""
    code = "adclaw_host_ai_unavailable"
    try:
        body = await response.aread()
        payload = json.loads(body.decode("utf-8"))
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            code = error["code"]
    except Exception:
        code = "adclaw_host_ai_unavailable"

    if response.status_code == 429 or code == "adclaw_host_ai_limit_reached":
        return _HostAiDirectCustomerError(
            "adclaw_host_ai_limit_reached",
            (
                "Included AdClaw Host AI messages for this billing period are "
                "used. Connect your own LLM key in Settings -> Models, or wait "
                "for the next period when included messages reset."
            ),
        )
    if response.status_code in (401, 402):
        return _HostAiDirectCustomerError(
            code,
            (
                "AdClaw Host AI needs an active hosted workspace session. "
                "Return to the Host dashboard and open the workspace again."
            ),
        )
    return _HostAiDirectCustomerError(
        code,
        (
            "Included AdClaw Host AI is temporarily unavailable. Retry once, "
            "or connect your own LLM key in Settings -> Models if it repeats."
        ),
    )


async def _host_ai_direct_sse_events(
    request: dict,
    cfg: _HostAiDirectConfig,
    timeout_seconds: float,
):
    """Yield protocol-compatible SSE events for hosted direct chat."""
    seq = SequenceNumberGenerator()
    request_messages = _request_messages_for_host_ai(request)
    system_context, normalized_messages, resolved_persona_id = _host_ai_persona_context(
        request,
        request_messages,
    )
    completion_messages = [
        {"role": "system", "content": system_context},
        *normalized_messages,
    ]
    message = Message(type=MessageType.MESSAGE, role="assistant")
    content = TextContent(index=0, msg_id=message.id, text="")
    response = AgentResponse(
        id=request.get("id"),
        session_id=request.get("session_id"),
    )
    output_text = ""
    timed_out = False

    yield seq.yield_with_sequence(message.in_progress())
    yield seq.yield_with_sequence(content.in_progress())

    stream = _stream_host_ai_direct_completion(
        cfg,
        completion_messages,
        timeout_seconds,
    )
    try:
        if timeout_seconds <= 0:
            async for chunk in stream:
                output_text += chunk
                yield seq.yield_with_sequence(
                    TextContent(
                        index=0,
                        msg_id=message.id,
                        text=chunk,
                        delta=True,
                    ).in_progress(),
                )
        else:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout_seconds
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), remaining)
                except StopAsyncIteration:
                    break
                output_text += chunk
                yield seq.yield_with_sequence(
                    TextContent(
                        index=0,
                        msg_id=message.id,
                        text=chunk,
                        delta=True,
                    ).in_progress(),
                )
    except asyncio.TimeoutError:
        try:
            await asyncio.wait_for(stream.aclose(), _AGENT_PROCESS_CLEANUP_SECONDS)
        except Exception:
            logger.debug("Host AI direct stream close failed after timeout")
        timed_out = True
        output_text = _agent_query_timeout_message(timeout_seconds)

    if not output_text.strip():
        output_text = (
            "I could not produce a visible answer. Retry once with a shorter "
            "request, or open Settings -> Models to connect your own provider."
        )

    completed_content = TextContent(
        index=0,
        msg_id=message.id,
        text=output_text,
    ).completed()
    yield seq.yield_with_sequence(completed_content)
    message.content = [completed_content]
    yield seq.yield_with_sequence(message.completed())
    response.add_new_message(message)
    yield seq.yield_with_sequence(response.completed())
    if not timed_out and resolved_persona_id and request.get("session_id"):
        try:
            runner._session_persona_map[request["session_id"]] = resolved_persona_id
        except AttributeError:
            pass


def _sse_json(data: str) -> str:
    return f"data: {data}\n\n"


def _sse_event(event) -> str:
    if hasattr(event, "model_dump_json"):
        return _sse_json(event.model_dump_json())
    if hasattr(event, "json"):
        return _sse_json(event.json())
    return _sse_json(json.dumps(event, ensure_ascii=False, default=str))


def _stream_state_event(request: dict) -> AgentResponse:
    """Build a protocol-safe no-output event to flush the SSE data path."""
    return AgentResponse(
        id=request.get("id"),
        session_id=request.get("session_id"),
    ).in_progress()


def _request_with_stable_response_id(request: dict) -> dict:
    """Ensure synthetic stream events share one response identity."""
    if request.get("id"):
        return request
    return {
        **request,
        "id": AgentResponse(session_id=request.get("session_id")).id,
    }


def _timeout_events(request: dict, timeout_seconds: float, start_sequence: int):
    """Build protocol-compatible visible timeout events."""
    seq = SequenceNumberGenerator(start=start_sequence)
    content_text = _agent_query_timeout_message(timeout_seconds)
    message = Message(
        type=MessageType.MESSAGE,
        role="assistant",
    )
    content = TextContent(
        index=0,
        msg_id=message.id,
        text=content_text,
    ).completed()
    response = AgentResponse(
        id=request.get("id"),
        session_id=request.get("session_id"),
    )

    yield seq.yield_with_sequence(message.in_progress())
    yield seq.yield_with_sequence(content)
    message.content = [content]
    yield seq.yield_with_sequence(message.completed())
    response.add_new_message(message)
    yield seq.yield_with_sequence(response.completed())


async def _cleanup_agent_process_stream(agen, next_task, reason: str) -> None:
    """Best-effort bounded cleanup for a stalled or disconnected agent stream."""
    if next_task is not None and not next_task.done():
        next_task.cancel()
        try:
            await asyncio.wait_for(next_task, _AGENT_PROCESS_CLEANUP_SECONDS)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug(
                "Agent process next chunk cleanup failed after %s",
                reason,
                exc_info=True,
            )

    try:
        await asyncio.wait_for(agen.aclose(), _AGENT_PROCESS_CLEANUP_SECONDS)
    except RuntimeError:
        # The async generator can still be closing from the cancelled __anext__.
        logger.debug("Agent process stream already closing after %s", reason)
    except Exception:
        logger.debug(
            "Agent process stream close failed after %s",
            reason,
            exc_info=True,
        )


def _safe_error_event(request: dict, start_sequence: int):
    """Build a customer-safe generic failure event without raw exception text."""
    seq = SequenceNumberGenerator(start=start_sequence)
    response = AgentResponse(
        id=request.get("id"),
        session_id=request.get("session_id"),
    )
    from agentscope_runtime.engine.schemas.agent_schemas import Error

    yield seq.yield_with_sequence(
        response.failed(
            Error(
                code="adclaw_agent_process_error",
                message=(
                    "AdClaw could not finish this request. Retry once, "
                    "or start a fresh chat if it repeats."
                ),
            ),
        ),
    )


def _customer_error_event(request: dict, code: str, message: str, start_sequence: int):
    """Build a customer-safe failure event for known hosted errors."""
    seq = SequenceNumberGenerator(start=start_sequence)
    response = AgentResponse(
        id=request.get("id"),
        session_id=request.get("session_id"),
    )
    from agentscope_runtime.engine.schemas.agent_schemas import Error

    yield seq.yield_with_sequence(
        response.failed(
            Error(
                code=code,
                message=message,
            ),
        ),
    )


async def _agent_process_sse_generator(request: dict):
    """Stream chat through an AdClaw-owned SSE watchdog.

    The upstream AgentScope route can leave clients with no terminal event when
    setup, adapter, or provider first-byte work stalls. This wrapper owns the
    `/api/agent/process` boundary: it commits the stream immediately, enforces
    a single request deadline, and emits a visible final message on timeout.
    """
    request = _request_with_stable_response_id(request)
    direct_enabled = _host_ai_direct_chat_enabled()
    timeout_seconds = _agent_process_timeout_seconds()
    if direct_enabled and timeout_seconds <= 0:
        timeout_seconds = _HOST_AI_DIRECT_DEFAULT_TIMEOUT_SECONDS
    direct_cfg = _active_host_ai_direct_config() if direct_enabled else None

    yield ": adclaw-agent-process-start\n\n"
    yield _sse_event(_stream_state_event(request))

    if direct_enabled:
        if direct_cfg is None:
            for event in _customer_error_event(
                request,
                "adclaw_host_ai_not_configured",
                (
                    "AdClaw Host AI is not ready in this workspace. Return to "
                    "the Host dashboard and open the workspace again."
                ),
                0,
            ):
                yield _sse_event(event)
            return
        last_sequence = -1
        try:
            async for event in _host_ai_direct_sse_events(
                request,
                direct_cfg,
                timeout_seconds,
            ):
                sequence_number = getattr(event, "sequence_number", None)
                if isinstance(sequence_number, int):
                    last_sequence = max(last_sequence, sequence_number)
                yield _sse_event(event)
            return
        except _HostAiDirectCustomerError as exc:
            for event in _customer_error_event(
                request,
                exc.code,
                exc.message,
                last_sequence + 1,
            ):
                yield _sse_event(event)
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Host AI direct chat failed: %s",
                type(exc).__name__,
                exc_info=False,
            )
            for event in _safe_error_event(request, last_sequence + 1):
                yield _sse_event(event)
            return

    deadline = (
        asyncio.get_running_loop().time() + timeout_seconds
        if timeout_seconds > 0
        else None
    )
    heartbeat_seconds = _AGENT_PROCESS_HEARTBEAT_SECONDS
    agen = runner.stream_query(request)
    next_task = None
    last_sequence = -1
    cleanup_scheduled = False

    try:
        while True:
            if next_task is None:
                next_task = asyncio.create_task(agen.__anext__())

            if deadline is None:
                wait_seconds = None
            else:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    cleanup_scheduled = True
                    asyncio.create_task(
                        _cleanup_agent_process_stream(
                            agen,
                            next_task,
                            "timeout",
                        ),
                    )
                    for event in _timeout_events(
                        request,
                        timeout_seconds,
                        last_sequence + 1,
                    ):
                        yield _sse_event(event)
                    return
                wait_seconds = min(heartbeat_seconds, remaining)

            done, _ = await asyncio.wait({next_task}, timeout=wait_seconds)
            if not done:
                yield ": adclaw-agent-process-heartbeat\n\n"
                yield _sse_event(_stream_state_event(request))
                continue

            try:
                chunk = next_task.result()
            except StopAsyncIteration:
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "Agent process stream failed: %s",
                    type(exc).__name__,
                    exc_info=False,
                )
                for event in _safe_error_event(request, last_sequence + 1):
                    yield _sse_event(event)
                return

            sequence_number = getattr(chunk, "sequence_number", None)
            if isinstance(sequence_number, int):
                last_sequence = max(last_sequence, sequence_number)
            yield _sse_event(chunk)
            next_task = None
    except asyncio.CancelledError:
        cleanup_scheduled = True
        asyncio.create_task(
            _cleanup_agent_process_stream(agen, next_task, "client disconnect"),
        )
        raise
    finally:
        if not cleanup_scheduled and next_task is not None and not next_task.done():
            asyncio.create_task(
                _cleanup_agent_process_stream(agen, next_task, "generator exit"),
            )


@app.post("/api/agent/process", include_in_schema=False)
async def adclaw_agent_process(request: dict):
    """Run the console chat stream with AdClaw-owned timeout semantics."""
    return StreamingResponse(
        _agent_process_sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


app.include_router(api_router, prefix="/api")

app.include_router(
    agent_app.router,
    prefix="/api/agent",
    tags=["agent"],
)

# Mount console: root static files (logo.png etc.) then assets, then SPA
# fallback.
if os.path.isdir(_CONSOLE_STATIC_DIR):
    _console_path = Path(_CONSOLE_STATIC_DIR)

    _assets_dir = _console_path / "assets"
    if _assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_assets_dir)),
            name="assets",
        )

    @app.get("/{full_path:path}")
    def _console_spa(full_path: str):
        # Serve static files from console root before SPA fallback
        if full_path and not full_path.startswith("api/"):
            static_file = _console_path / full_path
            if (
                static_file.is_file()
                and _console_path in static_file.resolve().parents
            ):
                return FileResponse(static_file)

        if _CONSOLE_INDEX and _CONSOLE_INDEX.exists():
            return FileResponse(_CONSOLE_INDEX)

        raise HTTPException(status_code=404, detail="Not Found")
