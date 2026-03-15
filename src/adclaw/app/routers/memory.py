# -*- coding: utf-8 -*-
"""REST API for Always-On Memory Agent."""

from __future__ import annotations

import logging
from typing import Optional

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


def _get_aom(request: Request):
    aom = getattr(request.app.state, "aom_manager", None)
    if aom is None or not aom.is_running:
        raise HTTPException(
            status_code=503,
            detail="Always-On Memory is not enabled or not running",
        )
    return aom


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class MemoryCreateRequest(BaseModel):
    content: str
    source_type: str = "manual"
    source_id: str = ""
    metadata: Optional[dict] = None
    skip_llm: bool = False


class MemoryQueryRequest(BaseModel):
    question: str
    max_results: int = 10


class AOMConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    consolidation_enabled: Optional[bool] = None
    consolidation_interval_minutes: Optional[int] = None
    auto_capture_mcp: Optional[bool] = None
    auto_capture_skills: Optional[bool] = None
    auto_capture_chat: Optional[bool] = None
    file_inbox_enabled: Optional[bool] = None
    importance_threshold: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_stats(request: Request):
    aom = _get_aom(request)
    stats = await aom.store.get_stats()
    return stats


@router.get("/memories")
async def list_memories(
    request: Request,
    source_type: Optional[str] = None,
    limit: int = 50,
    min_importance: float = 0.0,
):
    aom = _get_aom(request)
    memories = await aom.store.list_memories(
        source_type=source_type,
        limit=limit,
        min_importance=min_importance,
    )
    return [m.model_dump() for m in memories]


@router.get("/memories/{memory_id}")
async def get_memory(request: Request, memory_id: str):
    aom = _get_aom(request)
    mem = await aom.store.get_memory(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    return mem.model_dump()


@router.post("/memories")
async def create_memory(request: Request, body: MemoryCreateRequest):
    aom = _get_aom(request)
    mem = await aom.ingest_agent.ingest(
        content=body.content,
        source_type=body.source_type,
        source_id=body.source_id,
        skip_llm=body.skip_llm,
        metadata=body.metadata,
    )
    return mem.model_dump()


@router.post("/memories/upload")
async def upload_file_to_memory(request: Request, file: UploadFile = File(...)):
    """Upload and ingest a file into AOM.

    Text files work in basic mode. Images/audio/video/PDF require
    multimodal_api_key to be configured.
    """
    aom = _get_aom(request)
    import tempfile

    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        mem = await aom.ingest_agent.ingest_file(
            tmp_path, source_id=file.filename or "upload"
        )
        return mem.model_dump()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/multimodal/status")
async def multimodal_status(request: Request):
    """Check if multimodal processing is available."""
    aom = _get_aom(request)
    mm = aom.multimodal
    return {
        "available": mm is not None and mm.is_available,
        "provider": mm.provider if mm else None,
        "model": mm.model if mm else None,
    }


@router.delete("/memories/{memory_id}")
async def delete_memory(request: Request, memory_id: str):
    aom = _get_aom(request)
    deleted = await aom.store.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}


@router.post("/query")
async def query_memory(request: Request, body: MemoryQueryRequest):
    aom = _get_aom(request)
    result = await aom.query_agent.query(
        question=body.question,
        max_results=body.max_results,
    )
    return result.model_dump()


@router.get("/consolidations")
async def list_consolidations(request: Request, limit: int = 50):
    aom = _get_aom(request)
    cons = await aom.store.list_consolidations(limit=limit)
    return [c.model_dump() for c in cons]


@router.post("/consolidate")
async def run_consolidation(request: Request):
    aom = _get_aom(request)
    if not aom.consolidation_engine:
        raise HTTPException(status_code=400, detail="Consolidation engine not available")
    results = await aom.consolidation_engine.run_consolidation_cycle()
    return {"insights_created": len(results)}


@router.get("/config")
async def get_config(request: Request):
    aom = _get_aom(request)
    return aom.config.model_dump()


@router.put("/config")
async def update_config(request: Request, body: AOMConfigUpdateRequest):
    aom = _get_aom(request)
    current = aom.config.model_dump()
    updates = body.model_dump(exclude_none=True)
    current.update(updates)

    from ...memory_agent.models import AOMConfig

    new_config = AOMConfig(**current)
    await aom.update_config(new_config)
    return new_config.model_dump()
