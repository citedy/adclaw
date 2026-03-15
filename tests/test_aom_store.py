# -*- coding: utf-8 -*-
"""Tests for MemoryStore — CRUD, vector search, FTS5, dedup, stats."""

import pytest

from adclaw.memory_agent.models import Consolidation, Memory
from adclaw.memory_agent.store import MemoryStore


@pytest.fixture
async def store():
    s = MemoryStore(":memory:", dimensions=4)
    await s.initialize()
    yield s
    await s.close()


class TestMemoryCRUD:
    async def test_insert_and_get(self, store):
        mem = Memory(content="Test content", source_type="manual")
        result = await store.insert_memory(mem)
        assert result.id == mem.id

        fetched = await store.get_memory(mem.id)
        assert fetched is not None
        assert fetched.content == "Test content"

    async def test_list_memories(self, store):
        for i in range(5):
            await store.insert_memory(
                Memory(content=f"Memory {i}", source_type="mcp_tool")
            )
        items = await store.list_memories(limit=3)
        assert len(items) == 3

    async def test_list_by_source_type(self, store):
        await store.insert_memory(Memory(content="A", source_type="mcp_tool"))
        await store.insert_memory(Memory(content="B", source_type="skill"))
        items = await store.list_memories(source_type="skill")
        assert len(items) == 1
        assert items[0].source_type == "skill"

    async def test_soft_delete(self, store):
        mem = Memory(content="To delete", source_type="manual")
        await store.insert_memory(mem)
        deleted = await store.delete_memory(mem.id, hard=False)
        assert deleted is True

        fetched = await store.get_memory(mem.id)
        assert fetched is not None
        assert fetched.is_deleted == 1

        items = await store.list_memories()
        assert len(items) == 0  # soft-deleted excluded

    async def test_hard_delete(self, store):
        mem = Memory(content="Hard delete", source_type="manual")
        await store.insert_memory(mem)
        await store.delete_memory(mem.id, hard=True)
        assert await store.get_memory(mem.id) is None

    async def test_dedup_by_content_hash(self, store):
        mem1 = Memory(content="Same content", source_type="manual")
        mem2 = Memory(content="Same content", source_type="mcp_tool")
        r1 = await store.insert_memory(mem1)
        r2 = await store.insert_memory(mem2)
        assert r1.id == r2.id  # dedup returns existing

    async def test_get_nonexistent(self, store):
        assert await store.get_memory("nonexistent-id") is None

    async def test_delete_nonexistent(self, store):
        assert await store.delete_memory("nonexistent-id") is False


class TestVectorSearch:
    async def test_vector_search_returns_sorted(self, store):
        # Insert memories with known embeddings
        m1 = Memory(content="alpha", source_type="manual")
        m2 = Memory(content="beta", source_type="manual")
        m3 = Memory(content="gamma", source_type="manual")

        await store.insert_memory(m1, embedding=[1.0, 0.0, 0.0, 0.0])
        await store.insert_memory(m2, embedding=[0.0, 1.0, 0.0, 0.0])
        await store.insert_memory(m3, embedding=[0.9, 0.1, 0.0, 0.0])

        # Query close to m1 and m3
        results = await store.vector_search([1.0, 0.0, 0.0, 0.0], limit=3)
        assert len(results) >= 2
        ids = [r[0] for r in results]
        # m1 should be closest (or m3 close to it)
        assert m1.id in ids

    async def test_vector_search_empty_store(self, store):
        results = await store.vector_search([1.0, 0.0, 0.0, 0.0], limit=5)
        assert results == []


class TestKeywordSearch:
    async def test_keyword_search(self, store):
        await store.insert_memory(
            Memory(content="SEO keyword research for shoes", source_type="mcp_tool")
        )
        await store.insert_memory(
            Memory(content="Google Ads campaign budget", source_type="mcp_tool")
        )

        results = await store.keyword_search("shoes", limit=5)
        assert len(results) >= 1


class TestConsolidations:
    async def test_insert_and_list(self, store):
        c = Consolidation(
            insight="Test insight",
            memory_ids=["id1", "id2"],
            importance=0.8,
        )
        await store.insert_consolidation(c)
        items = await store.list_consolidations()
        assert len(items) == 1
        assert items[0].insight == "Test insight"


class TestStats:
    async def test_get_stats(self, store):
        await store.insert_memory(Memory(content="A", source_type="mcp_tool"))
        await store.insert_memory(Memory(content="B", source_type="skill"))
        stats = await store.get_stats()
        assert stats["total_memories"] == 2
        assert stats["by_source"]["mcp_tool"] == 1
        assert stats["by_source"]["skill"] == 1


class TestProcessedFiles:
    async def test_file_tracking(self, store):
        assert not await store.is_file_processed("/test/file.txt")
        await store.mark_file_processed("/test/file.txt")
        assert await store.is_file_processed("/test/file.txt")
