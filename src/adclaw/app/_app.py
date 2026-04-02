# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,unused-argument
import asyncio
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from agentscope_runtime.engine.app import AgentApp

from .runner import AgentRunner
from ..config import (  # pylint: disable=no-name-in-module
    load_config,
    update_last_dispatch,
    ConfigWatcher,
)
from ..config.utils import get_jobs_path, get_chats_path, get_config_path
from ..constant import DOCS_ENABLED, LOG_LEVEL_ENV, CORS_ORIGINS
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


@asynccontextmanager
async def lifespan(app: FastAPI):  # pylint: disable=too-many-statements
    await runner.start()

    # --- MCP client manager init (independent module, hot-reloadable) ---
    config = load_config()
    mcp_manager = MCPClientManager()
    if hasattr(config, "mcp"):
        try:
            await mcp_manager.init_from_config(config.mcp)
            runner.set_mcp_manager(mcp_manager)
            logger.debug("MCP client manager initialized")
        except Exception:
            logger.exception("Failed to initialize MCP manager")

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
    if hasattr(config, "mcp"):
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
    from .watchdog import AgentWatchdog
    watchdog = AgentWatchdog(runner=runner, check_interval=60, max_restarts=5)
    watchdog_task = asyncio.create_task(watchdog.start())
    app.state.watchdog = watchdog

    try:
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
