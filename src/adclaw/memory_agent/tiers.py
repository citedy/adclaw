# -*- coding: utf-8 -*-
"""Tiered context loading — progressive memory summaries at L0/L1/L2 budgets.

Instead of a single summary, generates three tiers of increasing detail:
- L0 (200 tokens): Critical decisions and actions only
- L1 (1000 tokens): Working context with configs and important notes
- L2 (3000 tokens): Full context with all details

Each tier is a superset of the previous. Sections are prioritized by type
and greedily packed into each budget.

Adapted from claw-compactor (github.com/aeromomo/claw-compactor).
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Token budgets per tier
TIER_BUDGETS: Dict[str, int] = {
    "L0": 200,
    "L1": 1000,
    "L2": 3000,
}

# Priority scores for section types (higher = more important)
SECTION_PRIORITIES: Dict[str, int] = {
    "decision": 10,
    "action": 8,
    "config": 7,
    "warning": 7,
    "error": 6,
    "note": 4,
    "context": 3,
    "archive": 1,
}

# Keywords that hint at section type
_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "decision": ["decided", "decision", "chose", "approved", "rejected", "agreed"],
    "action": ["todo", "action", "must", "should", "need to", "will", "task"],
    "config": ["config", "setting", "parameter", "env", "url", "key", "port", "path"],
    "warning": ["warning", "caution", "careful", "don't", "avoid", "never"],
    "error": ["error", "bug", "fix", "issue", "problem", "fail"],
    "note": ["note", "remember", "fyi", "info"],
}


@dataclass
class Section:
    """A chunk of content with a priority classification."""
    content: str
    section_type: str
    priority: int
    token_estimate: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


def _classify_section(text: str) -> str:
    """Classify a text section by keyword matching."""
    lower = text.lower()
    best_type = "note"
    best_count = 0
    for stype, keywords in _TYPE_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in lower)
        if count > best_count:
            best_count = count
            best_type = stype
    return best_type


def split_into_sections(text: str) -> List[Section]:
    """Split text into logical sections (by double newline or bullet groups).

    Each section gets classified and scored.
    """
    # Split on double newlines
    raw_sections = re.split(r"\n{2,}", text.strip())
    sections: List[Section] = []

    for raw in raw_sections:
        raw = raw.strip()
        if not raw:
            continue
        stype = _classify_section(raw)
        priority = SECTION_PRIORITIES.get(stype, 4)
        tokens = estimate_tokens(raw)
        sections.append(Section(
            content=raw,
            section_type=stype,
            priority=priority,
            token_estimate=tokens,
        ))

    return sections


def generate_tiers(
    text: str,
    budgets: Optional[Dict[str, int]] = None,
) -> Dict[str, str]:
    """Generate tiered summaries from text.

    Args:
        text: Full memory/summary text to tier.
        budgets: Override token budgets per tier. Defaults to TIER_BUDGETS.

    Returns:
        Dict mapping tier name ("L0", "L1", "L2") to content string.
        Each tier is a superset of the previous.
    """
    if not text or not text.strip():
        return {"L0": "", "L1": "", "L2": ""}

    budgets = budgets or TIER_BUDGETS
    sections = split_into_sections(text)

    # Sort by priority descending, then by position (stable sort preserves order)
    sections.sort(key=lambda s: -s.priority)

    tiers: Dict[str, str] = {}

    for tier_name in ["L0", "L1", "L2"]:
        budget = budgets.get(tier_name, 1000)
        used = 0
        selected: List[Tuple[int, Section]] = []  # (original_index, section)

        for idx, section in enumerate(sections):
            if used + section.token_estimate <= budget:
                selected.append((idx, section))
                used += section.token_estimate

        # Restore original order for readability
        selected.sort(key=lambda x: x[0])
        tiers[tier_name] = "\n\n".join(s.content for _, s in selected)

    logger.debug(
        "Tiered context: L0=%d, L1=%d, L2=%d tokens (from %d sections)",
        estimate_tokens(tiers["L0"]),
        estimate_tokens(tiers["L1"]),
        estimate_tokens(tiers["L2"]),
        len(sections),
    )

    return tiers
