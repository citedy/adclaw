# -*- coding: utf-8 -*-
# flake8: noqa: E501
"""System prompt building utilities.

This module provides utilities for building system prompts from
markdown configuration files in the working directory.
"""
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Default fallback prompt
DEFAULT_SYS_PROMPT = """
You are a helpful assistant.
"""

# Backward compatibility alias
SYS_PROMPT = DEFAULT_SYS_PROMPT


class PromptConfig:
    """Configuration for system prompt building."""

    # Define file loading order: (filename, required)
    FILE_ORDER = [
        ("AGENTS.md", True),
        ("SOUL.md", True),
        ("PROFILE.md", False),
    ]


class PromptBuilder:
    """Builder for constructing system prompts from markdown files."""

    def __init__(self, working_dir: Path, persona=None, team_summary: str = ""):
        """Initialize prompt builder.

        Args:
            working_dir: Directory containing markdown configuration files
            persona: Optional PersonaConfig with soul_md override
            team_summary: Optional team summary to append at the end
        """
        self.working_dir = working_dir
        self.persona = persona
        self.team_summary = team_summary
        self.prompt_parts = []
        self.loaded_count = 0

    def _load_file(self, filename: str, required: bool) -> bool:
        """Load a single markdown file.

        Args:
            filename: Name of the file to load
            required: Whether the file is required

        Returns:
            True if file was loaded successfully, False otherwise
        """
        file_path = self.working_dir / filename

        if not file_path.exists():
            if required:
                logger.warning(
                    "%s not found in working directory (%s), using default prompt",
                    filename,
                    self.working_dir,
                )
                return False
            else:
                logger.debug("Optional file %s not found, skipping", filename)
                return True  # Not an error for optional files

        try:
            content = file_path.read_text(encoding="utf-8").strip()

            # Remove YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()

            if content:
                if self.prompt_parts:  # Add separator if not first section
                    self.prompt_parts.append("")
                # Add section header with filename
                self.prompt_parts.append(f"# {filename}")
                self.prompt_parts.append("")
                self.prompt_parts.append(content)
                self.loaded_count += 1
                logger.debug("Loaded %s", filename)
            else:
                logger.debug("Skipped empty file: %s", filename)

            return True

        except Exception as e:
            if required:
                logger.error(
                    "Failed to read required file %s: %s",
                    filename,
                    e,
                    exc_info=True,
                )
                return False
            else:
                logger.warning(
                    "Failed to read optional file %s: %s",
                    filename,
                    e,
                )
                return True  # Not fatal for optional files

    def build(self) -> str:
        """Build the system prompt from markdown files.

        Returns:
            Constructed system prompt string
        """
        for filename, required in PromptConfig.FILE_ORDER:
            if filename == "SOUL.md" and self.persona and self.persona.soul_md:
                if self.prompt_parts:
                    self.prompt_parts.append("")
                self.prompt_parts.append(f"# SOUL.md ({self.persona.name})")
                self.prompt_parts.append("")
                self.prompt_parts.append(self.persona.soul_md)
                self.loaded_count += 1
                continue
            if not self._load_file(filename, required):
                # Required file failed to load
                return DEFAULT_SYS_PROMPT

        if self.team_summary:
            self.prompt_parts.append("")
            self.prompt_parts.append(self.team_summary)

        if not self.prompt_parts:
            logger.warning("No content loaded from working directory")
            return DEFAULT_SYS_PROMPT

        # Join all parts with double newlines
        final_prompt = "\n\n".join(self.prompt_parts)

        logger.debug(
            "System prompt built from %d file(s), total length: %d chars",
            self.loaded_count,
            len(final_prompt),
        )

        return final_prompt


def build_system_prompt_from_working_dir(persona=None, team_summary: str = "") -> str:
    """
    Build system prompt by reading markdown files from working directory.

    This function constructs the system prompt by loading markdown files from
    WORKING_DIR (~/.adclaw by default). These files define the agent's behavior,
    personality, and operational guidelines.

    Loading order and priority:
    1. AGENTS.md (required) - Detailed workflows, rules, and guidelines
    2. SOUL.md (required) - Core identity and behavioral principles
    3. PROFILE.md (optional) - Agent identity and user profile

    Args:
        persona: Optional PersonaConfig with soul_md override
        team_summary: Optional team summary to append at the end

    Returns:
        str: Constructed system prompt from markdown files.
             If required files don't exist, returns the default prompt.

    Example:
        If working_dir contains AGENTS.md, SOUL.md and PROFILE.md, they will be combined:
        "# AGENTS.md\\n\\n...\\n\\n# SOUL.md\\n\\n...\\n\\n# PROFILE.md\\n\\n..."
    """
    from ..constant import WORKING_DIR

    builder = PromptBuilder(working_dir=Path(WORKING_DIR), persona=persona, team_summary=team_summary)
    return builder.build()


