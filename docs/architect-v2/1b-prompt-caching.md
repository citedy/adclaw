# 1B: Prompt Caching & Static/Dynamic Separation

## Problem Statement

The current `PromptBuilder` (`src/adclaw/agents/prompt.py`) reads markdown files from disk on every call to `build()`. The `ReActAgent` mitigates this with a "Frozen Memory Snapshot" — a hash-based cache (`_frozen_prompt` / `_frozen_hash`) that avoids rebuilding when `AGENTS.md`, `SOUL.md`, and `PROFILE.md` haven't changed. However, several issues remain:

1. **No static/dynamic boundary.** The frozen snapshot caches the entire system prompt as one blob. Dynamic context (`env_context`, AOM tiered memories, session state, active tool list) is either baked into the hash or prepended outside the cache, meaning any dynamic change invalidates the whole cache.

2. **No section-level memoization.** Each markdown file is re-read and re-parsed (frontmatter stripping, section headers) even when only one file changed. With three required files, two reads are wasted on every single-file change.

3. **No tiered context integration.** AOM's `tiers.py` produces L0/L1/L2 summaries (200/1000/3000 tokens), but nothing in the prompt pipeline injects them. The tiered context is only available via the `query_long_term_memory` tool — it never appears in the system prompt itself.

4. **No per-persona cache isolation.** Persona switch re-hashes and rebuilds. With N personas, the agent constantly thrashes between prompt snapshots.

### Current Flow (Simplified)

```text
User message arrives
  → ReActAgent.rebuild_sys_prompt()
    → _prompt_source_hash()           # SHA-256 of file bytes + persona + env
    → if hash == _frozen_hash: reuse  # HIT
    → else: PromptBuilder(working_dir).build()  # MISS: read all files from disk
      → _load_file("AGENTS.md")
      → _load_file("SOUL.md") or persona.soul_md
      → _load_file("PROFILE.md")
      → join parts
    → prepend env_context
    → freeze result
```

## Design: Static/Dynamic Separation

Inspired by Claude Code's prompt architecture — where a stable "system-reminder" prefix enables provider-level prompt caching (Anthropic's 5-min TTL), and dynamic sections are appended after the cache boundary.

### Prompt Structure (After)

```text
┌─────────────────────────────────────────────┐
│  STATIC BLOCK (cached, hash-validated)      │
│  ┌─────────────────────────────────────┐    │
│  │ # AGENTS.md                         │    │
│  │ (workflows, rules, guidelines)      │    │
│  ├─────────────────────────────────────┤    │
│  │ # SOUL.md / SOUL.md (persona-name)  │    │
│  │ (identity, behavioral principles)   │    │
│  ├─────────────────────────────────────┤    │
│  │ # PROFILE.md                        │    │
│  │ (user profile, preferences)         │    │
│  └─────────────────────────────────────┘    │
├─────────────────────────────────────────────┤
│  DYNAMIC BLOCK (rebuilt per-turn)           │
│  ┌─────────────────────────────────────┐    │
│  │ # Environment Context               │    │
│  │ (channel info, session metadata)    │    │
│  ├─────────────────────────────────────┤    │
│  │ # Memory Context (AOM Tiered)       │    │
│  │ L0: critical decisions (200 tok)    │    │
│  │ L1: working context (1000 tok)      │    │
│  │ L2: full details (3000 tok)         │    │
│  ├─────────────────────────────────────┤    │
│  │ # Active Tools                      │    │
│  │ (registered skills, MCP tools)      │    │
│  ├─────────────────────────────────────┤    │
│  │ # Team Summary                      │    │
│  │ (other personas, coordinator info)  │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

### Key Principles

- **Static block** changes only when markdown files are edited or persona switches. Cached in memory with SHA-256 validation.
- **Dynamic block** is rebuilt every turn. Cheap to compute (string concatenation, no disk I/O).
- **Provider cache alignment:** By keeping the static prefix byte-identical across turns, Anthropic's prompt caching (and OpenAI's) can reuse the KV cache for the static portion. The dynamic suffix is the only part re-processed.
- **Ordering change:** The current code prepends `env_context` *before* the markdown files (`env_context + "\n\n" + files`). The new design moves all dynamic content *after* the static block. This is intentional -- provider KV caching requires a stable prefix, so the static files must come first.

## Implementation

### 1. `CachedSection` — Per-File Memoization

```python
# src/adclaw/agents/prompt.py

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class CachedSection:
    """A single markdown file cached with its content hash."""
    path: Path
    content: str = ""
    content_hash: str = ""
    last_checked: float = 0.0
    CHECK_INTERVAL: float = 2.0  # seconds between stat() calls

    def load(self, force: bool = False) -> str:
        """Load file content, using cache if file unchanged.

        Returns cached content if the file hash hasn't changed.
        Checks file modification at most every CHECK_INTERVAL seconds.
        """
        now = time.monotonic()
        if not force and (now - self.last_checked) < self.CHECK_INTERVAL:
            return self.content

        self.last_checked = now

        if not self.path.exists():
            self.content = ""
            self.content_hash = ""
            return ""

        raw = self.path.read_bytes()
        h = hashlib.sha256(raw).hexdigest()

        if h == self.content_hash:
            return self.content  # File unchanged

        # File changed — re-parse
        text = raw.decode("utf-8", errors="replace").strip()

        # Strip YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2].strip()

        self.content = text
        self.content_hash = h
        return self.content
