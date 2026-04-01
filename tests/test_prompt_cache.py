# -*- coding: utf-8 -*-
"""Tests for CachedPromptBuilder, DynamicContext, PersonaPromptPool."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from adclaw.agents.prompt import (
    DEFAULT_SYS_PROMPT,
    CachedPromptBuilder,
    CachedSection,
    DynamicContext,
    PersonaPromptPool,
    select_memory_tier,
)


@dataclass
class FakePersona:
    id: str = "writer"
    name: str = "Writer"
    soul_md: str = "I write content."


@pytest.fixture
def working_dir(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Agent instructions here.")
    (tmp_path / "SOUL.md").write_text("Soul identity here.")
    return tmp_path


# ---------------------------------------------------------------------------
# CachedSection Tests
# ---------------------------------------------------------------------------


class TestCachedSection:
    def test_load_reads_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello world")
        section = CachedSection(path=f)
        content = section.load()
        assert content == "hello world"
        assert section.content_hash != ""

    def test_cache_hit_on_unchanged(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        section = CachedSection(path=f)
        section.load()
        hash1 = section.content_hash
        # Load again — should use cache
        section.load(force=True)
        assert section.content_hash == hash1

    def test_cache_miss_on_change(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        section = CachedSection(path=f)
        section.load()
        hash1 = section.content_hash
        # Change file
        f.write_text("world")
        section.load(force=True)
        assert section.content_hash != hash1
        assert section.content == "world"

    def test_missing_file_returns_empty(self, tmp_path):
        section = CachedSection(path=tmp_path / "nonexistent.md")
        assert section.load() == ""

    def test_strips_yaml_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: test\n---\nActual content")
        section = CachedSection(path=f)
        assert section.load() == "Actual content"


# ---------------------------------------------------------------------------
# DynamicContext Tests
# ---------------------------------------------------------------------------


class TestDynamicContext:
    def test_empty_renders_empty(self):
        ctx = DynamicContext()
        assert ctx.render() == ""

    def test_env_only(self):
        ctx = DynamicContext(env_context="Platform: linux")
        assert ctx.render() == "Platform: linux"

    def test_all_fields(self):
        ctx = DynamicContext(
            env_context="env",
            aom_tier="memory data",
            aom_tier_name="L2",
            active_tools="tool1, tool2",
            team_summary="team info",
        )
        rendered = ctx.render()
        assert "env" in rendered
        assert "# Memory Context (L2)" in rendered
        assert "memory data" in rendered
        assert "# Active Tools" in rendered
        assert "# Team Summary" in rendered

    def test_team_summary_gets_header(self):
        ctx = DynamicContext(team_summary="Some team info")
        assert "# Team Summary" in ctx.render()


# ---------------------------------------------------------------------------
# CachedPromptBuilder Tests
# ---------------------------------------------------------------------------


class TestCachedPromptBuilder:
    def test_builds_static_from_files(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        prompt = builder.static_prompt
        assert "Agent instructions here." in prompt
        assert "Soul identity here." in prompt
        assert "# AGENTS.md" in prompt

    def test_static_cache_hit(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        p1 = builder.static_prompt
        p2 = builder.static_prompt
        assert p1 is p2  # same object = cache hit

    def test_static_invalidation_on_file_change(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        p1 = builder.static_prompt
        # Change file
        (working_dir / "AGENTS.md").write_text("New instructions.")
        builder.invalidate()
        p2 = builder.static_prompt
        assert p1 != p2
        assert "New instructions." in p2

    def test_build_with_dynamic(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        dynamic = DynamicContext(env_context="Platform: linux")
        prompt = builder.build(dynamic=dynamic)
        assert "Agent instructions" in prompt
        assert "Platform: linux" in prompt

    def test_build_without_dynamic(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        assert builder.build() == builder.static_prompt

    def test_persona_override(self, working_dir):
        persona = FakePersona()
        builder = CachedPromptBuilder(working_dir=working_dir, persona=persona)
        prompt = builder.static_prompt
        assert "I write content." in prompt
        assert "# SOUL.md (Writer)" in prompt

    def test_set_persona_invalidates(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        p1 = builder.static_prompt
        builder.set_persona(FakePersona())
        p2 = builder.static_prompt
        assert p1 != p2

    def test_missing_required_returns_default(self, tmp_path):
        # No AGENTS.md
        (tmp_path / "SOUL.md").write_text("soul")
        builder = CachedPromptBuilder(working_dir=tmp_path)
        assert builder.static_prompt == DEFAULT_SYS_PROMPT


# ---------------------------------------------------------------------------
# PersonaPromptPool Tests
# ---------------------------------------------------------------------------


class TestPersonaPromptPool:
    def test_get_default(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        builder = pool.get()
        assert isinstance(builder, CachedPromptBuilder)
        assert pool.size == 1

    def test_persona_isolation(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        b1 = pool.get()
        b2 = pool.get(FakePersona(id="writer"))
        assert b1 is not b2
        assert pool.size == 2

    def test_same_persona_reuses(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        persona = FakePersona(id="writer")
        b1 = pool.get(persona)
        b2 = pool.get(persona)
        assert b1 is b2

    def test_invalidate_all(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        pool.get()
        pool.get(FakePersona())
        pool.invalidate_all()
        assert pool.size == 0


# ---------------------------------------------------------------------------
# select_memory_tier Tests
# ---------------------------------------------------------------------------


class TestSelectMemoryTier:
    def test_selects_richest_that_fits(self):
        tiers = {"L0": "short", "L1": "medium length text", "L2": "a" * 1000}
        name, content = select_memory_tier(tiers, available_tokens=500, static_tokens=100)
        assert name == "L2"
        assert content == "a" * 1000

    def test_falls_back_to_smaller(self):
        tiers = {"L0": "tiny", "L1": "small", "L2": "a" * 100000}
        name, _content = select_memory_tier(tiers, available_tokens=100, static_tokens=90)
        assert name in ("L0", "L1")

    def test_empty_tiers_returns_l0(self):
        tiers = {"L0": "", "L1": "", "L2": ""}
        name, _content = select_memory_tier(tiers, available_tokens=1000, static_tokens=0)
        assert name == "L0"

    def test_negative_budget_returns_empty(self):
        """When static_tokens > available_tokens, no tier should be injected."""
        tiers = {"L0": "some content", "L1": "more", "L2": "a" * 1000}
        _name, content = select_memory_tier(tiers, available_tokens=100, static_tokens=200)
        assert content == ""


class TestPersonaPromptPoolEviction:
    def test_eviction_at_max_size(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        # Fill pool to max
        for i in range(PersonaPromptPool._MAX_POOL_SIZE + 5):
            pool.get(FakePersona(id=f"persona_{i}", name=f"P{i}", soul_md=f"Soul {i}"))
        assert pool.size <= PersonaPromptPool._MAX_POOL_SIZE
