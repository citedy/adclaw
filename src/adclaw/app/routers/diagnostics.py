# -*- coding: utf-8 -*-
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from ...providers.store import load_providers_json

logger = logging.getLogger(__name__)

_start_time = time.time()

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SubsystemStatus(BaseModel):
    status: str
    detail: Any = None


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    subsystems: Dict[str, SubsystemStatus]


class ErrorEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    traceback: Optional[str] = None


class ErrorsResponse(BaseModel):
    errors: List[ErrorEntry]
    total: int


class RestartResponse(BaseModel):
    restarted: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /diagnostics/health
# ---------------------------------------------------------------------------

_ERROR_LOG = Path("/var/log/app.err.log")
_LINE_RE = re.compile(
    r"^(ERROR|WARNING|CRITICAL)\s+.*?\|\s*"
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*(.*)"
)
_TB_RE = re.compile(r"^(Traceback |  File |    |\w+Error:)")


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    subsystems: Dict[str, SubsystemStatus] = {}

    # --- LLM ---
    try:
        data = load_providers_json()
        if data.active_llm.provider_id:
            subsystems["llm"] = SubsystemStatus(
                status="ok",
                detail={
                    "provider_id": data.active_llm.provider_id,
                    "model": data.active_llm.model,
                },
            )
        else:
            subsystems["llm"] = SubsystemStatus(
                status="error", detail="No active LLM configured"
            )
    except Exception as exc:
        subsystems["llm"] = SubsystemStatus(status="error", detail=str(exc))

    # --- Channels ---
    try:
        channels = request.app.state.channel_manager.channels
        names = [getattr(ch, "channel", getattr(ch, "name", "?")) for ch in channels]
        st = "ok" if len(channels) > 0 else "warning"
        subsystems["channels"] = SubsystemStatus(
            status=st, detail={"count": len(channels), "names": names}
        )
    except Exception as exc:
        subsystems["channels"] = SubsystemStatus(status="error", detail=str(exc))

    # --- MCP ---
    try:
        clients = request.app.state.mcp_manager._clients
        subsystems["mcp"] = SubsystemStatus(
            status="ok",
            detail={"count": len(clients), "keys": list(clients.keys())},
        )
    except Exception as exc:
        subsystems["mcp"] = SubsystemStatus(status="error", detail=str(exc))

    # --- Crons ---
    try:
        jobs = request.app.state.cron_manager._scheduler.get_jobs()
        subsystems["crons"] = SubsystemStatus(
            status="ok", detail={"count": len(jobs)}
        )
    except Exception as exc:
        subsystems["crons"] = SubsystemStatus(status="error", detail=str(exc))

    # --- AOM ---
    try:
        aom = request.app.state.aom_manager
        if aom is None:
            subsystems["aom"] = SubsystemStatus(
                status="ok", detail="Disabled"
            )
        else:
            subsystems["aom"] = SubsystemStatus(
                status="ok", detail="Enabled"
            )
    except Exception as exc:
        subsystems["aom"] = SubsystemStatus(status="error", detail=str(exc))

    # --- Watchdog ---
    wd = getattr(request.app.state, "watchdog", None)
    if wd:
        wd_status = wd.get_status()
        subsystems["watchdog"] = SubsystemStatus(
            status="ok" if wd_status["healthy"] else "warning",
            detail={
                "restarts": wd_status["restart_count"],
                "max_restarts": wd_status["max_restarts"],
            },
        )

    # --- Overall ---
    statuses = {s.status for s in subsystems.values()}
    if "error" in statuses:
        overall = "degraded"
    elif all(s.status == "ok" for s in subsystems.values()):
        overall = "healthy"
    else:
        overall = "healthy"

    return HealthResponse(
        status=overall,
        uptime_seconds=round(time.time() - _start_time, 2),
        subsystems=subsystems,
    )


# ---------------------------------------------------------------------------
# GET /diagnostics/errors
# ---------------------------------------------------------------------------


@router.get("/errors", response_model=ErrorsResponse)
async def errors(limit: int = Query(50, ge=1, le=1000)) -> ErrorsResponse:
    entries: List[ErrorEntry] = []

    if not _ERROR_LOG.exists():
        return ErrorsResponse(errors=[], total=0)

    try:
        lines = _ERROR_LOG.read_text(errors="replace").splitlines()
    except Exception:
        return ErrorsResponse(errors=[], total=0)

    current: Optional[ErrorEntry] = None
    tb_lines: List[str] = []

    def _flush():
        nonlocal current, tb_lines
        if current is not None:
            if tb_lines:
                current.traceback = "\n".join(tb_lines)
            entries.append(current)
            current = None
            tb_lines = []

    for line in lines:
        m = _LINE_RE.match(line)
        if m:
            _flush()
            current = ErrorEntry(
                level=m.group(1),
                timestamp=m.group(2),
                message=m.group(3),
            )
        elif current is not None and _TB_RE.match(line):
            tb_lines.append(line)

    _flush()

    total = len(entries)
    return ErrorsResponse(errors=entries[-limit:], total=total)


# ---------------------------------------------------------------------------
# POST /diagnostics/restart
# ---------------------------------------------------------------------------


@router.post("/restart", response_model=RestartResponse)
async def restart(request: Request) -> RestartResponse:
    try:
        runner = request.app.state.runner
        if runner.memory_manager is not None:
            await runner.memory_manager.close()
            runner.memory_manager = None
        await runner.init_handler()
        return RestartResponse(restarted=True)
    except Exception as exc:
        logger.exception("Failed to restart runner")
        return RestartResponse(restarted=False, error=str(exc))
