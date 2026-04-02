# 2C: Session Context Management -- Smart Compaction

## Problem Statement

Current memory compaction in AdClaw triggers at a fixed token ratio (`MEMORY_COMPACT_RATIO = 0.7` of `max_input_length`). When the threshold is crossed, the `MemoryCompactionHook` compacts **all** messages outside the `keep_recent` window (default 10 in the hook, constant `MEMORY_COMPACT_KEEP_RECENT=3` exists but is not used by the hook) into a single summary. There is no intelligence about **what** to compact:

- A user decision like "we chose glm-5 because it responds in 3s vs 17s" gets the same treatment as "ok thanks".
- Error reports and debugging sessions are compressed alongside filler acknowledgments.
- The LLM-generated summary is chronological, losing topic structure and "what failed" context.
- Cross-session knowledge relies entirely on AOM, with no lightweight bridge between sessions.

The deterministic `pre_compress()` pipeline (rule cleanup + n-gram codebook) saves ~15-30% on raw text but operates on the **already-generated** summary, not on the input messages. The tiered context system (`tiers.py`) classifies sections by keyword into L0/L1/L2 budgets but is only used for memory agent output, not for compaction decisions.

**Goal:** Make compaction importance-aware so critical context survives longer, summaries are structured by topic, and new sessions inherit actionable prior knowledge.

---

## Current Architecture (As-Is)

```text
User message arrives
        |
        v
MemoryCompactionHook.__call__()          # pre_reasoning hook
        |
        v
Estimate tokens: system_prompt + compactable + keep_recent + summary
        |
        v
estimated_total > threshold?
    NO  --> optional tool-result truncation
    YES --> pre_compress(previous_summary)    # deterministic pass
            |
            v
        compact_memory(messages_to_compact, previous_summary)
            |                                  # LLM summarization
            v
        update_compressed_summary(compact_content)
        mark messages as COMPRESSED
```

Key files:

| File | Role |
|------|------|
| `agents/hooks/memory_compaction.py` | Trigger logic, threshold check, mark messages |
| `agents/memory/memory_manager.py` | `compact_memory()` delegates to ReMeCopaw |
| `memory_agent/compressor.py` | `pre_compress()`: rule cleanup + n-gram codebook |
| `memory_agent/tiers.py` | `generate_tiers()`: L0/L1/L2 budget packing |
| `constant.py` | `MEMORY_COMPACT_RATIO=0.7`, `MEMORY_COMPACT_KEEP_RECENT=3` (note: hook default is 10, not 3) |

---

## Design: Importance-Aware Compaction

### 1. Message Importance Tagging

Every message entering memory gets an importance tag. Tags are assigned at ingestion time (cheap) and used at compaction time (expensive) to decide what to keep.