```

### 2. `CachedPromptBuilder` — Static/Dynamic Split

```python
# src/adclaw/agents/prompt.py (continued)

@dataclass
class DynamicContext:
    """All per-turn dynamic sections."""
    env_context: str = ""
    aom_tier: str = ""          # Tiered memory content (L0, L1, or L2)
    aom_tier_name: str = ""     # "L0", "L1", "L2"
    active_tools: str = ""      # Tool summary
    team_summary: str = ""

    def render(self) -> str:
        """Render dynamic sections into a single string."""
        parts: list[str] = []

        if self.env_context:
            parts.append("# Environment Context\n")
            parts.append(self.env_context)

        if self.aom_tier:
            parts.append(f"# Memory Context ({self.aom_tier_name})\n")
            parts.append(self.aom_tier)

        if self.active_tools:
            parts.append("# Active Tools\n")
            parts.append(self.active_tools)

        if self.team_summary:
            parts.append("# Team Summary\n")
            parts.append(self.team_summary)

        return "\n\n".join(parts)


class CachedPromptBuilder:
    """Prompt builder with static/dynamic separation and per-section caching.

    Static sections (AGENTS.md, SOUL.md, PROFILE.md) are cached per-file
    and only re-read when the file content hash changes. The combined
    static prompt is stored in memory.

    Dynamic sections (env_context, AOM tiered context, tools, team summary)
    are appended per-turn without invalidating the static cache.

    Usage:
        builder = CachedPromptBuilder(working_dir=Path("/app/working"))
        # On each turn:
        prompt = builder.build(dynamic=DynamicContext(
            env_context="channel=telegram",
            aom_tier=tiers["L1"],
            aom_tier_name="L1",
        ))
    """

    def __init__(self, working_dir: Path, persona: Optional["PersonaConfig"] = None):
        self._working_dir = working_dir
        self._persona = persona

        # Per-file caches
        self._file_caches: Dict[str, CachedSection] = {}
        for filename, _required in PromptConfig.FILE_ORDER:
            self._file_caches[filename] = CachedSection(
                path=working_dir / filename,
            )

        # Combined static prompt cache
        self._static_prompt: str = ""
        self._static_hash: str = ""

    def _build_static(self) -> str:
        """Build the static portion from cached file sections.

        Only re-reads files whose content hash changed.
        Returns the combined static prompt.

        Output format matches PromptBuilder.build() exactly:
        sections are separated by double blank lines (\\n\\n\\n\\n)
        to preserve backward compatibility and provider cache alignment.
        """
        parts: list[str] = []

        for filename, required in PromptConfig.FILE_ORDER:
            # Handle persona soul_md override
            if filename == "SOUL.md" and self._persona and self._persona.soul_md:
                if parts:
                    parts.append("")
                parts.append(f"# SOUL.md ({self._persona.name})")
                parts.append("")
                parts.append(self._persona.soul_md)
                continue

            cache = self._file_caches[filename]
            content = cache.load()

            if not content and required:
                logger.warning(
                    "%s not found or empty in %s", filename, self._working_dir,
                )
                return DEFAULT_SYS_PROMPT

            if content:
                if parts:
                    parts.append("")
                parts.append(f"# {filename}")
                parts.append("")
                parts.append(content)

        return "\n\n".join(parts) if parts else DEFAULT_SYS_PROMPT

    def _static_source_hash(self) -> str:
        """Hash of all static section content hashes + persona config."""
        h = hashlib.sha256()
        for filename in self._file_caches:
            h.update(self._file_caches[filename].content_hash.encode())
        if self._persona:
            h.update(self._persona.id.encode())
            h.update(self._persona.soul_md.encode())
        return h.hexdigest()

    @property
    def static_prompt(self) -> str:
        """Get the cached static prompt, rebuilding only if files changed."""
        # Force file cache checks
        for cache in self._file_caches.values():
            cache.load()

        current_hash = self._static_source_hash()
        if current_hash != self._static_hash:
            self._static_prompt = self._build_static()
            old = self._static_hash
            self._static_hash = current_hash
            logger.info(
                "Static prompt REBUILT (hash=%s->%s, len=%d)",
                (old or "none")[:8], current_hash[:8],
                len(self._static_prompt),
            )
        else:
            logger.debug(
                "Static prompt HIT (hash=%s, len=%d)",
                current_hash[:8], len(self._static_prompt),
            )
        return self._static_prompt

    def build(self, dynamic: Optional[DynamicContext] = None) -> str:
        """Build the full system prompt: static + dynamic.

        Args:
            dynamic: Per-turn dynamic context. If None, only static
                     prompt is returned.

        Returns:
            Complete system prompt string.
        """
        static = self.static_prompt

        if dynamic is None:
            return static

        dynamic_text = dynamic.render()
        if not dynamic_text:
            return static

        return f"{static}\n\n{dynamic_text}"

    def set_persona(self, persona: Optional["PersonaConfig"]) -> None:
        """Switch persona, invalidating the static cache."""
        self._persona = persona
        self._static_hash = ""  # Force rebuild on next access

    def invalidate(self) -> None:
        """Force full rebuild on next build() call."""
        self._static_hash = ""
        for cache in self._file_caches.values():
            cache.content_hash = ""
            cache.last_checked = 0.0
