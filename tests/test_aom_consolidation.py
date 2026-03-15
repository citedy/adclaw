# -*- coding: utf-8 -*-
"""Tests for ConsolidationEngine and ConsolidationScheduler."""

import asyncio

import pytest

from adclaw.memory_agent.consolidate import ConsolidationEngine, ConsolidationScheduler
from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.models import AOMConfig
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


class TestConsolidationEngine:
    async def test_consolidation_with_related_memories(
        self, store, embedder, fake_llm_caller, config
    ):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        # Ingest similar content so they cluster together
        await ingest.ingest("SEO keyword research: shoes volume 12000", skip_llm=True)
        await ingest.ingest("SEO keyword research: sneakers volume 8000", skip_llm=True)
        await ingest.ingest("SEO keyword research: boots volume 5000", skip_llm=True)

        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        results = await engine.run_consolidation_cycle()
        # Should generate at least 1 insight
        assert len(results) >= 1
        assert results[0].insight

    async def test_skip_with_less_than_2_memories(
        self, store, embedder, fake_llm_caller, config
    ):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        await ingest.ingest("Only one memory here", skip_llm=True)

        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        results = await engine.run_consolidation_cycle()
        assert len(results) == 0

    async def test_empty_store(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        results = await engine.run_consolidation_cycle()
        assert results == []

    async def test_marks_as_consolidated(
        self, store, embedder, fake_llm_caller, config
    ):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        await ingest.ingest("Data point A for consolidation test", skip_llm=True)
        await ingest.ingest("Data point B for consolidation test", skip_llm=True)

        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        await engine.run_consolidation_cycle()

        # Second cycle should find fewer unconsolidated
        remaining = await store.get_unconsolidated_memories()
        # At least some should be marked
        initial_count = 2
        assert len(remaining) < initial_count or len(remaining) == 0

    async def test_consolidation_stored(
        self, store, embedder, fake_llm_caller, config
    ):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        await ingest.ingest("Market research finding 1", skip_llm=True)
        await ingest.ingest("Market research finding 2", skip_llm=True)

        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        await engine.run_consolidation_cycle()

        consolidations = await store.list_consolidations()
        assert len(consolidations) >= 1


class TestConsolidationScheduler:
    async def test_start_stop(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        scheduler = ConsolidationScheduler(engine, interval_minutes=1)
        await scheduler.start()
        assert scheduler._task is not None
        await scheduler.stop()
        assert scheduler._task is None