```python
# src/adclaw/agents/memory/importance.py

from __future__ import annotations

import re
from enum import IntEnum
from typing import Dict, List, Optional

from agentscope.message import Msg, ToolUseBlock, ToolResultBlock


class Importance(IntEnum):
    """Message importance levels. Higher = survives longer in context."""
    CRITICAL = 5    # User decisions, config changes, explicit instructions
    HIGH = 4        # Errors, warnings, failed attempts, action items
    MEDIUM = 3      # Tool results with meaningful output, task progress
    LOW = 2         # Acknowledgments, status checks, routine output
    TRIVIAL = 1     # Greetings, small talk, empty/minimal responses


# Patterns that signal importance (compiled once at import)
_CRITICAL_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(decided|decision|chose|choose|approved|rejected)\b",
        r"\b(config(ure|uration)?|setting|parameter)\s*(changed?|updated?|set)\b",
        r"\b(never|always|must|critical|important)\b.*\b(do|use|avoid|remember)\b",
        r"\b(from now on|going forward|new rule)\b",
        r"/compact|/new|/reset",  # explicit session commands
    ]
]

_HIGH_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(error|exception|traceback|failed|failure|bug)\b",
        r"\b(warning|caution|don't|avoid|broke|broken)\b",
        r"\b(fix(ed)?|resolved|workaround|rollback)\b",
        r"\b(todo|action item|next step|blocker)\b",
        r"\b(tried|attempted|didn't work|won't work)\b",
    ]
]

_LOW_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^(ok|okay|sure|thanks|got it|understood|ack)\b",
        r"^(yes|no|right|correct|exactly)\s*[.!]?\s*$",
        r"^\s*(done|ready|noted)\s*[.!]?\s*$",
    ]
]


def classify_importance(msg: Msg) -> Importance:
    """Classify a message's importance based on content and role.

    Rules applied in priority order:
    1. System messages are always CRITICAL (they define behavior).
    2. Pattern matching on content for CRITICAL/HIGH/LOW.
    3. Tool call messages default to MEDIUM (they represent actions).
    4. Everything else defaults to MEDIUM.
    """
    content = msg.get_text_content() if hasattr(msg, "get_text_content") else str(msg.content or "")
    role = getattr(msg, "role", "user")

    # System messages are always critical
    if role == "system":
        return Importance.CRITICAL

    # Check critical patterns
    for pattern in _CRITICAL_PATTERNS:
        if pattern.search(content):
            return Importance.CRITICAL

    # Check high-importance patterns
    for pattern in _HIGH_PATTERNS:
        if pattern.search(content):
            return Importance.HIGH

    # Check low-importance patterns (short messages only)
    if len(content) < 100:
        for pattern in _LOW_PATTERNS:
            if pattern.search(content):
                return Importance.LOW

    # Very short responses with no substance
    if len(content.strip()) < 15 and role == "assistant":
        return Importance.LOW

    # Tool calls and results default to MEDIUM.
    # Agentscope Msg stores tool interactions as content blocks
    # (ToolUseBlock/ToolResultBlock), not a top-level tool_calls attribute.
    if isinstance(msg.content, list):
        for block in msg.content:
            if isinstance(block, (ToolUseBlock, ToolResultBlock)):
                return Importance.MEDIUM
            if isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result"):
                return Importance.MEDIUM

    return Importance.MEDIUM


def tag_messages(messages: List[Msg]) -> Dict[str, Importance]:
    """Tag a list of messages with importance scores.

    Returns:
        Dict mapping msg.id to Importance level.
    """
    return {msg.id: classify_importance(msg) for msg in messages}
```

### 2. Tiered Preservation in Compaction

The compaction hook uses importance tags to decide which messages to compact first. Messages are partitioned into tiers that map to the existing L0/L1/L2 system from `tiers.py`:

| Tier | Importance | Compaction behavior |
|------|-----------|---------------------|
| L0 (critical) | CRITICAL | Never auto-compacted. Kept verbatim until explicit `/compact` or session end. |
| L1 (working) | HIGH, MEDIUM | Compacted after 2 compaction cycles. Summarized with detail. |
| L2 (reference) | LOW, TRIVIAL | Compacted first. Aggressive summarization (or dropped entirely). |