```

### 3. Per-Persona Prompt Cache Pool

> **Note:** This is a thin dict wrapper. If persona count stays small (< 10),
> a plain `dict[str, CachedPromptBuilder]` with a helper function would suffice.
> The class form is used here for `invalidate_all()` convenience.

```python
# src/adclaw/agents/prompt.py (continued)

class PersonaPromptPool:
    """Cache pool that maintains one CachedPromptBuilder per persona.

    Persona switch = load a different builder, not rebuild from scratch.
    The "default" persona (no persona config) uses key "__default__".
    """

    def __init__(self, working_dir: Path):
        self._working_dir = working_dir
        self._pool: Dict[str, CachedPromptBuilder] = {}

    def get(self, persona: Optional["PersonaConfig"] = None) -> CachedPromptBuilder:
        """Get or create a CachedPromptBuilder for the given persona."""
        key = persona.id if persona else "__default__"

        if key not in self._pool:
            self._pool[key] = CachedPromptBuilder(
                working_dir=self._working_dir,
                persona=persona,
            )
            logger.debug("Created prompt cache for persona '%s'", key)

        return self._pool[key]

    def invalidate_all(self) -> None:
        """Invalidate all cached prompts (e.g., after file edit)."""
        for builder in self._pool.values():
            builder.invalidate()

    @property
    def size(self) -> int:
        return len(self._pool)
