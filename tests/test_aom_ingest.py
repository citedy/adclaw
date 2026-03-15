# -*- coding: utf-8 -*-
"""Tests for IngestAgent, AOMCaptureHook, FileInboxWatcher."""

import tempfile
from pathlib import Path

import pytest

from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.store import MemoryStore
from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.models import AOMConfig
from adclaw.agents.hooks.aom_capture import AOMCaptureHook
from adclaw.memory_agent.file_inbox import FileInboxWatcher


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
    return AOMConfig(enabled=True, embedding_dimensions=32, importance_threshold=0.3)


class TestIngestAgent:
    async def test_single_ingest(self, store, embedder, fake_llm_caller, config):
        agent = IngestAgent(store, embedder, fake_llm_caller, config)
        mem = await agent.ingest("Test SEO data", source_type="mcp_tool", source_id="ahrefs")
        assert mem.content == "Test SEO data"
        assert mem.source_type == "mcp_tool"
        assert "test_entity" in mem.entities

    async def test_ingest_skip_llm(self, store, embedder, fake_llm_caller, config):
        agent = IngestAgent(store, embedder, fake_llm_caller, config)
        mem = await agent.ingest("Raw data", skip_llm=True)
        assert mem.entities == []
        assert mem.topics == []

    async def test_ingest_dedup(self, store, embedder, fake_llm_caller, config):
        agent = IngestAgent(store, embedder, fake_llm_caller, config)
        m1 = await agent.ingest("Duplicate content")
        m2 = await agent.ingest("Duplicate content")
        assert m1.id == m2.id

    async def test_ingest_empty_raises(self, store, embedder, fake_llm_caller, config):
        agent = IngestAgent(store, embedder, fake_llm_caller, config)
        with pytest.raises(ValueError, match="Empty"):
            await agent.ingest("")

    async def test_batch_ingest(self, store, embedder, fake_llm_caller, config):
        agent = IngestAgent(store, embedder, fake_llm_caller, config)
        items = [
            {"content": "Item 1", "source_type": "mcp_tool"},
            {"content": "Item 2", "source_type": "skill"},
            {"content": "Item 3"},
        ]
        results = await agent.ingest_batch(items, skip_llm=True)
        assert len(results) == 3
        stats = await store.get_stats()
        assert stats["total_memories"] == 3

    async def test_ingest_with_metadata(self, store, embedder, fake_llm_caller, config):
        agent = IngestAgent(store, embedder, fake_llm_caller, config)
        mem = await agent.ingest(
            "Data with meta",
            metadata={"tool_version": "2.0"},
            skip_llm=True,
        )
        assert mem.metadata["tool_version"] == "2.0"

    async def test_importance_threshold(self, store, embedder, config):
        async def low_importance_llm(prompt):
            return '{"entities": [], "topics": [], "importance": 0.1}'

        agent = IngestAgent(store, embedder, low_importance_llm, config)
        mem = await agent.ingest("Low importance item")
        assert mem.importance >= config.importance_threshold


class TestAOMCaptureHook:
    async def test_capture_result(self, store, embedder, fake_llm_caller, config):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        hook = AOMCaptureHook(ingest_agent=ingest)
        await hook.on_tool_result("ahrefs_keywords", "Keyword: shoes, volume: 12000")
        items = await store.list_memories()
        assert len(items) == 1
        assert items[0].source_id == "ahrefs_keywords"

    async def test_skip_short_results(self, store, embedder, fake_llm_caller, config):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)
        hook = AOMCaptureHook(ingest_agent=ingest)
        await hook.on_tool_result("tool", "ok")  # too short
        items = await store.list_memories()
        assert len(items) == 0


class TestFileInboxWatcher:
    async def test_scan_inbox(self, store, embedder, fake_llm_caller, config):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)

        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir) / "inbox"
            inbox.mkdir()
            (inbox / "notes.txt").write_text("Important SEO findings for Q1")
            (inbox / "data.md").write_text("# Competitor Analysis\nDA: 85")

            watcher = FileInboxWatcher(
                inbox_dir=inbox,
                ingest_agent=ingest,
                store=store,
            )
            await watcher._scan_inbox()

            items = await store.list_memories()
            assert len(items) == 2

    async def test_skip_already_processed(self, store, embedder, fake_llm_caller, config):
        ingest = IngestAgent(store, embedder, fake_llm_caller, config)

        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir) / "inbox"
            inbox.mkdir()
            (inbox / "notes.txt").write_text("Some content here for testing")

            watcher = FileInboxWatcher(
                inbox_dir=inbox,
                ingest_agent=ingest,
                store=store,
            )
            await watcher._scan_inbox()
            count1 = (await store.get_stats())["total_memories"]

            # Second scan should not re-ingest
            await watcher._scan_inbox()
            count2 = (await store.get_stats())["total_memories"]
            assert count1 == count2