```python
# src/adclaw/agents/memory/tiered_compaction.py

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from agentscope.message import Msg

from .importance import Importance, classify_importance

logger = logging.getLogger(__name__)


# How many compaction cycles each tier survives before being compacted
TIER_SURVIVAL_CYCLES: Dict[str, int] = {
    "L0": 999,  # effectively never (manual /compact only)
    "L1": 2,    # survive 2 compaction triggers
    "L2": 0,    # compacted on first trigger
}

# Maps Importance levels to tier names
IMPORTANCE_TO_TIER: Dict[Importance, str] = {
    Importance.CRITICAL: "L0",
    Importance.HIGH: "L1",
    Importance.MEDIUM: "L1",
    Importance.LOW: "L2",
    Importance.TRIVIAL: "L2",
}


@dataclass
class CompactionPlan:
    """Result of planning which messages to compact."""
    to_compact: List[Msg] = field(default_factory=list)
    to_preserve: List[Msg] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


def plan_compaction(
    messages: List[Msg],
    cycle_counts: Dict[str, int],
    current_cycle: int,
) -> CompactionPlan:
    """Decide which messages to compact based on importance tiers.

    Args:
        messages: Messages in the compactable window (excludes system
            prompt and keep_recent).
        cycle_counts: Dict mapping msg.id to the compaction cycle number
            when the message was first seen. Messages not in this dict
            are treated as newly arrived (current_cycle).
        current_cycle: The current compaction cycle number.

    Returns:
        CompactionPlan with messages split into compact vs preserve.
    """
    plan = CompactionPlan()
    tier_counts = {"L0": 0, "L1": 0, "L2": 0}

    for msg in messages:
        importance = classify_importance(msg)
        tier = IMPORTANCE_TO_TIER[importance]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        survival = TIER_SURVIVAL_CYCLES[tier]

        first_seen = cycle_counts.get(msg.id, current_cycle)
        age_in_cycles = current_cycle - first_seen

        if age_in_cycles >= survival:
            plan.to_compact.append(msg)
        else:
            plan.to_preserve.append(msg)

    plan.stats = {
        "total": len(messages),
        "compacting": len(plan.to_compact),
        "preserving": len(plan.to_preserve),
        **{f"tier_{k}": v for k, v in tier_counts.items()},
    }

    logger.info(
        "Compaction plan: %d/%d messages to compact "
        "(L0=%d preserved, L1=%d, L2=%d), cycle=%d",
        len(plan.to_compact),
        len(messages),
        tier_counts["L0"],
        tier_counts["L1"],
        tier_counts["L2"],
        current_cycle,
    )

    return plan
```

### 3. Smart Summary Generation

Instead of chronological summarization, group messages by topic clusters before sending to LLM. This produces structured summaries that are easier to search and more useful when injected into future context.