```

### 4. Tiered Context Integration

The `tiers.py` module already produces `{"L0": ..., "L1": ..., "L2": ...}` dictionaries. The integration point selects which tier to inject based on available token budget.

```python
# src/adclaw/agents/prompt.py (continued)

def select_memory_tier(
    tiers: Dict[str, str],
    available_tokens: int,
    static_tokens: int,
) -> tuple[str, str]:
    """Select the richest memory tier that fits the token budget.

    Args:
        tiers: Dict from generate_tiers() with keys "L0", "L1", "L2".
        available_tokens: Total context window budget for the system prompt.
        static_tokens: Tokens already consumed by the static prompt.

    Returns:
        Tuple of (tier_name, tier_content). Returns ("", "") if no tier fits.
    """
    # NOTE: _estimate_tokens is currently private in tiers.py.
    # Rename it to estimate_tokens (drop the underscore) before using here.
    from ..memory_agent.tiers import estimate_tokens

    remaining = available_tokens - static_tokens

    # Try richest tier first
    for tier_name in ("L2", "L1", "L0"):
        content = tiers.get(tier_name, "")
        if not content:
            continue
        est = estimate_tokens(content)
        if est <= remaining:
            logger.debug(
                "Selected memory tier %s (%d tokens, %d remaining)",
                tier_name, est, remaining,
            )
            return tier_name, content

    logger.debug("No memory tier fits within %d remaining tokens", remaining)
    return "", ""
```

### 5. Integration into `ReActAgent`

The `ReActAgent` changes are minimal — replace `_frozen_prompt`/`_frozen_hash` with a `CachedPromptBuilder` and pass `DynamicContext` on each turn.

```python
# src/adclaw/agents/react_agent.py — changes (not a full file)

class ReActAgent:
    def __init__(self, ...):
        # Replace _frozen_prompt/_frozen_hash with:
        from .prompt import CachedPromptBuilder, PersonaPromptPool

        self._prompt_pool = PersonaPromptPool(
            working_dir=Path(WORKING_DIR),
        )
        self._prompt_builder = self._prompt_pool.get(self._persona)
        # ...

    def rebuild_sys_prompt(self) -> None:
        """Rebuild system prompt using static/dynamic separation."""
        from .prompt import DynamicContext, select_memory_tier

        # Build dynamic context
        dynamic = DynamicContext(
            env_context=self._env_context or "",
            team_summary=self._team_summary or "",
        )

        # Inject AOM tiered memory if available.
        # NOTE: AOMManager does not have a get_summary() method yet.
        # Phase 3 must add one (e.g. query_agent.get_cached_summary()).
        if self._aom_manager and self._aom_manager.is_running:
            try:
                from ..memory_agent.tiers import generate_tiers, estimate_tokens

                full_summary = self._aom_manager.get_cached_summary()
                if full_summary:
                    tiers = generate_tiers(full_summary)
                    static_tokens = estimate_tokens(
                        self._prompt_builder.static_prompt
                    )
                    tier_name, tier_content = select_memory_tier(
                        tiers,
                        available_tokens=self._max_input_length,
                        static_tokens=static_tokens,
                    )
                    dynamic.aom_tier = tier_content
                    dynamic.aom_tier_name = tier_name
            except Exception as exc:
                logger.warning("Failed to inject AOM tier: %s", exc)

        # Build full prompt
        self._sys_prompt = self._prompt_builder.build(dynamic=dynamic)

        # Update system message in memory
        for msg, _marks in self.memory.content:
            if msg.role == "system":
                msg.content = self.sys_prompt
            break
