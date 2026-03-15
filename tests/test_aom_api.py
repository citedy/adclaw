# -*- coding: utf-8 -*-
"""Tests for AOM REST API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adclaw.app.routers.memory import router
from adclaw.memory_agent.models import AOMConfig, Consolidation, Memory, QueryResult, MemorySearchResult


def _make_app(aom_manager=None):
    """Create test app with optional AOM manager."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.aom_manager = aom_manager
    return app


def _fake_aom_manager():
    """Create a fake AOM manager with mocked components."""
    mgr = MagicMock()
    mgr.is_running = True
    mgr.config = AOMConfig(enabled=True, embedding_dimensions=32)

    # Mock store
    mgr.store = AsyncMock()
    mgr.store.get_stats = AsyncMock(return_value={
        "total_memories": 5,
        "with_embeddings": 5,
        "consolidations": 1,
        "by_source": {"mcp_tool": 3, "skill": 2},
    })
    mgr.store.list_memories = AsyncMock(return_value=[
        Memory(content="Test mem", source_type="mcp_tool"),
    ])
    mgr.store.get_memory = AsyncMock(return_value=Memory(
        id="test-id", content="Test", source_type="manual"
    ))
    mgr.store.delete_memory = AsyncMock(return_value=True)
    mgr.store.list_consolidations = AsyncMock(return_value=[
        Consolidation(insight="Test insight", memory_ids=["id1"]),
    ])

    # Mock ingest
    mgr.ingest_agent = AsyncMock()
    mgr.ingest_agent.ingest = AsyncMock(return_value=Memory(
        content="New mem", source_type="manual"
    ))

    # Mock query
    mgr.query_agent = AsyncMock()
    mgr.query_agent.query = AsyncMock(return_value=QueryResult(
        answer="Test answer",
        citations=[MemorySearchResult(
            memory=Memory(content="Cited", source_type="mcp_tool"),
            score=0.9,
        )],
    ))

    # Mock consolidation
    mgr.consolidation_engine = AsyncMock()
    mgr.consolidation_engine.run_consolidation_cycle = AsyncMock(return_value=[
        Consolidation(insight="New insight", memory_ids=["a"]),
    ])

    mgr.update_config = AsyncMock()
    return mgr


class TestAOMDisabled:
    def test_stats_returns_503(self):
        app = _make_app(aom_manager=None)
        client = TestClient(app)
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 503

    def test_not_running_returns_503(self):
        mgr = MagicMock()
        mgr.is_running = False
        app = _make_app(aom_manager=mgr)
        client = TestClient(app)
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 503


class TestAOMEndpoints:
    @pytest.fixture
    def client(self):
        mgr = _fake_aom_manager()
        app = _make_app(aom_manager=mgr)
        return TestClient(app)

    def test_get_stats(self, client):
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_memories"] == 5

    def test_list_memories(self, client):
        resp = client.get("/api/memory/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_get_memory(self, client):
        resp = client.get("/api/memory/memories/test-id")
        assert resp.status_code == 200
        assert resp.json()["id"] == "test-id"

    def test_create_memory(self, client):
        resp = client.post(
            "/api/memory/memories",
            json={"content": "New memory content"},
        )
        assert resp.status_code == 200

    def test_delete_memory(self, client):
        resp = client.delete("/api/memory/memories/test-id")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_query_memory(self, client):
        resp = client.post(
            "/api/memory/query",
            json={"question": "What about shoes?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Test answer"
        assert len(data["citations"]) == 1

    def test_list_consolidations(self, client):
        resp = client.get("/api/memory/consolidations")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_run_consolidation(self, client):
        resp = client.post("/api/memory/consolidate")
        assert resp.status_code == 200
        assert resp.json()["insights_created"] == 1

    def test_get_config(self, client):
        resp = client.get("/api/memory/config")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_update_config(self, client):
        resp = client.put(
            "/api/memory/config",
            json={"consolidation_enabled": False},
        )
        assert resp.status_code == 200