```python
# src/adclaw/agents/memory/topic_summarizer.py

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from agentscope.message import Msg

from .importance import Importance, classify_importance
from ...memory_agent.compressor import rule_compress

logger = logging.getLogger(__name__)


@dataclass
class TopicCluster:
    """A group of related messages around a single topic."""
    topic: str
    messages: List[Msg]
    max_importance: Importance
    has_failure: bool = False


# Tool names that hint at topic categories
_TOOL_TOPIC_MAP: Dict[str, str] = {
    "execute_shell_command": "shell-ops",
    "read_file": "file-ops",
    "write_file": "file-ops",
    "edit_file": "file-ops",
    "browser_use": "web-research",
    "send_email": "communication",
    "memory_search": "memory-ops",
    "patch_skill_script": "skill-management",
}


def _msg_text(msg: Msg) -> str:
    """Extract text content from a Msg, with fallback."""
    if hasattr(msg, "get_text_content"):
        return msg.get_text_content() or ""
    return str(msg.content or "")


def _extract_tool_names(msg: Msg) -> List[str]:
    """Extract tool names from a message's content blocks.

    Agentscope Msg stores tool calls as ToolUseBlock items in content,
    not as a top-level tool_calls attribute.
    """
    names: List[str] = []
    if not hasattr(msg, "content") or not isinstance(msg.content, list):
        return names
    for block in msg.content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name = block.get("name", "")
            if name:
                names.append(name)
        elif hasattr(block, "name"):
            # ToolUseBlock with a name attribute
            names.append(block.name)
    return names


def _extract_topic_hint(msg: Msg) -> Optional[str]:
    """Extract a topic hint from a message based on tool calls or content."""
    # Check tool calls (via content blocks, not top-level tool_calls)
    tool_names = _extract_tool_names(msg)
    # Check all tool names — prefer mapped topics over generic skill: prefix
    for fn_name in tool_names:
        if fn_name in _TOOL_TOPIC_MAP:
            return _TOOL_TOPIC_MAP[fn_name]
    # No mapped topic found — fall back to first tool name
    if tool_names:
        return f"skill:{tool_names[0]}"

    # Content-based hints
    content = _msg_text(msg)
    lower = content.lower()

    if any(kw in lower for kw in ["config", "setting", "parameter", "env"]):
        return "configuration"
    if any(kw in lower for kw in ["deploy", "docker", "build", "release"]):
        return "deployment"
    if any(kw in lower for kw in ["error", "bug", "fix", "debug", "traceback"]):
        return "debugging"
    if any(kw in lower for kw in ["test", "assert", "expect", "verify"]):
        return "testing"

    return None


def cluster_by_topic(messages: List[Msg]) -> List[TopicCluster]:
    """Group messages into topic clusters.

    Uses a sliding-window approach: consecutive messages with the same
    topic hint are grouped together. Messages without a clear topic
    inherit the topic of their neighbors.
    """
    if not messages:
        return []

    # First pass: assign topic hints
    hints: List[Optional[str]] = [_extract_topic_hint(m) for m in messages]

    # Second pass: fill gaps by inheriting from neighbors
    for i in range(len(hints)):
        if hints[i] is None and i > 0:
            hints[i] = hints[i - 1]
    # Backward pass for leading Nones
    for i in range(len(hints) - 2, -1, -1):
        if hints[i] is None:
            hints[i] = hints[i + 1]
    # Any remaining Nones become "general"
    hints = [h or "general" for h in hints]

    # Third pass: group consecutive same-topic messages
    clusters: List[TopicCluster] = []
    current_topic = hints[0]
    current_msgs: List[Msg] = [messages[0]]

    for i in range(1, len(messages)):
        if hints[i] == current_topic:
            current_msgs.append(messages[i])
        else:
            clusters.append(_build_cluster(current_topic, current_msgs))
            current_topic = hints[i]
            current_msgs = [messages[i]]

    if current_msgs:
        clusters.append(_build_cluster(current_topic, current_msgs))

    return clusters


def _build_cluster(topic: str, messages: List[Msg]) -> TopicCluster:
    """Build a TopicCluster with computed metadata."""
    importances = [classify_importance(m) for m in messages]
    has_failure = any(
        "fail" in _msg_text(m).lower() or "error" in _msg_text(m).lower()
        for m in messages
    )
    return TopicCluster(
        topic=topic,
        messages=messages,
        max_importance=max(importances),
        has_failure=has_failure,
    )


def build_structured_summary_prompt(
    clusters: List[TopicCluster],
    previous_summary: str = "",
) -> str:
    """Build a prompt for LLM summarization that preserves topic structure.

    The prompt instructs the LLM to:
    1. Summarize each topic cluster separately.
    2. Preserve key decisions and entities.
    3. Explicitly note what was tried and failed.
    4. Output in a structured format that tiers.py can classify.
    """
    sections: List[str] = []

    if previous_summary:
        sections.append(
            "## Prior Context (from earlier compaction)\n"
            f"{rule_compress(previous_summary)}"
        )

    for cluster in clusters:
        importance_label = cluster.max_importance.name
        msg_texts = []
        for m in cluster.messages:
            role = getattr(m, "role", "unknown")
            content = _msg_text(m)
            # Truncate very long tool results for the summary prompt
            if len(content) > 500:
                content = content[:400] + f"\n... [{len(content) - 400} chars truncated]"
            msg_texts.append(f"[{role}] {content}")

        failure_marker = " [CONTAINS FAILURES]" if cluster.has_failure else ""
        sections.append(
            f"## Topic: {cluster.topic} (importance: {importance_label}){failure_marker}\n"
            + "\n".join(msg_texts)
        )

    prompt = (
        "Summarize the following conversation segments by topic. "
        "For each topic section:\n"
        "1. State the key outcome or decision (prefix with DECISION: if applicable).\n"
        "2. List any actions taken or pending (prefix with ACTION:).\n"
        "3. If something was tried and failed, note it explicitly "
        "(prefix with FAILED:).\n"
        "4. Preserve exact entity names (file paths, URLs, config values, model names).\n"
        "5. Keep the topic headers.\n"
        "6. For LOW importance topics, write at most one sentence.\n\n"
        + "\n\n".join(sections)
    )

    return prompt
```