```

## Token Savings Estimate

Assumptions based on typical AdClaw deployment:

| Component | Tokens (est.) | Category |
|-----------|---------------|----------|
| AGENTS.md | ~2,000 | Static |
| SOUL.md | ~800 | Static |
| PROFILE.md | ~400 | Static |
| **Static total** | **~3,200** | **Cached** |
| env_context | ~100 | Dynamic |
| AOM L1 tier | ~1,000 | Dynamic |
| Team summary | ~200 | Dynamic |
| **Dynamic total** | **~1,300** | **Per-turn** |

### Savings Per Conversation Turn

Two separate layers of caching are at play:

1. **Provider-level KV cache (Anthropic 5-min TTL, OpenAI prefix caching):** The existing frozen snapshot already provides this benefit because the prompt string is byte-identical across turns when files haven't changed. The new static/dynamic split improves this by keeping the static prefix stable even when dynamic context changes (env_context, AOM tier). Previously, any env_context change invalidated the frozen hash and produced a new prompt string, breaking provider cache alignment.

2. **In-memory section caching (new):** Avoids re-reading files from disk and re-parsing frontmatter when only one file changed or no files changed.

Estimated per-turn improvement from the static/dynamic split:

- **Before:** Any `env_context` change (e.g., new session metadata) invalidates the frozen hash, causing a full rebuild. The entire ~4,500-token prompt is a new string, defeating provider KV caching.
- **After:** Only the ~1,300-token dynamic suffix changes. The ~3,200-token static prefix is byte-identical, enabling provider KV cache reuse. Net: provider processes ~1,300 new tokens instead of ~4,500 on dynamic-only changes.

### Savings From Per-Persona Pool

Without the pool, switching from persona A to persona B requires a full rebuild (read files, parse, join). With the pool, each persona's static prompt is built once and reused on subsequent switches. For a coordinator cycling through 5 personas:

- **Before:** Each switch triggers a full rebuild (~3 file reads + parse + join).
- **After:** First switch per persona triggers a rebuild; all subsequent switches are O(1) dict lookups.
- The saving is in CPU and disk I/O, not in token processing (each persona already gets its own prompt string).

### Savings From Section-Level Memoization

When only one file changes (e.g., PROFILE.md updated), the old approach re-reads all three files. The new approach re-reads only the changed file. Disk I/O saving: ~67% per rebuild. The `CHECK_INTERVAL` (2s) means rapid successive calls (e.g., during multi-turn conversations) skip `stat()` calls entirely.

## Testing Strategy

### Unit Tests

```python
# tests/test_prompt_caching.py

import hashlib
import tempfile
import time
from pathlib import Path

import pytest

from adclaw.agents.prompt import (
    CachedPromptBuilder,
    CachedSection,
    DynamicContext,
    PersonaPromptPool,
    select_memory_tier,
    DEFAULT_SYS_PROMPT,
)
from adclaw.config.config import PersonaConfig


@pytest.fixture
def working_dir(tmp_path):
    """Create a temporary working directory with standard markdown files."""
    (tmp_path / "AGENTS.md").write_text("You are a marketing agent.\n\n## Rules\n- Be concise")
    (tmp_path / "SOUL.md").write_text("Core identity: helpful and proactive.")
    return tmp_path


