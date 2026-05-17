from types import SimpleNamespace

import pytest

from adclaw.memory_agent.shared_persona import (
    build_shared_persona_memory_context,
    capture_chat_memory,
)
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.models import AOMConfig, Memory


class SpyEmbedder:
    async def embed(self, _text):
        raise AssertionError("embedding should be skipped on chat capture")


class FakeStore:
    def __init__(self):
        self.memories = []

    async def recent_memories(self, limit=100):
        return list(reversed(self.memories))[:limit]

    async def insert_memory(self, memory, embedding=None):
        self.memories.append(memory)
        return memory

    async def get_stats(self):
        return {
            "total_memories": len(self.memories),
            "with_embeddings": 0,
        }


async def fake_llm_caller(_prompt):
    return '{"entities": [], "topics": [], "importance": 0.7}'


@pytest.mark.asyncio
async def test_chat_capture_skips_embedding():
    store = FakeStore()
    ingest = IngestAgent(
        store=store,
        embedder=SpyEmbedder(),
        llm_caller=fake_llm_caller,
        config=AOMConfig(enabled=True),
    )

    memory = await ingest.ingest(
        content="User asked: hi\nresearcher answered: shared fact",
        source_type="chat",
        source_id="u:s:researcher",
        skip_llm=True,
        skip_embedding=True,
        metadata={
            "user_id": "u",
            "base_session_id": "s",
            "persona_id": "researcher",
        },
    )

    assert memory.source_type == "chat"
    stats = await store.get_stats()
    assert stats["total_memories"] == 1
    assert stats["with_embeddings"] == 0


@pytest.mark.asyncio
async def test_shared_context_includes_other_personas_same_user():
    store = FakeStore()
    store.memories.append(
        Memory(
            content="User asked: trend\nresearcher answered: Keep token CROSS-123.",
            source_type="chat",
            source_id="u:s:researcher",
            metadata={
                "user_id": "u",
                "base_session_id": "s",
                "persona_id": "researcher",
            },
        )
    )
    store.memories.append(
        Memory(
            content="User asked: private\nresearcher answered: OTHER-USER.",
            source_type="chat",
            source_id="other:s:researcher",
            metadata={
                "user_id": "other",
                "base_session_id": "s",
                "persona_id": "researcher",
            },
        )
    )

    section = await build_shared_persona_memory_context(
        SimpleNamespace(
            is_running=True,
            store=store,
            config=AOMConfig(enabled=True, auto_capture_chat=True),
        ),
        base_session_id="s",
        user_id="u",
        current_persona_id="content-writer",
    )

    assert "## Shared Persona Memory" in section
    assert "researcher" in section
    assert "CROSS-123" in section
    assert "OTHER-USER" not in section


@pytest.mark.asyncio
async def test_capture_chat_memory_persists_to_shared_aom():
    store = FakeStore()
    ingest = IngestAgent(
        store=store,
        embedder=SpyEmbedder(),
        llm_caller=fake_llm_caller,
        config=AOMConfig(enabled=True),
    )
    await capture_chat_memory(
        SimpleNamespace(
            is_running=True,
            ingest_agent=ingest,
            config=AOMConfig(enabled=True, auto_capture_chat=True),
        ),
        base_session_id="s",
        scoped_session_id="researcher::s",
        user_id="u",
        channel="console",
        persona_id="researcher",
        user_text="remember visible shared phrase",
        assistant_text="CROSS-PERSONA-SMOKE-9261",
    )

    memories = await store.recent_memories(limit=10)
    assert len(memories) == 1
    assert memories[0].source_type == "chat"
    assert memories[0].metadata["persona_id"] == "researcher"
    assert "CROSS-PERSONA-SMOKE-9261" in memories[0].content