### 4. Cross-Session Context

New sessions should not start cold. The AOM (Always-On Memory) agent already stores long-term memories, but the bridge between sessions needs explicit "prior knowledge" injection with staleness cues.

```python
# src/adclaw/agents/memory/session_bridge.py

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ...memory_agent.tiers import generate_tiers, TIER_BUDGETS

logger = logging.getLogger(__name__)

# Staleness thresholds in seconds
FRESH_THRESHOLD = 3600        # < 1 hour: "just now"
RECENT_THRESHOLD = 86400      # < 1 day: "earlier today" / "yesterday"
STALE_THRESHOLD = 604800      # < 1 week: "this week"
# > 1 week: "archived" (may be outdated)


@dataclass
class SessionSummary:
    """Summary of a completed session for cross-session injection."""
    session_id: str
    timestamp: float              # unix epoch when session ended
    summary_text: str             # L1-tier summary of the session
    decisions: List[str]          # extracted DECISION: lines
    failures: List[str]           # extracted FAILED: lines
    topic_tags: List[str]         # topic names from clusters


def staleness_label(timestamp: float) -> str:
    """Human-readable staleness cue for a timestamp."""
    age = time.time() - timestamp
    if age < FRESH_THRESHOLD:
        return "just now"
    if age < RECENT_THRESHOLD:
        hours = int(age / 3600)
        return f"{hours}h ago"
    if age < STALE_THRESHOLD:
        days = int(age / 86400)
        return f"{days}d ago"
    weeks = int(age / 604800)
    return f"{weeks}w ago (may be outdated)"


def build_prior_knowledge_section(
    session_summaries: List[SessionSummary],
    aom_memories: List[str],
    token_budget: int = 2000,
) -> str:
    """Build a 'Prior Knowledge' section for injection into new session context.

    Combines:
    1. Recent session summaries (with staleness cues).
    2. AOM memories (always fresh -- they are curated).

    Content is tiered to fit within token_budget using generate_tiers().

    Args:
        session_summaries: Summaries from recent sessions, newest first.
        aom_memories: Relevant AOM memories for the current context.
        token_budget: Maximum tokens for the prior knowledge section.

    Returns:
        Formatted string ready for injection into system prompt or
        first-message context.
    """
    parts: List[str] = []

    # AOM memories first (highest signal, curated)
    if aom_memories:
        aom_section = "### Long-Term Memory\n" + "\n".join(
            f"- {mem}" for mem in aom_memories
        )
        parts.append(aom_section)

    # Recent session summaries with staleness
    for summary in session_summaries[:5]:  # cap at 5 most recent
        staleness = staleness_label(summary.timestamp)
        header = f"### Session ({staleness})"

        lines = [header]
        if summary.decisions:
            lines.append("Decisions: " + "; ".join(summary.decisions))
        if summary.failures:
            lines.append("Failed approaches: " + "; ".join(summary.failures))
        lines.append(summary.summary_text)

        parts.append("\n".join(lines))

    if not parts:
        return ""

    full_text = "\n\n".join(parts)

    # Tier to fit budget
    custom_budgets = {"L0": token_budget // 4, "L1": token_budget // 2, "L2": token_budget}
    tiers = generate_tiers(full_text, budgets=custom_budgets)

    # Pick the largest tier that fits
    for tier_name in ["L2", "L1", "L0"]:
        tier_text = tiers.get(tier_name, "")
        est_tokens = max(1, len(tier_text) // 4)
        if est_tokens <= token_budget:
            return f"## Prior Knowledge\n{tier_text}"

    return f"## Prior Knowledge\n{tiers.get('L0', '')}"
```

---

## Updated Compaction Hook

The existing `MemoryCompactionHook` is modified to use importance-aware planning:

