# -*- coding: utf-8 -*-
"""Always-On Memory Agent (AOM) — persistent memory layer for AdClaw.

Provides SQLite + sqlite-vec vector search + FTS5 keyword search,
LLM-powered ingest/consolidation/query pipeline, and auto-capture hooks.
"""

from .models import AOMConfig, Memory, Consolidation, MemorySearchResult, QueryResult
from .store import MemoryStore
from .embeddings import EmbeddingPipeline, FakeEmbeddingPipeline
from .ingest import IngestAgent
from .consolidate import ConsolidationEngine
from .query import QueryAgent
from .manager import AOMManager
from .multimodal import MultimodalProcessor

__all__ = [
    "AOMConfig",
    "AOMManager",
    "Consolidation",
    "ConsolidationEngine",
    "EmbeddingPipeline",
    "FakeEmbeddingPipeline",
    "IngestAgent",
    "Memory",
    "MemorySearchResult",
    "MemoryStore",
    "MultimodalProcessor",
    "QueryAgent",
    "QueryResult",
]
