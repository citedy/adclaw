# -*- coding: utf-8 -*-
"""Tests for QueryAgent — hybrid search, RRF, synthesis."""

import pytest

from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.models import AOMConfig
from adclaw.memory_agent.query import QueryAgent, _reciprocal_rank_fusion
from adclaw.memory_agent.store import MemoryStore


@pytest.fixture
async def store():
    s = MemoryStore(":memory:", dimensions=32)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def embedder():
    return FakeEmbeddingPipeline(dimensions=32)


@pytest.fixture
def config():
    return AOMConfig(enabled=True, embedding_dimensions=32, importance_threshold=0.1)


async def _populate_store(store, embedder, fake_llm_caller, config):
    """Helper to populate store with test data."""
    ingest = IngestAgent(store, embedder, fake_llm_caller, config)
    await ingest.ingest(
        "Keyword shoes has volume 12000 and CPC $2.50",
        source_type="mcp_tool",
        source_id="ahrefs",
        skip_llm=True,
    )
    await ingest.ingest(
        "Competitor ranks #1 for shoes with DA 85",
        source_type="mcp_tool",
        source_id="ahrefs",
        skip_llm=True,
    )
    await ingest.ingest(
        "Google Ads CTR for shoes campaign: 3.2%",
        source_type="mcp_tool",
        source_id="google_ads",
        skip_llm=True,
    )
    await ingest.ingest(
        "Email open rate for newsletter: 22%",
        source_type="skill",
        source_id="sendgrid",
        skip_llm=True,
    )


class TestRRF:
    def test_rrf_merges_lists(self):
        list1 = [("a", 0.1), ("b", 0.2), ("c", 0.3)]
        list2 = [("b", 0.1), ("d", 0.2), ("a", 0.3)]
        merged = _reciprocal_rank_fusion(list1, list2)
        ids = [x[0] for x in merged]
        # Both "a" and "b" appear in both lists, should rank higher
        assert "a" in ids[:3]
        assert "b" in ids[:3]

    def test_rrf_empty_lists(self):
        assert _reciprocal_rank_fusion() == []

    def test_rrf_single_list(self):
        results = _reciprocal_rank_fusion([("x", 0.1), ("y", 0.2)])
        assert len(results) == 2


class TestQueryAgent:
    async def test_query_with_results(self, store, embedder, fake_llm_caller, config):
        await _populate_store(store, embedder, fake_llm_caller, config)
        agent = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await agent.query("What do we know about shoes?")
        assert result.answer
        assert len(result.citations) >= 1

    async def test_query_empty_store(self, store, embedder, fake_llm_caller, config):
        agent = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await agent.query("anything")
        assert "No relevant memories" in result.answer
        assert len(result.citations) == 0

    async def test_query_skip_synthesis(self, store, embedder, fake_llm_caller, config):
        await _populate_store(store, embedder, fake_llm_caller, config)
        agent = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await agent.query("shoes", skip_synthesis=True)
        assert result.answer == ""
        assert len(result.citations) >= 1

    async def test_query_max_results(self, store, embedder, fake_llm_caller, config):
        await _populate_store(store, embedder, fake_llm_caller, config)
        agent = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await agent.query("data", max_results=2, skip_synthesis=True)
        assert len(result.citations) <= 2

    async def test_query_returns_consolidations(self, store, embedder, fake_llm_caller, config):
        await _populate_store(store, embedder, fake_llm_caller, config)
        from adclaw.memory_agent.models import Consolidation

        await store.insert_consolidation(
            Consolidation(insight="Shoes market insight", memory_ids=["id1"])
        )
        agent = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await agent.query("shoes")
        assert len(result.consolidations) >= 1