class TestCachedSection:
    def test_load_reads_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Hello world")
        cs = CachedSection(path=f)
        assert cs.load() == "Hello world"
        assert cs.content_hash != ""

    def test_load_caches_content(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Original")
        cs = CachedSection(path=f)
        cs.load()
        original_hash = cs.content_hash

        # Within CHECK_INTERVAL, even if file changes, cache is returned
        f.write_text("Modified")
        assert cs.load() == "Original"  # Still cached (interval not elapsed)

    def test_load_detects_change_after_interval(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Original")
        cs = CachedSection(path=f, CHECK_INTERVAL=0.0)  # No delay
        cs.load()

        f.write_text("Modified")
        cs.last_checked = 0.0  # Force re-check
        assert cs.load() == "Modified"

    def test_load_missing_file(self, tmp_path):
        cs = CachedSection(path=tmp_path / "missing.md")
        assert cs.load() == ""
        assert cs.content_hash == ""

    def test_strips_yaml_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Test\n---\nActual content here")
        cs = CachedSection(path=f)
        assert cs.load() == "Actual content here"

    def test_force_bypasses_interval(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("V1")
        cs = CachedSection(path=f)
        cs.load()

        f.write_text("V2")
        # Without force, interval prevents re-read
        assert cs.load() == "V1"
        # With force, always re-reads
        assert cs.load(force=True) == "V2"


class TestCachedPromptBuilder:
    def test_build_static_only(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        prompt = builder.build()
        assert "# AGENTS.md" in prompt
        assert "# SOUL.md" in prompt
        assert "marketing agent" in prompt

    def test_build_with_dynamic(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        dynamic = DynamicContext(
            env_context="channel=telegram, user=admin",
            aom_tier="User prefers concise responses.",
            aom_tier_name="L1",
        )
        prompt = builder.build(dynamic=dynamic)
        assert "# AGENTS.md" in prompt
        assert "# Environment Context" in prompt
        assert "# Memory Context (L1)" in prompt
        assert "channel=telegram" in prompt

    def test_static_cache_hit(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        p1 = builder.static_prompt
        p2 = builder.static_prompt
        assert p1 == p2
        assert p1 is p2  # Same object — not rebuilt

    def test_static_cache_invalidates_on_file_change(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        # Force zero check interval for testing
        for cache in builder._file_caches.values():
            cache.CHECK_INTERVAL = 0.0

        p1 = builder.static_prompt

        (working_dir / "AGENTS.md").write_text("Updated agent instructions.")
        for cache in builder._file_caches.values():
            cache.last_checked = 0.0
        builder._static_hash = ""  # Force recheck

        p2 = builder.static_prompt
        assert p1 != p2
        assert "Updated agent instructions" in p2

    def test_persona_override_soul_md(self, working_dir):
        persona = PersonaConfig(
            id="marketer",
            name="Marketer",
            soul_md="I am a growth hacker focused on ROI.",
        )
        builder = CachedPromptBuilder(working_dir=working_dir, persona=persona)
        prompt = builder.build()
        assert "# SOUL.md (Marketer)" in prompt
        assert "growth hacker" in prompt
        # Original SOUL.md content should NOT be present
        assert "Core identity" not in prompt

    def test_set_persona_invalidates_cache(self, working_dir):
        builder = CachedPromptBuilder(working_dir=working_dir)
        p1 = builder.static_prompt

        persona = PersonaConfig(id="writer", name="Writer", soul_md="I write.")
        builder.set_persona(persona)
        p2 = builder.static_prompt
        assert p1 != p2

    def test_missing_required_file_returns_default(self, tmp_path):
        # Only SOUL.md, no AGENTS.md
        (tmp_path / "SOUL.md").write_text("Soul content")
        builder = CachedPromptBuilder(working_dir=tmp_path)
        prompt = builder.build()
        assert prompt == DEFAULT_SYS_PROMPT

    def test_optional_profile_missing(self, working_dir):
        # PROFILE.md not created in fixture — should still work
        builder = CachedPromptBuilder(working_dir=working_dir)
        prompt = builder.build()
        assert "# AGENTS.md" in prompt
        assert "PROFILE.md" not in prompt


class TestDynamicContext:
    def test_empty_dynamic(self):
        d = DynamicContext()
        assert d.render() == ""

    def test_all_sections(self):
        d = DynamicContext(
            env_context="env info",
            aom_tier="memory content",
            aom_tier_name="L2",
            active_tools="tool1, tool2",
            team_summary="3 personas active",
        )
        rendered = d.render()
        assert "# Environment Context" in rendered
        assert "# Memory Context (L2)" in rendered
        assert "# Active Tools" in rendered
        assert "# Team Summary" in rendered
        assert "3 personas active" in rendered

    def test_partial_sections(self):
        d = DynamicContext(aom_tier="memories", aom_tier_name="L0")
        rendered = d.render()
        assert "# Memory Context (L0)" in rendered
        assert "Environment" not in rendered


class TestPersonaPromptPool:
    def test_default_persona(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        builder = pool.get()
        assert builder is not None
        assert pool.size == 1

    def test_multiple_personas(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        p1 = PersonaConfig(id="seo", name="SEO", soul_md="SEO expert.")
        p2 = PersonaConfig(id="ads", name="Ads", soul_md="Ads expert.")

        b1 = pool.get(p1)
        b2 = pool.get(p2)
        b_default = pool.get()

        assert pool.size == 3
        assert b1 is not b2
        assert b1 is pool.get(p1)  # Same instance on second get

    def test_invalidate_all(self, working_dir):
        pool = PersonaPromptPool(working_dir=working_dir)
        pool.get()
        pool.get(PersonaConfig(id="x", name="X"))

        # Should not raise
        pool.invalidate_all()
        assert pool.size == 2


class TestSelectMemoryTier:
    def test_selects_richest_fitting_tier(self):
        tiers = {
            "L0": "Short.",           # ~2 tokens
            "L1": "A " * 500,         # ~500 tokens
            "L2": "B " * 1500,        # ~1500 tokens
        }
        # Plenty of room — should pick L2
        tier_name, content = select_memory_tier(
            tiers, available_tokens=10000, static_tokens=3000,
        )
        assert tier_name == "L2"

    def test_falls_back_to_smaller_tier(self):
        tiers = {
            "L0": "Short.",
            "L1": "A " * 500,
            "L2": "B " * 1500,
        }
        # Only ~600 tokens remaining — L2 won't fit, L1 won't fit, pick L0
        tier_name, content = select_memory_tier(
            tiers, available_tokens=3600, static_tokens=3000,
        )
        assert tier_name == "L0"

    def test_no_tier_fits(self):
        tiers = {"L0": "A " * 500, "L1": "B " * 1000, "L2": "C " * 3000}
        tier_name, content = select_memory_tier(
            tiers, available_tokens=3000, static_tokens=3000,
        )
        assert tier_name == ""
        assert content == ""

    def test_empty_tiers(self):
        tiers = {"L0": "", "L1": "", "L2": ""}
        tier_name, content = select_memory_tier(
            tiers, available_tokens=10000, static_tokens=0,
        )
        assert tier_name == ""
```

### Integration Tests

```python
# tests/test_prompt_caching_integration.py

import tempfile
from pathlib import Path

from adclaw.agents.prompt import CachedPromptBuilder, DynamicContext
from adclaw.memory_agent.tiers import generate_tiers


def test_full_pipeline_with_tiered_memory():
    """End-to-end: build prompt with real tiered memory injection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wd = Path(tmpdir)
        (wd / "AGENTS.md").write_text(
            "## Workflow\n1. Analyze the request\n2. Use appropriate tools\n3. Respond concisely"
        )
        (wd / "SOUL.md").write_text(
            "You are a marketing AI assistant. Be data-driven and actionable."
        )

        builder = CachedPromptBuilder(working_dir=wd)

        # Simulate AOM memory
        raw_memory = (
            "Decision: Switched to glm-5 model for 3s response time.\n\n"
            "Config: API endpoint is https://coding-intl.dashscope.aliyuncs.com/v1\n\n"
            "Note: User prefers English responses.\n\n"
            "Action: Need to update PROFILE.md with timezone.\n\n"
            "Context: Last session discussed SEO keyword strategy for Q2."
        )
        tiers = generate_tiers(raw_memory)

        # Verify tiers are generated
        assert tiers["L0"]  # At least something in L0
        assert len(tiers["L2"]) >= len(tiers["L0"])  # L2 is superset

        # Build with L1 tier
        dynamic = DynamicContext(
            env_context="channel=telegram",
            aom_tier=tiers["L1"],
            aom_tier_name="L1",
        )
        prompt = builder.build(dynamic=dynamic)

        # Static sections present
        assert "# AGENTS.md" in prompt
        assert "# SOUL.md" in prompt

        # Dynamic sections present
        assert "# Environment Context" in prompt
        assert "# Memory Context (L1)" in prompt

        # Second call should use cached static
        prompt2 = builder.build(dynamic=DynamicContext(
            env_context="channel=discord",
            aom_tier=tiers["L0"],
            aom_tier_name="L0",
        ))
        assert "channel=discord" in prompt2
        assert "Memory Context (L0)" in prompt2
        # Static portion is identical
        static = builder.static_prompt
        assert prompt.startswith(static)
        assert prompt2.startswith(static)
```

### Benchmarks

```python
# tests/bench_prompt_caching.py

"""Run with: pytest tests/bench_prompt_caching.py -v --benchmark (requires pytest-benchmark)"""

import tempfile
from pathlib import Path

import pytest

from adclaw.agents.prompt import CachedPromptBuilder, DynamicContext, PromptBuilder


@pytest.fixture
def working_dir(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Rules\n" + "- Rule line\n" * 200)
    (tmp_path / "SOUL.md").write_text("Identity and principles.\n" * 50)
    (tmp_path / "PROFILE.md").write_text("User profile info.\n" * 30)
    return tmp_path


def test_bench_old_prompt_builder(working_dir, benchmark):
    """Benchmark: old PromptBuilder (reads files every call)."""
    def run():
        builder = PromptBuilder(working_dir=working_dir)
        return builder.build()
    benchmark(run)


def test_bench_cached_prompt_builder_miss(working_dir, benchmark):
    """Benchmark: CachedPromptBuilder first call (cold cache)."""
    def run():
        builder = CachedPromptBuilder(working_dir=working_dir)
        return builder.build()
    benchmark(run)


def test_bench_cached_prompt_builder_hit(working_dir, benchmark):
    """Benchmark: CachedPromptBuilder subsequent calls (warm cache)."""
    builder = CachedPromptBuilder(working_dir=working_dir)
    builder.build()  # Warm up

    dynamic = DynamicContext(env_context="channel=telegram")

    def run():
        return builder.build(dynamic=dynamic)
    benchmark(run)
```

## Migration Path

1. **Phase 1 (non-breaking):** Add `CachedPromptBuilder`, `DynamicContext`, `PersonaPromptPool`, and `select_memory_tier` to `prompt.py` alongside existing code. Existing `PromptBuilder` and `build_system_prompt_from_working_dir` remain unchanged.

2. **Phase 2:** Update `ReActAgent.__init__` to create a `PersonaPromptPool`. Update `rebuild_sys_prompt` to use `CachedPromptBuilder.build(dynamic=...)` instead of `_frozen_prompt`/`_frozen_hash`. Remove the old frozen snapshot fields.

3. **Phase 3:** Wire AOM tiered injection into `rebuild_sys_prompt`. **Prerequisite:** `AOMManager` currently has no method to retrieve a cached summary. Add `get_cached_summary() -> str` (or similar) that returns the latest compacted memory text. Also rename `_estimate_tokens` to `estimate_tokens` in `tiers.py` to make it a public API.

4. **Phase 4:** Remove old `PromptBuilder` usage from `build_system_prompt_from_working_dir` (or make it delegate to `CachedPromptBuilder` internally for backward compatibility).