```python
# Changes to agents/hooks/memory_compaction.py

# In __init__, add:
self._compaction_cycle: int = 0
self._cycle_counts: Dict[str, int] = {}  # msg.id -> first-seen cycle

# In __call__, replace the simple split with:
from ..memory.tiered_compaction import plan_compaction
from ..memory.topic_summarizer import cluster_by_topic, build_structured_summary_prompt

# Track when messages were first seen
for msg in messages_to_compact:
    if msg.id not in self._cycle_counts:
        self._cycle_counts[msg.id] = self._compaction_cycle

# Plan what to compact
plan = plan_compaction(
    messages=messages_to_compact,
    cycle_counts=self._cycle_counts,
    current_cycle=self._compaction_cycle,
)

if plan.to_compact:
    # Cluster by topic for structured summarization
    clusters = cluster_by_topic(plan.to_compact)

    # Build a structured prompt that combines the previous summary
    # with topic-clustered messages. This replaces the raw messages
    # that compact_memory would normally receive -- the structured
    # prompt IS the previous_summary context for the LLM call.
    #
    # NOTE: compact_memory() passes previous_summary to ReMeCopaw
    # which injects it as context for the LLM summarizer. We pass
    # the structured prompt here so the LLM sees topic-grouped
    # content instead of a flat chronological blob.
    structured_context = build_structured_summary_prompt(
        clusters=clusters,
        previous_summary=previous_summary,
    )

    # LLM generates topic-structured summary.
    # `messages` provides the raw message objects (needed by compact_memory
    # for token counting, message-mark updates, and as fallback content).
    # `previous_summary` supplies the topic-clustered structural template
    # that the LLM uses to organize its output -- it does NOT duplicate
    # `messages` but rather reshapes them into a summarization prompt.
    compact_content = await self.memory_manager.compact_memory(
        messages=plan.to_compact,
        previous_summary=structured_context,
    )

    await agent.memory.update_compressed_summary(compact_content)
    await agent.memory.update_messages_mark(
        new_mark=_MemoryMark.COMPRESSED,
        msg_ids=[msg.id for msg in plan.to_compact],
    )

    # Clean up cycle tracking for compacted messages
    for msg in plan.to_compact:
        self._cycle_counts.pop(msg.id, None)

# Also clean up IDs for messages no longer in the compactable window
# to prevent unbounded growth of _cycle_counts (L0 messages with
# survival=999 would otherwise accumulate forever).
active_ids = {msg.id for msg in messages_to_compact}
self._cycle_counts = {
    mid: cyc for mid, cyc in self._cycle_counts.items()
    if mid in active_ids
}

self._compaction_cycle += 1
```

---

## Implementation Plan

### Phase 1: Importance Tagging (1-2 hours)

1. Create `src/adclaw/agents/memory/importance.py` with `classify_importance()` and `tag_messages()`.
2. Compute importance on-demand via `classify_importance(msg)` during compaction (not persisted — classification is cheap and stateless).
3. Unit tests for pattern matching across all importance levels.

### Phase 2: Tiered Compaction (2-3 hours)

1. Create `src/adclaw/agents/memory/tiered_compaction.py` with `plan_compaction()`.
2. Add `_compaction_cycle` and `_cycle_counts` tracking to `MemoryCompactionHook.__init__`.
3. Replace flat message split with `plan_compaction()` in the hook.
4. Integration test: simulate 3 compaction cycles, verify L0 messages survive, L2 compacted first.

### Phase 3: Topic-Clustered Summarization (3-4 hours)

1. Create `src/adclaw/agents/memory/topic_summarizer.py`.
2. Build structured prompt with topic headers, failure markers, entity preservation instructions.
3. Validate that `tiers.py` correctly classifies the structured output (DECISION/ACTION/FAILED prefixes map to high priority).
4. A/B test: compare chronological vs topic-clustered summaries on 10 real session transcripts.

### Phase 4: Cross-Session Bridge (2-3 hours)

1. Create `src/adclaw/agents/memory/session_bridge.py`.
2. On session end (`summary_memory`), extract `SessionSummary` and persist to `sessions/` directory.
3. On session start, load recent summaries and AOM memories into prior knowledge section.
4. Inject prior knowledge via `_build_sys_prompt()` or as first context message.

