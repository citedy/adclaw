# -*- coding: utf-8 -*-
"""Tests for ConsolidationEngine v2 — gate logic, 4-phase, contradictions."""

import time

import pytest

from adclaw.memory_agent.consolidate import (
    ConsolidationEngine,
    ConsolidationScheduler,
    _classify_memory_color,
)
from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.models import AOMConfig, Memory, _utcnow
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
        consolidation_min_interval_seconds=0,  # no time gate for tests
        consolidation_min_new_memories=1,  # low threshold for tests
    )


# ---------------------------------------------------------------------------
# Gate Logic Tests
# ---------------------------------------------------------------------------


class TestEventGate:
    async def test_skip_when_no_new_memories(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        # No notify_new_memory() called → should_run returns False
        assert engine._should_run() is False

    async def test_pass_when_new_memories_exist(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        engine.notify_new_memory()
        assert engine._should_run() is True


class TestTimeGate:
    async def test_skip_when_too_recent(self, store, embedder, fake_llm_caller):
        config = AOMConfig(
            enabled=True,
            embedding_dimensions=32,
            consolidation_min_interval_seconds=3600,  # 1 hour
            consolidation_min_new_memories=1,
        )
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        engine.notify_new_memory()
        # Pretend last consolidation was just now
        engine._last_consolidation_ts = time.monotonic()
        assert engine._should_run() is False

    async def test_pass_when_enough_time(self, store, embedder, fake_llm_caller):
        config = AOMConfig(
            enabled=True,
            embedding_dimensions=32,
            consolidation_min_interval_seconds=1,
            consolidation_min_new_memories=1,
        )
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        engine.notify_new_memory()
        engine._last_consolidation_ts = time.monotonic() - 10  # 10s ago
        assert engine._should_run() is True


class TestCountGate:
    async def test_skip_when_too_few(self, store, embedder, fake_llm_caller):
        config = AOMConfig(
            enabled=True,
            embedding_dimensions=32,
            consolidation_min_interval_seconds=0,
            consolidation_min_new_memories=5,
        )
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        engine.notify_new_memory()  # only 1, need 5
        assert engine._should_run() is False

    async def test_pass_when_enough(self, store, embedder, fake_llm_caller):
        config = AOMConfig(
            enabled=True,
            embedding_dimensions=32,
            consolidation_min_interval_seconds=0,
            consolidation_min_new_memories=3,
        )
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        for _ in range(3):
            engine.notify_new_memory()
        assert engine._should_run() is True


# ---------------------------------------------------------------------------
# Cheap Sentiment Tests
# ---------------------------------------------------------------------------


class TestCheapSentiment:
    async def test_positive(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        assert engine._cheap_sentiment("This approach works well and is correct") is True

    async def test_negative(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        assert engine._cheap_sentiment("This method is broken and deprecated") is False

    async def test_neutral(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        assert engine._cheap_sentiment("The sky is blue today") is None


# ---------------------------------------------------------------------------
# Memory Color Classification
# ---------------------------------------------------------------------------


class TestMemoryColor:
    def test_high_importance_is_red(self):
        mem = Memory(content="important", importance=0.9)
        assert _classify_memory_color(mem) == "red"

    def test_chat_low_importance_is_green(self):
        mem = Memory(content="hello", source_type="chat", importance=0.3)
        assert _classify_memory_color(mem) == "green"

    def test_skill_is_red_regardless_of_importance(self):
        mem = Memory(content="skill result", source_type="skill", importance=0.6)
        assert _classify_memory_color(mem) == "red"

    def test_file_inbox_medium_importance_is_yellow(self):
        mem = Memory(content="uploaded doc", source_type="file_inbox", importance=0.6)
        assert _classify_memory_color(mem) == "yellow"


# ---------------------------------------------------------------------------
# Full Cycle Tests
# ---------------------------------------------------------------------------


class TestConsolidationCycle:
    async def test_full_cycle_resets_counter(self, store, embedder, fake_llm_caller, config):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        await ingest.ingest("SEO keyword research: shoes volume 12000", skip_llm=True)
        await ingest.ingest("SEO keyword research: sneakers volume 8000", skip_llm=True)
        await ingest.ingest("SEO keyword research: boots volume 5000", skip_llm=True)

        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        for _ in range(3):
            engine.notify_new_memory()

        results = await engine.run_consolidation_cycle()
        assert len(results) >= 1
        # Counter should be reset after successful cycle
        assert engine._new_memory_count == 0

    async def test_backoff_on_empty_cycle(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        engine.notify_new_memory()
        # Store is empty → orient phase returns empty
        await engine.run_consolidation_cycle()
        assert engine._backoff_multiplier > 1.0


# ---------------------------------------------------------------------------
# Contradiction Detection Tests
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    async def test_opposing_sentiment_shared_topic(self, store, embedder, config):
        """Two memories with shared topics and opposing sentiment should trigger resolution."""
        async def llm_caller(prompt: str) -> str:
            if "contradict" in prompt.lower() or "winner" in prompt.lower():
                return "WINNER: B\nREASON: B is newer and more accurate."
            return "INSIGHT: Test insight.\nIMPORTANCE: 0.7"

        engine = ConsolidationEngine(store, embedder, llm_caller, config)

        mem_a = Memory(
            content="The API endpoint is active and works correctly",
            topics=["api", "endpoint"],
            importance=0.6,
        )
        mem_b = Memory(
            content="The API endpoint is broken and deprecated",
            topics=["api", "endpoint"],
            importance=0.6,
        )
        await store.insert_memory(mem_a)
        await store.insert_memory(mem_b)

        await engine._detect_contradictions([mem_a, mem_b])

        # Loser (mem_a) should be superseded
        loser = await store.get_memory(mem_a.id)
        assert loser is not None
        assert loser.is_deleted == 1
        assert loser.superseded_by == mem_b.id

        # Winner (mem_b) should be untouched
        winner = await store.get_memory(mem_b.id)
        assert winner is not None
        assert winner.is_deleted == 0
        assert winner.superseded_by is None


class TestMarkSuperseded:
    async def test_loser_soft_deleted_winner_untouched(self, store):
        """mark_superseded should soft-delete loser and leave winner intact."""
        mem_a = Memory(content="Old fact", importance=0.5)
        mem_b = Memory(content="New fact", importance=0.5)
        await store.insert_memory(mem_a)
        await store.insert_memory(mem_b)

        await store.mark_superseded(mem_a.id, mem_b.id)

        loser = await store.get_memory(mem_a.id)
        assert loser.is_deleted == 1
        assert loser.superseded_by == mem_b.id

        winner = await store.get_memory(mem_b.id)
        assert winner.is_deleted == 0
        assert winner.superseded_by is None


class TestMarkVerified:
    async def test_timestamp_written_and_readable(self, store):
        """mark_verified should set last_verified_at that is readable back."""
        mem = Memory(content="Test memory", importance=0.5)
        await store.insert_memory(mem)
        assert (await store.get_memory(mem.id)).last_verified_at is None

        await store.mark_verified([mem.id])

        updated = await store.get_memory(mem.id)
        assert updated.last_verified_at is not None
        assert len(updated.last_verified_at) > 0


class TestCleanupOrphanConsolidations:
    async def test_delete_consolidation_with_all_deleted_sources(self, store):
        """Consolidation whose source memories are all deleted should be removed."""
        mem_a = Memory(content="Mem A", importance=0.5)
        mem_b = Memory(content="Mem B", importance=0.5)
        await store.insert_memory(mem_a)
        await store.insert_memory(mem_b)

        from adclaw.memory_agent.models import Consolidation
        cons = Consolidation(
            insight="Test insight",
            memory_ids=[mem_a.id, mem_b.id],
            importance=0.6,
        )
        await store.insert_consolidation(cons)

        # Soft-delete both source memories
        await store.delete_memory(mem_a.id, hard=False)
        await store.delete_memory(mem_b.id, hard=False)

        removed = await store.cleanup_orphan_consolidations()
        assert removed == 1

        # Verify consolidation is gone
        remaining = await store.list_consolidations(limit=100)
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# Scheduler Tests
# ---------------------------------------------------------------------------


class TestIsStale:
    async def test_recently_verified_is_not_stale(self, store, embedder, fake_llm_caller, config):
        from adclaw.memory_agent.consolidate import _is_stale
        mem = Memory(content="test", importance=0.8, last_verified_at=_utcnow())
        assert _is_stale(mem, stale_days=14) is False

    async def test_never_verified_falls_back_to_created_at(self, store, embedder, fake_llm_caller, config):
        from adclaw.memory_agent.consolidate import _is_stale
        # created_at is just now → not stale
        mem = Memory(content="test", importance=0.8)
        assert _is_stale(mem, stale_days=14) is False

    async def test_malformed_date_returns_false(self, store, embedder, fake_llm_caller, config):
        from adclaw.memory_agent.consolidate import _is_stale
        mem = Memory(content="test", importance=0.8, last_verified_at="not-a-date")
        assert _is_stale(mem, stale_days=14) is False


class TestContradictionNoSharedTopics:
    async def test_no_shared_topics_skips_resolution(self, store, embedder, config):
        """Memories with no topic overlap should not trigger contradiction."""
        call_count = 0
        async def counting_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            return "WINNER: A"

        engine = ConsolidationEngine(store, embedder, counting_llm, config)
        mem_a = Memory(content="API is active", topics=["api"], importance=0.6)
        mem_b = Memory(content="Database is broken", topics=["database"], importance=0.6)
        await store.insert_memory(mem_a)
        await store.insert_memory(mem_b)

        await engine._detect_contradictions([mem_a, mem_b])
        # LLM should NOT have been called (no shared topics)
        assert call_count == 0


class TestResolveContradictionUnparseable:
    async def test_unparseable_llm_skips_resolution(self, store, embedder, config):
        """If LLM returns garbage, neither memory should be superseded."""
        async def garbage_llm(prompt: str) -> str:
            return "I cannot determine which is correct. Both have merit."

        engine = ConsolidationEngine(store, embedder, garbage_llm, config)
        mem_a = Memory(content="API works", topics=["api"], importance=0.6)
        mem_b = Memory(content="API broken", topics=["api"], importance=0.6)
        await store.insert_memory(mem_a)
        await store.insert_memory(mem_b)

        await engine._resolve_contradiction(mem_a, mem_b)

        # Neither should be superseded
        a = await store.get_memory(mem_a.id)
        b = await store.get_memory(mem_b.id)
        assert a.is_deleted == 0
        assert b.is_deleted == 0


class TestMigrateV2Idempotent:
    async def test_double_initialize(self):
        """Calling initialize() twice should not crash (migration idempotent)."""
        s = MemoryStore(":memory:", dimensions=32)
        await s.initialize()
        await s.initialize()  # second call — migrations should be no-op
        # Verify new columns exist
        mem = Memory(content="test", importance=0.5)
        await s.insert_memory(mem)
        loaded = await s.get_memory(mem.id)
        assert loaded.last_verified_at is None
        assert loaded.superseded_by is None
        await s.close()


class TestCountMemories:
    async def test_count_excludes_deleted(self, store):
        mem_a = Memory(content="A", importance=0.5)
        mem_b = Memory(content="B", importance=0.5)
        await store.insert_memory(mem_a)
        await store.insert_memory(mem_b)
        assert await store.count_memories() == 2
        await store.delete_memory(mem_a.id, hard=False)
        assert await store.count_memories() == 1
        assert await store.count_memories(include_deleted=True) == 2


class TestIngestCallsNotify:
    async def test_callback_fired_on_ingest(self, store, embedder, fake_llm_caller, config):
        """IngestAgent._on_memory_inserted fires after successful insert."""
        from adclaw.memory_agent.ingest import IngestAgent
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        called = []
        ingest._on_memory_inserted = lambda: called.append(1)
        await ingest.ingest("Test memory for callback", skip_llm=True)
        assert len(called) == 1


# ---------------------------------------------------------------------------
# Scheduler Tests
# ---------------------------------------------------------------------------


class TestSchedulerIdempotent:
    async def test_start_idempotent(self, store, embedder, fake_llm_caller, config):
        engine = ConsolidationEngine(store, embedder, fake_llm_caller, config)
        scheduler = ConsolidationScheduler(engine, interval_minutes=60)
        await scheduler.start()
        task1 = scheduler._task
        await scheduler.start()  # second call should be no-op
        assert scheduler._task is task1
        await scheduler.stop()
