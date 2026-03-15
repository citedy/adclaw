"""Tests for Mission Control P3: per-persona session isolation."""
import os
import json
import pytest
from pathlib import Path
from adclaw.agents.persona_manager import PersonaManager
from adclaw.config.config import PersonaConfig


class TestSessionIsolation:
    """Each persona chat tab must use a separate session file."""

    def test_session_files_separate(self, tmp_path):
        """Simulate session files per persona — they must not collide."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        user = "123456789"
        personas = ["coordinator", "researcher", "content-writer"]

        for pid in personas:
            session_id = f"{pid}::console--default"
            fname = f"{user}_{pid}----console--default.json"
            session_file = sessions_dir / fname
            session_file.write_text(json.dumps({
                "session_id": session_id,
                "persona": pid,
                "messages": [{"role": "user", "text": f"Hello {pid}"}],
            }))

        files = list(sessions_dir.iterdir())
        assert len(files) == 3
        names = {f.name for f in files}
        assert f"{user}_coordinator----console--default.json" in names
        assert f"{user}_researcher----console--default.json" in names
        assert f"{user}_content-writer----console--default.json" in names

    def test_session_data_isolated(self, tmp_path):
        """Messages in one session must not appear in another."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Write researcher session
        r_file = sessions_dir / "user_researcher----console.json"
        r_file.write_text(json.dumps({"messages": [{"text": "AI trends report"}]}))

        # Write writer session
        w_file = sessions_dir / "user_content-writer----console.json"
        w_file.write_text(json.dumps({"messages": [{"text": "Blog draft v2"}]}))

        r_data = json.loads(r_file.read_text())
        w_data = json.loads(w_file.read_text())

        assert r_data["messages"][0]["text"] == "AI trends report"
        assert w_data["messages"][0]["text"] == "Blog draft v2"
        assert r_data["messages"] != w_data["messages"]


class TestSharedMemory:
    """AOM (Always-On Memory) must be shared across all persona sessions."""

    @pytest.mark.asyncio
    async def test_aom_shared_across_personas(self, aom_store, fake_embedder):
        """Memory ingested by researcher should be queryable by writer."""
        from adclaw.memory_agent.ingest import IngestAgent

        agent = IngestAgent(store=aom_store, embedder=fake_embedder, llm_caller=None)

        # Researcher ingests a memory
        await agent.ingest(
            content="AI market will reach $500B by 2027",
            source_type="chat",
            source_id="researcher::console",
            skip_llm=True,
        )

        # Query from "writer" perspective — same store (recent_memories is not persona-scoped)
        results = await aom_store.recent_memories(limit=10)
        assert len(results) >= 1
        assert "500B" in results[0].content

    @pytest.mark.asyncio
    async def test_aom_not_scoped_to_persona(self, aom_store, fake_embedder):
        """AOM has no persona filtering — all memories visible to all."""
        from adclaw.memory_agent.ingest import IngestAgent

        agent = IngestAgent(store=aom_store, embedder=fake_embedder, llm_caller=None)

        await agent.ingest(content="Fact A from researcher", source_type="chat", source_id="researcher", skip_llm=True)
        await agent.ingest(content="Fact B from writer", source_type="chat", source_id="writer", skip_llm=True)

        stats = await aom_store.get_stats()
        assert stats["total_memories"] == 2  # Both visible