---

## Token Savings Estimate

Based on analysis of the current codebase constants and typical session patterns:

| Component | Current cost | With smart compaction | Savings |
|-----------|-------------|----------------------|---------|
| **Compaction input** (messages sent to LLM for summarization) | 100% of compactable window | ~60% (L0 excluded from compaction, L2 compacted with minimal summarization) | **~40%** |
| **Summary size** | ~2000 tokens (chronological blob) | ~1500 tokens (structured, deduped by topic) | **~25%** |
| **Pre-compression** (`compressor.py`) | 15-30% savings on summary | Same, but applied to smaller input | Compounds |
| **Cross-session cold start** | 0 tokens (starts fresh) | 500-2000 tokens of prior knowledge | Net cost, but avoids user repeating context |
| **Per-cycle LLM calls** | 1 call per compaction trigger | 1 call (same), but smaller input | Reduced input cost |

**Net effect:** ~30-40% reduction in LLM tokens spent on compaction, with better information retention. The cross-session bridge adds 500-2000 tokens per session start but eliminates the typical 2-5 user messages spent re-establishing context.

---

## Testing Strategy

### Unit Tests

```python
# tests/test_importance.py

import pytest
from unittest.mock import MagicMock
from agentscope.message import Msg

from adclaw.agents.memory.importance import (
    Importance,
    classify_importance,
    tag_messages,
)


def _make_msg(content: str, role: str = "user", msg_id: str = "test") -> Msg:
    """Create a minimal Msg for testing.

    Note: agentscope Msg uses content blocks (ToolUseBlock/ToolResultBlock),
    not a top-level tool_calls attribute. For text-only messages, content
    is a plain string.
    """
    msg = MagicMock(spec=Msg)
    msg.id = msg_id
    msg.role = role
    msg.content = content
    msg.get_text_content.return_value = content
    return msg


class TestClassifyImportance:
    def test_system_messages_always_critical(self):
        msg = _make_msg("You are a helpful assistant", role="system")
        assert classify_importance(msg) == Importance.CRITICAL

    def test_decision_keywords(self):
        msg = _make_msg("I decided to use glm-5 for production")
        assert classify_importance(msg) == Importance.CRITICAL

    def test_config_change_is_critical(self):
        msg = _make_msg("Config changed: max_input_length set to 64000")
        assert classify_importance(msg) == Importance.CRITICAL

    def test_error_is_high(self):
        msg = _make_msg("Error: connection refused on port 8088")
        assert classify_importance(msg) == Importance.HIGH

    def test_failed_attempt_is_high(self):
        msg = _make_msg("Tried qwen-max but it didn't work on Coding Plan")
        assert classify_importance(msg) == Importance.HIGH

    def test_acknowledgment_is_low(self):
        msg = _make_msg("ok thanks", role="user")
        assert classify_importance(msg) == Importance.LOW

    def test_short_assistant_response_is_low(self):
        msg = _make_msg("Done.", role="assistant")
        assert classify_importance(msg) == Importance.LOW

    def test_normal_message_is_medium(self):
        msg = _make_msg("Can you help me set up the deployment pipeline?")
        assert classify_importance(msg) == Importance.MEDIUM

    def test_tag_messages_returns_dict(self):
        msgs = [
            _make_msg("decided to use X", msg_id="1"),
            _make_msg("ok", msg_id="2"),
            _make_msg("error in build", msg_id="3"),
        ]
        tags = tag_messages(msgs)
        assert tags["1"] == Importance.CRITICAL
        assert tags["2"] == Importance.LOW
        assert tags["3"] == Importance.HIGH


class TestTieredCompaction:
    def test_l2_compacted_immediately(self):
        from adclaw.agents.memory.tiered_compaction import plan_compaction

        msgs = [
            _make_msg("ok thanks", msg_id="ack1"),
            _make_msg("sure", msg_id="ack2"),
            _make_msg("I decided to use glm-5", msg_id="decision1"),
        ]
        plan = plan_compaction(
            messages=msgs,
            cycle_counts={"ack1": 0, "ack2": 0, "decision1": 0},
            current_cycle=0,
        )
        # L2 (LOW) messages compacted at cycle 0 (survival=0)
        compact_ids = {m.id for m in plan.to_compact}
        assert "ack1" in compact_ids
        assert "ack2" in compact_ids
        # L0 (CRITICAL) preserved
        assert "decision1" not in compact_ids

    def test_l1_survives_two_cycles(self):
        from adclaw.agents.memory.tiered_compaction import plan_compaction

        msgs = [_make_msg("Error: connection failed", msg_id="err1")]

        # Cycle 0: should survive
        plan = plan_compaction(msgs, {"err1": 0}, current_cycle=0)
        assert len(plan.to_compact) == 0

        # Cycle 1: should still survive
        plan = plan_compaction(msgs, {"err1": 0}, current_cycle=1)
        assert len(plan.to_compact) == 0

        # Cycle 2: should be compacted
        plan = plan_compaction(msgs, {"err1": 0}, current_cycle=2)
        assert len(plan.to_compact) == 1


class TestTopicClustering:
    def test_groups_consecutive_same_topic(self):
        from adclaw.agents.memory.topic_summarizer import cluster_by_topic

        msgs = [
            _make_msg("There's a bug in the config"),
            _make_msg("Error: missing key in config.json"),
            _make_msg("Let me deploy the fix"),
        ]
        clusters = cluster_by_topic(msgs)
        # First two should cluster (debugging), third is deployment
        assert len(clusters) >= 1
        assert len(clusters) <= 3

    def test_failure_detection(self):
        from adclaw.agents.memory.topic_summarizer import cluster_by_topic

        msgs = [_make_msg("Tried X but it failed with error Y")]
        clusters = cluster_by_topic(msgs)
        assert clusters[0].has_failure is True


class TestSessionBridge:
    def test_staleness_labels(self):
        from adclaw.agents.memory.session_bridge import staleness_label
        import time

        now = time.time()
        assert staleness_label(now - 60) == "just now"
        assert "h ago" in staleness_label(now - 7200)
        assert "d ago" in staleness_label(now - 172800)
        assert "outdated" in staleness_label(now - 1209600)

    def test_empty_prior_knowledge(self):
        from adclaw.agents.memory.session_bridge import build_prior_knowledge_section

        result = build_prior_knowledge_section([], [])
        assert result == ""

    def test_aom_memories_included(self):
        from adclaw.agents.memory.session_bridge import build_prior_knowledge_section

        result = build_prior_knowledge_section(
            session_summaries=[],
            aom_memories=["glm-5 is 6x faster than qwen3.5-plus"],
        )
        assert "glm-5" in result
        assert "Prior Knowledge" in result
```

### Integration Tests

1. **Full compaction cycle:** Create a 50-message session with mixed importance. Trigger 3 compaction cycles. Verify that CRITICAL messages remain in context, LOW messages are gone after cycle 0, HIGH messages gone after cycle 2.

2. **Summary quality:** Compare summaries generated with chronological vs topic-clustered prompts using the same 50-message input. Check that the topic-clustered version preserves more entity names (file paths, config values) and explicitly mentions failures.

3. **Cross-session injection:** End a session, start a new one. Verify that `build_prior_knowledge_section()` produces output that fits within the token budget and includes decisions from the prior session.

4. **Regression:** Ensure existing `pre_compress()` and `generate_tiers()` continue to work unchanged -- the new code layers on top, it does not modify them.

### Load Testing

Run the full compaction pipeline on sessions of 100, 500, and 1000 messages. Measure:
- Wall time for `plan_compaction()` (target: <10ms for 1000 messages).
- Wall time for `cluster_by_topic()` (target: <50ms for 1000 messages).
- LLM token count sent for summarization (target: 40% reduction vs current).
