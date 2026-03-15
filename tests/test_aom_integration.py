# -*- coding: utf-8 -*-
"""Integration tests — full cycle: ingest → consolidate → query."""

import pytest

from adclaw.memory_agent.consolidate import ConsolidationEngine
from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.models import AOMConfig
from adclaw.memory_agent.query import QueryAgent
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
    return AOMConfig(
        enabled=True,
        embedding_dimensions=32,
        importance_threshold=0.1,
    )


class TestFullCycle:
    async def test_ingest_consolidate_query(
        self, store, embedder, fake_llm_caller, config
    ):
        """MCP tool results → ingest → consolidate → query — no chat needed."""
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)

        # Simulate 3 MCP tool results
        await ingest.ingest(
            '{"keyword":"buy shoes","volume":12000}',
            source_type="mcp_tool",
            source_id="ahrefs",
        )
        await ingest.ingest(
            "Competitor ranks #1 for shoes, DA 85",
            source_type="mcp_tool",
            source_id="ahrefs",
        )
        await ingest.ingest(
            "CTR for shoes ads: 3.2%",
            source_type="mcp_tool",
            source_id="google_ads",
        )

        # Verify ingest
        stats = await store.get_stats()
        assert stats["total_memories"] == 3

        # Consolidation
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        insights = await engine.run_consolidation_cycle()
        assert len(insights) >= 1

        # Query
        query = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await query.query("What do we know about shoes?")
        assert result.answer
        assert len(result.citations) >= 1

    async def test_dedup_across_sources(
        self, store, embedder, fake_llm_caller, config
    ):
        """Same content from different sources should be deduped."""
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        m1 = await ingest.ingest("Exact same content", source_type="mcp_tool")
        m2 = await ingest.ingest("Exact same content", source_type="skill")
        assert m1.id == m2.id
        stats = await store.get_stats()
        assert stats["total_memories"] == 1

    async def test_delete_and_query(
        self, store, embedder, fake_llm_caller, config
    ):
        """Deleted memories should not appear in query results."""
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        mem = await ingest.ingest(
            "This will be deleted soon for test",
            source_type="manual",
            skip_llm=True,
        )
        await store.delete_memory(mem.id, hard=False)

        query = QueryAgent(store, embedder, fake_llm_caller, config)
        result = await query.query("deleted", skip_synthesis=True)
        mem_ids = [c.memory.id for c in result.citations]
        assert mem.id not in mem_ids

    async def test_query_tool_function(
        self, store, embedder, fake_llm_caller, config
    ):
        """Test the query tool function wrapper."""
        from adclaw.agents.tools.aom_query import create_aom_query_tool

        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        await ingest.ingest(
            "Important finding about market trends for shoes",
            source_type="mcp_tool",
            source_id="analysis",
        )

        query_agent = QueryAgent(store, embedder, fake_llm_caller, config)
        tool_fn = create_aom_query_tool(query_agent)
        result = await tool_fn("shoes trends")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.slow
    async def test_bulk_ingest_1000(
        self, store, embedder, fake_llm_caller, config
    ):
        """Bulk ingest 1000 memories with skip_llm=True."""
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        items = [
            {"content": f"Bulk memory item number {i} with unique content"}
            for i in range(1000)
        ]
        results = await ingest.ingest_batch(items, skip_llm=True)
        assert len(results) == 1000
        stats = await store.get_stats()
        assert stats["total_memories"] == 1000