def build_bootstrap_guidance(
    language: str = "zh",
) -> str:
    """Build bootstrap guidance message for first-time setup.

    Args:
        language: Language code (en/zh)

    Returns:
        Formatted bootstrap guidance message
    """
    if language == "en":
        return """# 🌟 BOOTSTRAP MODE ACTIVATED

**IMPORTANT: You are in first-time setup mode.**

A `BOOTSTRAP.md` file exists in your working directory. This means you should guide the user through the bootstrap process to establish your identity and preferences.

**Your task:**
1. Read the BOOTSTRAP.md file, greet the user warmly as a first meeting, and guide them through the bootstrap process.
2. Follow the instructions in BOOTSTRAP.md. For example, help the user define your identity, their preferences, and establish the working relationship.
3. Create and update the necessary files (PROFILE.md, MEMORY.md, etc.) as described in the guide.
4. After completing the bootstrap process, delete BOOTSTRAP.md as instructed.

**If the user wants to skip:**
If the user explicitly says they want to skip the bootstrap or just want their question answered directly, then proceed to answer their original question below. You can always help them bootstrap later.

**Original user message:**
"""
    else:  # zh
        return """# 🌟 BOOTSTRAP MODE ACTIVATED

**IMPORTANT: You are in first-time setup mode.**

A `BOOTSTRAP.md` file exists in your working directory. This means you should guide the user through the bootstrap process to establish your identity and preferences.

**Your task:**
1. Read the BOOTSTRAP.md file, greet the user warmly as a first meeting, and guide them through the bootstrap process.
2. Follow the instructions in BOOTSTRAP.md. For example, help the user define your identity, their preferences, and establish the working relationship.
3. Create and update the necessary files (PROFILE.md, MEMORY.md, etc.) as described in the guide.
4. After completing the bootstrap process, delete BOOTSTRAP.md as instructed.

**If the user wants to skip:**
If the user explicitly says they want to skip the bootstrap or just want their question answered directly, then proceed to answer their original question below. You can always help them bootstrap later.

**Original user message:**
"""


# ---------------------------------------------------------------------------
# v2: Cached prompt system (static/dynamic separation)
# ---------------------------------------------------------------------------

@dataclass
class CachedSection:
    """Hash-based file cache for a single prompt section."""

    path: Path
    content: str = ""
    content_hash: str = ""
    last_checked: float = 0.0
    CHECK_INTERVAL: ClassVar[float] = 2.0

    def load(self, force: bool = False) -> str:
        """Load file content, using cache if hash unchanged."""
        now = time.monotonic()
        if not force and self.content and (now - self.last_checked) < self.CHECK_INTERVAL:
            return self.content

        self.last_checked = now

        if not self.path.exists():
            self.content = ""
            self.content_hash = ""
            return ""

        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            # Strip YAML frontmatter
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    raw = parts[2].strip()

            new_hash = hashlib.sha256(raw.encode()).hexdigest()
            if new_hash != self.content_hash:
                self.content = raw
                self.content_hash = new_hash
            return self.content
        except Exception as exc:
            logger.warning("CachedSection: failed to read %s: %s", self.path, exc)
            return self.content  # return stale content on error


@dataclass
class DynamicContext:
    """Per-turn dynamic context injected after the static prompt."""

    env_context: str = ""
    aom_tier: str = ""
    aom_tier_name: str = ""
    active_tools: str = ""
    team_summary: str = ""

    def render(self) -> str:
        """Render dynamic sections into formatted string."""
        parts: list[str] = []
        if self.env_context:
            parts.append(self.env_context)
        if self.aom_tier:
            header = f"# Memory Context ({self.aom_tier_name})" if self.aom_tier_name else "# Memory Context"
            parts.append(f"{header}\n\n{self.aom_tier}")
        if self.active_tools:
            parts.append(f"# Active Tools\n\n{self.active_tools}")
        if self.team_summary:
            parts.append(f"# Team Summary\n\n{self.team_summary}")
        return "\n\n".join(parts)


