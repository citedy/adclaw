# -*- coding: utf-8 -*-
"""Tests for 1B bridge: CachedPromptBuilder integration in ReActAgent."""

from dataclasses import dataclass

import pytest

from adclaw.agents.prompt import (
    CachedPromptBuilder,
    DynamicContext,
    PersonaPromptPool,
)


@dataclass
class FakePersona:
    id: str = "writer"
    name: str = "Writer"
    soul_md: str = "I write marketing content."


@pytest.fixture
def working_dir(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Agent instructions for marketing.")
    (tmp_path / "SOUL.md").write_text("Core identity: helpful marketing assistant.")
    return tmp_path


# ---------------------------------------------------------------------------
# Integration: CachedPromptBuilder used like ReActAgent does
# ---------------------------------------------------------------------------


class TestPromptBridgeIntegration:
    """Tests that mirror how ReActAgent uses CachedPromptBuilder."""

    def test_build_with_env_and_team(self, working_dir):
        """ReActAgent._build_sys_prompt builds with env_context + team_summary."""
        builder = CachedPromptBuilder(working_dir=working_dir)
        dynamic = DynamicContext(
            env_context="Platform: linux\nShell: bash",
            team_summary="Team has 3 agents: researcher, writer, SEO.",
        )
        prompt = builder.build(dynamic=dynamic)
        assert "Agent instructions" in prompt
        assert "Core identity" in prompt
        assert "Platform: linux" in prompt
        assert "# Team Summary" in prompt
        assert "3 agents" in prompt

    def test_rebuild_reuses_static(self, working_dir):
        """rebuild_sys_prompt should reuse cached static, only rebuild dynamic."""
        builder = CachedPromptBuilder(working_dir=working_dir)

        # First build
        d1 = DynamicContext(env_context="env1")
        p1 = builder.build(dynamic=d1)

        # Second build with different dynamic — static should be cached
        d2 = DynamicContext(env_context="env2")
        p2 = builder.build(dynamic=d2)

        assert "env1" in p1
        assert "env2" in p2
        # Static parts identical in both builds
        assert "Agent instructions" in p1
        assert "Agent instructions" in p2

    def test_persona_switch(self, working_dir):
        """Switching persona should rebuild static with new soul_md."""
        pool = PersonaPromptPool(working_dir=working_dir)

        b1 = pool.get()
        p1 = b1.static_prompt
        assert "Core identity" in p1

        persona = FakePersona()
        b2 = pool.get(persona)
        p2 = b2.static_prompt
        assert "I write marketing content." in p2
        assert "# SOUL.md (Writer)" in p2

        # Different builders
        assert b1 is not b2

    def test_file_change_invalidates(self, working_dir):
        """When AGENTS.md changes, next build should reflect new content."""
        builder = CachedPromptBuilder(working_dir=working_dir)
        p1 = builder.static_prompt
        assert "Agent instructions for marketing" in p1

        # Change file
        (working_dir / "AGENTS.md").write_text("Updated agent instructions for SEO.")
        builder.invalidate()
        p2 = builder.static_prompt
        assert "Updated agent instructions for SEO" in p2

    def test_dynamic_context_empty(self, working_dir):
        """With no dynamic context, build returns just static."""
        builder = CachedPromptBuilder(working_dir=working_dir)
        assert builder.build() == builder.static_prompt

    def test_dynamic_context_aom_tier(self, working_dir):
        """AOM tier content should appear in prompt."""
        builder = CachedPromptBuilder(working_dir=working_dir)
        dynamic = DynamicContext(
            aom_tier="User prefers formal tone. Never use emojis.",
            aom_tier_name="L1",
        )
        prompt = builder.build(dynamic=dynamic)
        assert "# Memory Context (L1)" in prompt
        assert "formal tone" in prompt


# ---------------------------------------------------------------------------
# ReActAgent mock: verify the wiring works
# ---------------------------------------------------------------------------


class TestReActAgentWiring:
    """Verify the import paths and class attributes exist."""

    def test_prompt_imports_available(self):
        """All v2 prompt classes should be importable."""
        from adclaw.agents.prompt import (  # noqa: F401
            CachedPromptBuilder,
            DynamicContext,
            PersonaPromptPool,
            select_memory_tier,
        )

    def test_react_agent_imports_v2(self):
        """ReActAgent should import the v2 prompt classes."""
        import adclaw.agents.react_agent as mod
        # Check that the module imported the new classes
        assert hasattr(mod, "CachedPromptBuilder")
        assert hasattr(mod, "DynamicContext")
        assert hasattr(mod, "PersonaPromptPool")