class CachedPromptBuilder:
    """Prompt builder with static/dynamic separation and hash-based caching."""

    def __init__(self, working_dir: Path, persona=None) -> None:
        self._working_dir = working_dir
        self._persona = persona
        self._file_caches: Dict[str, CachedSection] = {}
        self._static_prompt: str = ""
        self._static_hash: str = ""

        # Initialize caches for each file
        for filename, _required in PromptConfig.FILE_ORDER:
            self._file_caches[filename] = CachedSection(path=working_dir / filename)

    def _build_static(self) -> str:
        """Build the static portion from cached files."""
        parts: list[str] = []
        for filename, required in PromptConfig.FILE_ORDER:
            # Persona soul_md override
            if filename == "SOUL.md" and self._persona and getattr(self._persona, "soul_md", None):
                if parts:  # Add separator before persona section
                    parts.append("")
                parts.append(f"# SOUL.md ({self._persona.name})")
                parts.append("")
                parts.append(self._persona.soul_md)
                continue

            section = self._file_caches.get(filename)
            if section is None:
                continue
            content = section.load()
            if content:
                if parts:
                    parts.append("")
                parts.append(f"# {filename}")
                parts.append("")
                parts.append(content)
            elif required:
                return DEFAULT_SYS_PROMPT

        return "\n\n".join(parts) if parts else DEFAULT_SYS_PROMPT

    def _static_source_hash(self) -> str:
        """Hash of all file content hashes + persona for cache invalidation."""
        h = hashlib.sha256()
        for filename, _ in PromptConfig.FILE_ORDER:
            section = self._file_caches.get(filename)
            if section:
                section.load()  # ensure loaded
                h.update(section.content_hash.encode())
        if self._persona:
            h.update(getattr(self._persona, "id", "").encode())
            h.update(getattr(self._persona, "soul_md", "").encode())
        return h.hexdigest()

    @property
    def static_prompt(self) -> str:
        """Get cached static prompt, rebuilding only if files changed."""
        current_hash = self._static_source_hash()
        if current_hash != self._static_hash:
            self._static_prompt = self._build_static()
            self._static_hash = current_hash
        return self._static_prompt

    def build(self, dynamic: Optional[DynamicContext] = None) -> str:
        """Return static + dynamic prompt."""
        static = self.static_prompt
        if dynamic is None:
            return static
        dynamic_text = dynamic.render()
        if not dynamic_text:
            return static
        return f"{static}\n\n{dynamic_text}"

    def set_persona(self, persona) -> None:
        """Switch persona, invalidating the static cache."""
        self._persona = persona
        self._static_hash = ""  # force rebuild

    def invalidate(self) -> None:
        """Force rebuild on next access."""
        self._static_hash = ""
        for section in self._file_caches.values():
            section.content_hash = ""
            section.last_checked = 0.0


class PersonaPromptPool:
    """Maintains one CachedPromptBuilder per persona."""

    _MAX_POOL_SIZE = 50

    def __init__(self, working_dir: Path) -> None:
        self._working_dir = working_dir
        self._builders: Dict[str, CachedPromptBuilder] = {}

    def get(self, persona=None) -> CachedPromptBuilder:
        """Get or create a builder for the given persona."""
        key = getattr(persona, "id", "__default__") if persona else "__default__"
        if key not in self._builders:
            # Evict oldest entry if pool is at capacity
            if len(self._builders) >= self._MAX_POOL_SIZE:
                oldest_key = next(iter(self._builders))
                del self._builders[oldest_key]
            self._builders[key] = CachedPromptBuilder(
                working_dir=self._working_dir, persona=persona
            )
        return self._builders[key]

    def invalidate_all(self) -> None:
        """Clear all cached builders."""
        self._builders.clear()

    @property
    def size(self) -> int:
        return len(self._builders)


def select_memory_tier(
    tiers: Dict[str, str],
    available_tokens: int,
    static_tokens: int,
) -> Tuple[str, str]:
    """Select the richest AOM memory tier that fits the remaining budget.

    Args:
        tiers: Dict from generate_tiers() with keys L0, L1, L2
        available_tokens: Total token budget for the prompt
        static_tokens: Tokens already used by the static prompt

    Returns:
        (tier_name, tier_content) — e.g. ("L2", "full context text")
    """
    from ..memory_agent.tiers import estimate_tokens

    remaining = available_tokens - static_tokens
    # Try richest first
    for tier_name in ("L2", "L1", "L0"):
        content = tiers.get(tier_name, "")
        if not content:
            continue
        tokens = estimate_tokens(content)
        if tokens <= remaining:
            return tier_name, content
    # Budget exhausted — return empty rather than L0 that may not fit
    l0 = tiers.get("L0", "")
    if l0 and estimate_tokens(l0) > remaining:
        return "L0", ""
    return "L0", l0


__all__ = [
    "build_system_prompt_from_working_dir",
    "build_bootstrap_guidance",
    "PromptBuilder",
    "PromptConfig",
    "DEFAULT_SYS_PROMPT",
    "SYS_PROMPT",  # Backward compatibility
    # v2
    "CachedSection",
    "DynamicContext",
    "CachedPromptBuilder",
    "PersonaPromptPool",
    "select_memory_tier",
]
