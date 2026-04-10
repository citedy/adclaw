# 1A: AOM Consolidation Upgrade -- AutoDream Pattern

## Problem Statement

Current `ConsolidationEngine` (in `src/adclaw/memory_agent/consolidate.py`) clusters
memories by semantic similarity and generates LLM insights. It works, but has
fundamental efficiency and quality gaps:

1. **No gate logic.** `ConsolidationScheduler` fires every N minutes regardless of
   activity. If no new memories arrived, it still queries the DB, embeds texts, and
   potentially calls the LLM -- wasting tokens and compute.

2. **No structured phases.** The cycle is a single pass: fetch unconsolidated ->
   cluster -> generate insight -> prune. There is no orient step (what changed since
   last run?), no explicit gather step (what old memories drifted?), and pruning is
   bolted on at the end rather than integrated.

3. **No contradiction detection.** Two memories can say opposite things about the
   same topic. Both survive indefinitely and both get cited in query results.

4. **No staleness cues.** Memories have `created_at` and `last_consolidated_at` but
   no `last_verified_at`. Old memories rank the same as fresh ones in retrieval.
   Users get no signal about how recent a cited memory is.

## Design (based on Claude Code AutoDream)

Apply Claude Code's AutoDream consolidation pattern to AdClaw's existing engine.
The key idea: consolidation is an expensive operation (LLM calls, embedding lookups)
that should only run when there is genuine new signal, and when it runs it should
follow a disciplined 4-phase protocol.

### 1. Gate Logic (cheapest first)

Before any DB query or LLM call, the scheduler checks three gates in order. If any
gate says "skip", the cycle is aborted with zero cost.

```text
Event gate  -->  Time gate  -->  Count gate  -->  Run consolidation
  (free)          (free)          (1 SQL)
```

- **Event gate**: An in-memory counter `_new_memory_count` is incremented by
  `IngestAgent` every time a memory is inserted. If zero since last consolidation,
  skip. Cost: zero (memory read).

- **Time gate**: `min_interval_seconds` (default 300). Even if there are new
  memories, don't consolidate more often than this. Cost: zero (time comparison).

- **Count gate**: `min_new_memories` (default 5). Even if the time gate passes, wait
  until at least N new memories exist. Cost: one `SELECT COUNT(*)`.

### 2. Four-Phase Consolidation

#### Phase 1: Orient

Scan the memory store for stats and recent consolidation history. This determines
what the consolidation cycle should focus on.

- Total memory count, unconsolidated count, last consolidation timestamp.
- If total memories < 2, skip (not enough data for clustering).
- NOTE: Exponential backoff is handled by `_backoff_multiplier` in the time
  gate, not here. The Orient phase only gathers stats for logging/decisions.

#### Phase 2: Gather

Collect the working set of memories to consolidate.

- **Unconsolidated memories**: `last_consolidated_at IS NULL` (existing behavior).
- **Drifted memories**: memories consolidated > 7 days ago whose topics overlap with
  recently added memories. These may need re-clustering.
- **Stale high-importance memories**: importance >= 0.7 with `last_verified_at` older
  than 14 days. Flag for re-verification during consolidation.

#### Phase 3: Consolidate

The core clustering + insight generation, enhanced with contradiction detection.

- Cluster by vector similarity (existing behavior).
- For each cluster, before generating the insight, run a lightweight contradiction
  check (see section 3 below).
- Generate insight via LLM, now including contradiction resolution instructions.
- Update `last_verified_at` for all memories touched.

#### Phase 4: Prune

Existing temporal pruning (green/yellow/red) plus:

- **Contradiction removal**: memories marked `superseded_by` in phase 3 get
  soft-deleted.
- **Orphan cleanup**: consolidation records whose source memories are all deleted.

### 3. Contradiction Detection

Two-tier approach: cheap heuristic first, LLM only when ambiguous.

**Tier 1 -- Topic overlap + sentiment divergence (no LLM)**

For memories in the same cluster that share >= 1 topic, compute a simple sentiment
signal from keywords (positive: "works", "correct", "confirmed"; negative: "broken",
"wrong", "deprecated"). If one is positive and one is negative on a shared topic,
flag as potential contradiction.

> **Limitation**: This heuristic is very naive -- typical AOM content like config
> changes ("port changed to 8088") contains none of the signal keywords. In
> practice, Tier 1 will rarely flag pairs and most contradiction detection will
> fall through to Tier 2 LLM calls. Consider expanding the keyword set or
> switching to embedding-based similarity delta as a future improvement.

**Tier 2 -- LLM arbitration**

For flagged pairs, ask the LLM:

```text
Given these two memories about the same topic:
A: {memory_a.content}
B: {memory_b.content}

Are these contradictory? If yes, which is more likely correct given their dates?
Reply: CONTRADICTORY|COMPATIBLE, KEEP: A|B|BOTH
```

The loser gets `metadata["superseded_by"] = winner.id` and is soft-deleted in the
prune phase.

### 4. Memory Staleness Cues

- Add `last_verified_at` field to `Memory` model.
- During consolidation, any memory that participates in a cluster gets its
  `last_verified_at` updated to now.
- Query results include age annotation: "5 days old", "verified 2 hours ago".
- Retrieval scoring applies a temporal decay multiplier:
  `score * decay_factor(days_since_verified)` where decay = `max(0.5, 1.0 - 0.02 * days)`.

## Implementation Plan

### models.py -- Add fields

```python
# In class Memory(BaseModel):

class Memory(BaseModel):
    """A single memory entry."""

    id: str = Field(default_factory=_uuid4)
    content: str
    content_hash: str = ""
    source_type: Literal["mcp_tool", "skill", "chat", "file_inbox", "manual"] = "manual"
    source_id: str = ""
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    importance: float = 0.5
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    is_deleted: int = 0
    last_consolidated_at: Optional[str] = None
    last_verified_at: Optional[str] = None        # NEW
    superseded_by: Optional[str] = None            # NEW — memory ID that replaces this one


class AOMConfig(BaseModel):
    """Always-On Memory configuration."""

    # ... existing fields ...

    # Gate logic (NEW)
    consolidation_min_interval_seconds: int = 300
    consolidation_min_new_memories: int = 5

    # Staleness (NEW)
    staleness_decay_rate: float = 0.02        # score penalty per day
    staleness_min_weight: float = 0.5         # floor for decay multiplier
    stale_verification_days: int = 14         # re-verify after this many days

    # Contradiction (NEW)
    contradiction_detection_enabled: bool = True
```

### store.py -- Schema migration + new queries

```python
# Add to _create_tables, after existing CREATE TABLE memories:

async def _migrate_v2(self) -> None:
    """Add v2 columns if missing (backward compatible)."""
    assert self._db is not None
    for col, typedef in [
        ("last_verified_at", "TEXT"),
        ("superseded_by", "TEXT"),
    ]:
        try:
            await self._db.execute(
                f"ALTER TABLE memories ADD COLUMN {col} {typedef}"
            )
            logger.info("Migration: added column memories.%s", col)
        except Exception:
            pass  # column already exists
    await self._db.commit()


async def count_unconsolidated(self) -> int:
    """Count memories not yet consolidated (cheap gate check)."""
    assert self._db is not None
    rows = await self._db.execute_fetchall(
        "SELECT COUNT(*) FROM memories "
        "WHERE is_deleted = 0 AND last_consolidated_at IS NULL"
    )
    return rows[0][0]


async def get_drifted_memories(
    self, recent_topics: List[str], older_than_days: int = 7, limit: int = 30
) -> List[Memory]:
    """Find consolidated memories older than N days whose topics overlap
    with recently active topics. These may need re-clustering."""
    assert self._db is not None
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    cutoff_str = cutoff.isoformat()

    rows = await self._db.execute_fetchall(
        "SELECT * FROM memories WHERE is_deleted = 0 "
        "AND last_consolidated_at IS NOT NULL "
        "AND last_consolidated_at < ? "
        "ORDER BY importance DESC LIMIT ?",
        (cutoff_str, limit * 3),  # over-fetch, filter in Python
    )
    results = []
    topic_set = set(t.lower() for t in recent_topics)
    for r in rows:
        mem = self._row_to_memory(r)
        mem_topics = set(t.lower() for t in mem.topics)
        if mem_topics & topic_set:
            results.append(mem)
            if len(results) >= limit:
                break
    return results


async def get_stale_important_memories(
    self, stale_days: int = 14, min_importance: float = 0.7, limit: int = 20
) -> List[Memory]:
    """Find high-importance memories not verified recently."""
    assert self._db is not None
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    cutoff_str = cutoff.isoformat()

    rows = await self._db.execute_fetchall(
        "SELECT * FROM memories WHERE is_deleted = 0 "
        "AND importance >= ? "
        "AND (last_verified_at IS NULL OR last_verified_at < ?) "
        "ORDER BY importance DESC LIMIT ?",
        (min_importance, cutoff_str, limit),
    )
    return [self._row_to_memory(r) for r in rows]


async def mark_verified(self, memory_ids: List[str]) -> None:
    """Update last_verified_at for a batch of memories."""
    assert self._db is not None
    now = _utcnow()
    for mid in memory_ids:
        await self._db.execute(
            "UPDATE memories SET last_verified_at = ? WHERE id = ?",
            (now, mid),
        )
    await self._db.commit()


async def mark_superseded(self, loser_id: str, winner_id: str) -> None:
    """Soft-delete a contradicted memory, recording what superseded it."""
    assert self._db is not None
    now = _utcnow()
    await self._db.execute(
        "UPDATE memories SET superseded_by = ?, is_deleted = 1, updated_at = ? "
        "WHERE id = ?",
        (winner_id, now, loser_id),
    )
    await self._db.commit()


async def cleanup_orphan_consolidations(self) -> int:
    """Delete consolidation records whose source memories are all deleted.

    NOTE: This is an N+1 query pattern -- for each consolidation, it loads
    every source memory individually.  Acceptable for now since consolidation
    count is typically low (< 100), but if it grows, replace with a single
    SQL query joining consolidations against memories.
    """
    assert self._db is not None
    cons = await self.list_consolidations(limit=500)
    deleted = 0
    for c in cons:
        all_gone = True
        for mid in c.memory_ids:
            mem = await self.get_memory(mid)
            if mem and not mem.is_deleted:
                all_gone = False
                break
        if all_gone:
            await self._db.execute(
                "DELETE FROM consolidations WHERE id = ?", (c.id,)
            )
            deleted += 1
    if deleted:
        await self._db.commit()
    return deleted
```

Update `_row_to_memory` to handle the new columns:

```python
@staticmethod
def _row_to_memory(row) -> Memory:
    # row_factory = aiosqlite.Row, so use named access for robustness.
    # Positional indices break if any future migration inserts columns
    # between existing ones.
    kwargs = dict(
        id=row["id"],
        content=row["content"],
        content_hash=row["content_hash"] or "",
        source_type=row["source_type"],
        source_id=row["source_id"] or "",
        entities=json.loads(row["entities"]) if row["entities"] else [],
        topics=json.loads(row["topics"]) if row["topics"] else [],
        importance=float(row["importance"]),
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_deleted=int(row["is_deleted"]),
        last_consolidated_at=row["last_consolidated_at"],
    )
    # v2 columns (may not exist in older DBs before _migrate_v2 runs)
    try:
        kwargs["last_verified_at"] = row["last_verified_at"]
    except (IndexError, KeyError):
        pass
    try:
        kwargs["superseded_by"] = row["superseded_by"]
    except (IndexError, KeyError):
        pass
    return Memory(**kwargs)
```

> **Note**: The existing v1 `_row_to_memory` uses positional indices (`row[0]`,
> `row[1]`, etc.). Since `row_factory = aiosqlite.Row` is set in `initialize()`,
> `Row` objects support both positional and named access. The v2 code switches to
> named access for safety. This is backward compatible -- `aiosqlite.Row` has
> supported key access since v0.17.

### consolidate.py -- Rewritten ConsolidationEngine

```python
"""ConsolidationEngine v2 -- AutoDream pattern with gate logic,
4-phase consolidation, contradiction detection, and staleness cues."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from .embeddings import EmbeddingPipeline
from .models import AOMConfig, Consolidation, Memory
from .store import MemoryStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CONSOLIDATE_PROMPT = """You are analyzing a cluster of related memory entries.
Generate a concise insight that synthesizes the key information from these memories.

Memories:
{memories}

If any memories contradict each other, note the contradiction and state which
information is more likely current/correct based on dates.

Write a single concise insight paragraph (2-4 sentences) that captures the most
important information, patterns, or connections. Rate its importance 0.0-1.0.

Format your response as:
INSIGHT: <your insight>
IMPORTANCE: <float>"""

_CONTRADICTION_PROMPT = """Given these two memories about the same topic:

Memory A (created {date_a}):
{content_a}

Memory B (created {date_b}):
{content_b}

Are these contradictory? If yes, which is more likely correct given their dates
and specificity?

Reply in EXACTLY this format:
VERDICT: CONTRADICTORY or COMPATIBLE
KEEP: A or B or BOTH
REASON: <one sentence>"""

# ---------------------------------------------------------------------------
# Sentiment keywords for cheap contradiction pre-filter
# ---------------------------------------------------------------------------

_POSITIVE_SIGNALS = frozenset({
    "works", "correct", "confirmed", "enabled", "active", "true",
    "success", "valid", "resolved", "fixed", "upgraded",
})
_NEGATIVE_SIGNALS = frozenset({
    "broken", "wrong", "deprecated", "disabled", "inactive", "false",
    "failed", "invalid", "error", "removed", "downgraded",
})


def _cheap_sentiment(text: str) -> Optional[bool]:
    """Return True for positive, False for negative, None for neutral."""
    words = set(text.lower().split())
    pos = len(words & _POSITIVE_SIGNALS)
    neg = len(words & _NEGATIVE_SIGNALS)
    if pos > neg:
        return True
    if neg > pos:
        return False
    return None


class ConsolidationEngine:
    """Finds related memories, clusters them, generates LLM insights.

    v2 additions:
    - Gate logic (event/time/count) to skip unnecessary cycles
    - 4-phase consolidation (orient/gather/consolidate/prune)
    - Contradiction detection (heuristic + LLM)
    - Staleness tracking (last_verified_at)
    """

    def __init__(
        self,
        store: MemoryStore,
        embedder: EmbeddingPipeline,
        llm_caller: Callable[[str], Coroutine[Any, Any, str]],
        config: Optional[AOMConfig] = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.llm_caller = llm_caller
        self.config = config or AOMConfig()

        # Gate state
        self._new_memory_count: int = 0
        self._last_consolidation_ts: float = 0.0
        self._backoff_multiplier: float = 1.0

    # ------ Public: called by IngestAgent on every insert ------

    def notify_new_memory(self) -> None:
        """Increment the event counter. Zero-cost signal for the event gate."""
        self._new_memory_count += 1

    # ------ Gate logic ------

    async def _should_run(self) -> bool:
        """Check gates in order: event -> time -> count. Return True to proceed."""
        # Gate 1: Event gate (free)
        if self._new_memory_count == 0:
            logger.debug("Consolidation gate: no new memories, skipping")
            return False

        # Gate 2: Time gate (free)
        min_interval = (
            self.config.consolidation_min_interval_seconds * self._backoff_multiplier
        )
        elapsed = time.monotonic() - self._last_consolidation_ts
        if elapsed < min_interval:
            logger.debug(
                "Consolidation gate: too soon (%.0fs < %.0fs), skipping",
                elapsed, min_interval,
            )
            return False

        # Gate 3: Count gate (one SQL query)
        min_count = self.config.consolidation_min_new_memories
        actual = await self.store.count_unconsolidated()
        if actual < min_count:
            logger.debug(
                "Consolidation gate: not enough new memories (%d < %d), skipping",
                actual, min_count,
            )
            return False

        return True

    # ------ Main cycle ------

    async def run_consolidation_cycle(self) -> List[Consolidation]:
        """Run one full 4-phase consolidation cycle with gate checks."""

        # --- Gates ---
        if not await self._should_run():
            return []

        self._last_consolidation_ts = time.monotonic()

        # --- Phase 1: Orient ---
        stats = await self.store.get_stats()
        total = stats["total_memories"]
        if total < 2:
            logger.debug("Orient: fewer than 2 memories total, skipping")
            return []

        logger.info(
            "Consolidation orient: %d total memories, %d consolidations",
            total, stats["consolidations"],
        )

        # --- Phase 2: Gather ---
        unconsolidated = await self.store.get_unconsolidated_memories(limit=50)

        # Collect recent topics for drift detection
        recent_topics: List[str] = []
        for mem in unconsolidated:
            recent_topics.extend(mem.topics)

        drifted: List[Memory] = []
        if recent_topics:
            drifted = await self.store.get_drifted_memories(
                recent_topics, older_than_days=7, limit=20
            )

        stale = await self.store.get_stale_important_memories(
            stale_days=self.config.stale_verification_days,
            min_importance=0.7,
            limit=20,
        )

        # Merge working set (dedup by ID)
        seen_ids: set[str] = set()
        working_set: List[Memory] = []
        for mem in unconsolidated + drifted + stale:
            if mem.id not in seen_ids:
                working_set.append(mem)
                seen_ids.add(mem.id)

        if len(working_set) < 2:
            logger.debug("Gather: working set too small (%d), skipping", len(working_set))
            self._backoff_multiplier = min(self._backoff_multiplier * 1.5, 8.0)
            return []

        logger.info(
            "Consolidation gather: %d unconsolidated, %d drifted, %d stale -> %d working set",
            len(unconsolidated), len(drifted), len(stale), len(working_set),
        )

        # --- Phase 3: Consolidate ---
        clusters = await self._build_clusters(working_set)

        results: List[Consolidation] = []
        all_touched_ids: List[str] = []

        for cluster_ids in clusters:
            # Contradiction detection within cluster
            if self.config.contradiction_detection_enabled:
                await self._detect_contradictions(cluster_ids)

            # Generate insight
            try:
                insight = await self._generate_insight(cluster_ids)
                if insight:
                    results.append(insight)
                    await self.store.mark_consolidated(cluster_ids)
                    all_touched_ids.extend(cluster_ids)
            except Exception as exc:
                logger.warning("Insight generation failed: %s", exc)

        # Update last_verified_at for all touched memories
        if all_touched_ids:
            await self.store.mark_verified(all_touched_ids)

        logger.info(
            "Consolidation: %d clusters -> %d insights", len(clusters), len(results)
        )

        # --- Phase 4: Prune ---
        try:
            prune_stats = await temporal_prune(self.store)
            if prune_stats["deleted"] > 0 or prune_stats["condensed"] > 0:
                logger.info(
                    "Temporal pruning: deleted=%d, condensed=%d, kept=%d",
                    prune_stats["deleted"],
                    prune_stats["condensed"],
                    prune_stats["kept"],
                )
        except Exception as exc:
            logger.warning("Temporal pruning failed: %s", exc)

        # Orphan consolidation cleanup
        try:
            orphans = await self.store.cleanup_orphan_consolidations()
            if orphans:
                logger.info("Cleaned up %d orphan consolidations", orphans)
        except Exception as exc:
            logger.warning("Orphan cleanup failed: %s", exc)

        # Reset backoff on successful cycle with results
        if results:
            self._backoff_multiplier = 1.0
        else:
            self._backoff_multiplier = min(self._backoff_multiplier * 1.5, 8.0)

        # Reset counter only after the full cycle completes successfully.
        # If reset earlier (before orient/gather/consolidate), a thrown
        # exception would lose the signal that new memories arrived.
        self._new_memory_count = 0

        return results

    # ------ Clustering ------

    async def _build_clusters(
        self, memories: List[Memory]
    ) -> List[List[str]]:
        """Build clusters by vector similarity (same algorithm as v1)."""
        clusters: List[List[str]] = []
        seen: set[str] = set()

        for mem in memories:
            if mem.id in seen:
                continue

            try:
                vec = await self.embedder.embed(mem.content)
                neighbors = await self.store.vector_search(vec, limit=5)
            except Exception:
                continue

            cluster_ids = [mem.id]
            for neighbor_id, dist in neighbors:
                if neighbor_id != mem.id and neighbor_id not in seen:
                    cluster_ids.append(neighbor_id)

            if len(cluster_ids) >= 2:
                clusters.append(cluster_ids)
                seen.update(cluster_ids)

        return clusters

    # ------ Contradiction detection ------

    async def _detect_contradictions(self, cluster_ids: List[str]) -> None:
        """Two-tier contradiction detection within a cluster.

        Tier 1: cheap heuristic (topic overlap + sentiment divergence).
        Tier 2: LLM arbitration for flagged pairs.
        """
        # Load memories
        mems: List[Memory] = []
        for mid in cluster_ids:
            mem = await self.store.get_memory(mid)
            if mem:
                mems.append(mem)

        if len(mems) < 2:
            return

        # Tier 1: find candidate contradiction pairs
        candidates: List[Tuple[Memory, Memory]] = []
        for i, a in enumerate(mems):
            for b in mems[i + 1:]:
                # Check topic overlap (>= 1 shared topic is sufficient)
                shared_topics = set(t.lower() for t in a.topics) & set(
                    t.lower() for t in b.topics
                )
                if not shared_topics:
                    continue

                sent_a = _cheap_sentiment(a.content)
                sent_b = _cheap_sentiment(b.content)

                # Opposite sentiments on shared topic
                if sent_a is not None and sent_b is not None and sent_a != sent_b:
                    candidates.append((a, b))

        if not candidates:
            return

        logger.info(
            "Contradiction detection: %d candidate pairs in cluster", len(candidates)
        )

        # Tier 2: LLM arbitration (limit to 3 pairs per cycle to control cost)
        for a, b in candidates[:3]:
            try:
                await self._resolve_contradiction(a, b)
            except Exception as exc:
                logger.warning("Contradiction resolution failed: %s", exc)

    async def _resolve_contradiction(self, a: Memory, b: Memory) -> None:
        """Ask LLM which memory to keep and mark loser as superseded."""
        prompt = _CONTRADICTION_PROMPT.format(
            date_a=a.created_at[:10],
            content_a=a.content[:500],
            date_b=b.created_at[:10],
            content_b=b.content[:500],
        )
        raw = await self.llm_caller(prompt)

        verdict = "COMPATIBLE"
        keep = "BOTH"
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                verdict = line.split(":", 1)[1].strip().upper()
            elif line.startswith("KEEP:"):
                keep = line.split(":", 1)[1].strip().upper()

        if "CONTRADICTORY" not in verdict or keep == "BOTH":
            return

        if keep == "A":
            await self.store.mark_superseded(b.id, a.id)
            logger.info("Contradiction resolved: %s superseded by %s", b.id[:8], a.id[:8])
        elif keep == "B":
            await self.store.mark_superseded(a.id, b.id)
            logger.info("Contradiction resolved: %s superseded by %s", a.id[:8], b.id[:8])

    # ------ Insight generation (same as v1, enhanced prompt) ------

    async def _generate_insight(
        self, memory_ids: List[str]
    ) -> Optional[Consolidation]:
        """Generate an insight from a cluster of memory IDs."""
        memories_text = []
        for mid in memory_ids:
            mem = await self.store.get_memory(mid)
            if mem:
                memories_text.append(
                    f"- [{mem.source_type}/{mem.source_id}] {mem.content[:500]}"
                )

        if not memories_text:
            return None

        prompt = _CONSOLIDATE_PROMPT.format(memories="\n".join(memories_text))
        raw = await self.llm_caller(prompt)

        insight_text = raw.strip()
        importance = 0.5
        for line in raw.strip().split("\n"):
            if line.startswith("INSIGHT:"):
                insight_text = line[len("INSIGHT:"):].strip()
            elif line.startswith("IMPORTANCE:"):
                try:
                    importance = float(line[len("IMPORTANCE:"):].strip())
                except ValueError:
                    pass

        consolidation = Consolidation(
            insight=insight_text,
            memory_ids=memory_ids,
            importance=importance,
        )
        return await self.store.insert_consolidation(consolidation)


# ---------------------------------------------------------------------------
# Temporal Pruning (unchanged from v1, included for completeness)
# ---------------------------------------------------------------------------

# Must match Memory.source_type Literal: "mcp_tool", "skill", "chat", "file_inbox", "manual"
# WARNING: v1 used {"note", "info", "chat", "manual"} and {"decision", "critical",
# "config", "error"} which don't match actual source_type values.  Fixed here.
_GREEN_TYPES = {"chat", "manual"}
_RED_TYPES = {"skill", "mcp_tool"}  # tool/skill outputs are more durable than chat
_GREEN_MAX_DAYS = 7
_YELLOW_MAX_DAYS = 30


def _classify_memory_color(mem: Memory) -> str:
    st = mem.source_type.lower()
    if st in _RED_TYPES or mem.importance >= 0.8:
        return "red"
    if st in _GREEN_TYPES and mem.importance < 0.5:
        return "green"
    return "yellow"


def _memory_age_days(mem: Memory) -> float:
    try:
        created = datetime.fromisoformat(mem.created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - created).total_seconds() / 86400
    except Exception:
        return 0.0


async def temporal_prune(store: MemoryStore) -> Dict[str, int]:
    """Age-based pruning (green/yellow/red) + superseded memory cleanup."""
    stats = {"deleted": 0, "condensed": 0, "kept": 0}
    memories = await store.list_memories(limit=500, min_importance=0.0)

    for mem in memories:
        # v2: skip already-superseded (should be deleted, but safety net)
        if mem.superseded_by:
            await store.delete_memory(mem.id, hard=False)
            stats["deleted"] += 1
            continue

        color = _classify_memory_color(mem)
        age = _memory_age_days(mem)

        if color == "red":
            stats["kept"] += 1
            continue

        if color == "green" and age > _GREEN_MAX_DAYS:
            await store.delete_memory(mem.id, hard=False)
            stats["deleted"] += 1
        elif color == "yellow" and age > _YELLOW_MAX_DAYS:
            first_line = mem.content.split("\n")[0][:200]
            if len(first_line) < len(mem.content):
                await store.update_memory_content(mem.id, first_line)
                stats["condensed"] += 1
            else:
                stats["kept"] += 1
        else:
            stats["kept"] += 1

    return stats


# ---------------------------------------------------------------------------
# Scheduler (updated for gate-aware cycle)
# ---------------------------------------------------------------------------

class ConsolidationScheduler:
    """Runs consolidation cycles on a schedule.

    v2: The engine itself handles gate logic, so the scheduler just needs to
    call run_consolidation_cycle frequently. The engine will skip when gates
    don't pass. We use a shorter poll interval (30s) since the gates are cheap.
    """

    def __init__(
        self,
        engine: ConsolidationEngine,
        interval_minutes: int = 60,
    ) -> None:
        self.engine = engine
        # v2: poll every 30 seconds, gates handle the real throttling
        self._poll_interval = 30
        # Keep interval_minutes for backward compat (used as max backoff ceiling)
        self.interval_minutes = interval_minutes
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Consolidation scheduler started (poll every %ds)", self._poll_interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                await self.engine.run_consolidation_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Consolidation cycle error: %s", exc)
```

### query.py -- Staleness-aware scoring

Add temporal decay to retrieval results:

```python
import math
from datetime import datetime, timezone


def staleness_weight(
    last_verified_at: Optional[str],
    created_at: str,
    decay_rate: float = 0.02,
    min_weight: float = 0.5,
) -> float:
    """Compute a decay multiplier based on memory freshness.

    Uses last_verified_at if available, otherwise falls back to created_at.
    Returns a float in [min_weight, 1.0].
    """
    ref = last_verified_at or created_at
    try:
        ref_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - ref_dt).total_seconds() / 86400
        return max(min_weight, 1.0 - decay_rate * days)
    except Exception:
        return 1.0


def format_age_annotation(memory: Memory) -> str:
    """Return a human-readable age string for display in query results."""
    ref = memory.last_verified_at or memory.created_at
    try:
        ref_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ref_dt
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return "just now"
        if hours < 24:
            return f"{int(hours)}h ago"
        days = int(hours / 24)
        if days == 1:
            return "1 day ago"
        if days < 30:
            return f"{days} days ago"
        return f"{days // 30}mo ago"
    except Exception:
        return "unknown age"


# In QueryAgent._hybrid_search, after combining scores:
# Apply staleness weight:
#   final_score = raw_score * staleness_weight(
#       mem.last_verified_at, mem.created_at,
#       self.config.staleness_decay_rate, self.config.staleness_min_weight,
#   )
```

### manager.py -- Wire up notify_new_memory

In `AOMManager.start()`, after creating the `ConsolidationEngine`, pass a reference
to `IngestAgent` so it can call `engine.notify_new_memory()`:

```python
# In AOMManager.start(), after creating consolidation_engine:
if self.ingest_agent and self.consolidation_engine:
    self.ingest_agent.on_memory_inserted = self.consolidation_engine.notify_new_memory
```

In `IngestAgent`, add the callback hook:

```python
class IngestAgent:
    def __init__(self, ...):
        ...
        self.on_memory_inserted: Optional[Callable[[], None]] = None

    async def _store_memory(self, memory: Memory, embedding=None) -> Memory:
        result = await self.store.insert_memory(memory, embedding)
        if self.on_memory_inserted:
            self.on_memory_inserted()
        return result
```

## Testing Strategy

### Unit tests (no LLM, no DB)

```python
# test_consolidation_gates.py

import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from adclaw.memory_agent.consolidate import ConsolidationEngine, _cheap_sentiment
from adclaw.memory_agent.models import AOMConfig


@pytest.fixture
def engine():
    store = AsyncMock()
    embedder = AsyncMock()
    llm = AsyncMock(return_value="INSIGHT: test\nIMPORTANCE: 0.7")
    config = AOMConfig(
        consolidation_min_interval_seconds=10,
        consolidation_min_new_memories=3,
    )
    return ConsolidationEngine(store, embedder, llm, config)


class TestEventGate:
    @pytest.mark.asyncio
    async def test_skip_when_no_new_memories(self, engine):
        """Should skip when _new_memory_count is 0."""
        assert await engine._should_run() is False

    @pytest.mark.asyncio
    async def test_pass_when_new_memories_exist(self, engine):
        """Should proceed past event gate when memories were added."""
        engine.notify_new_memory()
        engine.notify_new_memory()
        engine.notify_new_memory()
        engine.store.count_unconsolidated = AsyncMock(return_value=5)
        assert await engine._should_run() is True


class TestTimeGate:
    @pytest.mark.asyncio
    async def test_skip_when_too_recent(self, engine):
        """Should skip when last consolidation was too recent."""
        engine._new_memory_count = 10
        engine._last_consolidation_ts = time.monotonic()  # just now
        assert await engine._should_run() is False


class TestCountGate:
    @pytest.mark.asyncio
    async def test_skip_when_too_few(self, engine):
        """Should skip when unconsolidated count < min_new_memories."""
        engine._new_memory_count = 10
        engine._last_consolidation_ts = 0  # long ago
        engine.store.count_unconsolidated = AsyncMock(return_value=1)
        assert await engine._should_run() is False


class TestCheapSentiment:
    def test_positive(self):
        assert _cheap_sentiment("the feature works correctly") is True

    def test_negative(self):
        assert _cheap_sentiment("the API is broken and deprecated") is False

    def test_neutral(self):
        assert _cheap_sentiment("the system uses SQLite") is None


class TestBackoff:
    @pytest.mark.asyncio
    async def test_backoff_increases_on_empty_cycle(self, engine):
        """Backoff multiplier should increase when cycle produces no insights."""
        engine._new_memory_count = 10
        engine._last_consolidation_ts = 0
        engine.store.count_unconsolidated = AsyncMock(return_value=10)
        engine.store.get_stats = AsyncMock(return_value={
            "total_memories": 5, "consolidations": 0, "by_source": {}
        })
        engine.store.get_unconsolidated_memories = AsyncMock(return_value=[])
        engine.store.get_drifted_memories = AsyncMock(return_value=[])
        engine.store.get_stale_important_memories = AsyncMock(return_value=[])

        await engine.run_consolidation_cycle()
        assert engine._backoff_multiplier > 1.0
```

### Integration tests (real SQLite, mock LLM)

```python
# test_consolidation_integration.py

import pytest
import tempfile
from pathlib import Path
from adclaw.memory_agent.store import MemoryStore
from adclaw.memory_agent.models import Memory, AOMConfig
from adclaw.memory_agent.consolidate import ConsolidationEngine
from unittest.mock import AsyncMock


@pytest.fixture
async def store():
    with tempfile.TemporaryDirectory() as d:
        s = MemoryStore(Path(d) / "test.db")
        await s.initialize()
        await s._migrate_v2()
        yield s
        await s.close()


@pytest.mark.asyncio
async def test_full_cycle_with_contradictions(store):
    """Insert contradictory memories, run cycle, verify one is superseded."""
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 384)

    llm = AsyncMock(side_effect=[
        # First call: contradiction check
        "VERDICT: CONTRADICTORY\nKEEP: B\nREASON: B is newer",
        # Second call: insight generation
        "INSIGHT: Config uses port 8088\nIMPORTANCE: 0.8",
    ])

    m1 = Memory(
        content="The server runs on port 3000",
        topics=["server", "port"],
        importance=0.6,
    )
    m2 = Memory(
        content="The server port was changed to 8088",
        topics=["server", "port"],
        importance=0.6,
    )
    await store.insert_memory(m1, [0.1] * 384)
    await store.insert_memory(m2, [0.1] * 384)

    engine = ConsolidationEngine(
        store, embedder, llm,
        AOMConfig(
            consolidation_min_interval_seconds=0,
            consolidation_min_new_memories=1,
            contradiction_detection_enabled=True,
        ),
    )
    engine._new_memory_count = 2

    results = await engine.run_consolidation_cycle()

    # Verify m1 was superseded
    m1_after = await store.get_memory(m1.id)
    assert m1_after.is_deleted == 1 or m1_after.superseded_by == m2.id


@pytest.mark.asyncio
async def test_staleness_weight():
    """Verify temporal decay math."""
    from adclaw.memory_agent.query import staleness_weight

    # Fresh memory: weight ~1.0
    from adclaw.memory_agent.models import _utcnow
    w = staleness_weight(_utcnow(), _utcnow(), decay_rate=0.02, min_weight=0.5)
    assert w > 0.99

    # 25 days old: weight = max(0.5, 1.0 - 0.02*25) = 0.5
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(days=25)).isoformat()
    w = staleness_weight(old, old, decay_rate=0.02, min_weight=0.5)
    assert 0.49 <= w <= 0.51
```

## Migration (backward compatible)

The upgrade is fully backward compatible with existing AOM databases:

1. **Schema migration**: `_migrate_v2()` uses `ALTER TABLE ADD COLUMN` which is a
   no-op if the column already exists. Called during `MemoryStore.initialize()`.

2. **`_row_to_memory` safety**: New columns are accessed via try/except on named
   keys (not positional indices). `aiosqlite.Row` supports both access modes.
   Existing databases with 13 columns work without migration since missing keys
   fall through to the except clause.

3. **Gate state is in-memory only**: `_new_memory_count`, `_last_consolidation_ts`,
   and `_backoff_multiplier` reset on restart. This is intentional -- on startup,
   the first timer tick will find unconsolidated memories and process them.

4. **New `AOMConfig` fields have defaults**: All new config fields
   (`consolidation_min_interval_seconds`, `consolidation_min_new_memories`,
   `staleness_decay_rate`, etc.) have sensible defaults. Existing `config.json` files
   that lack these keys will use defaults automatically via Pydantic.

5. **Rollback plan**: If issues arise, revert `consolidate.py` to v1. The new DB
   columns (`last_verified_at`, `superseded_by`) are nullable and ignored by v1 code.
   No data loss.

### Migration sequence

```text
1. Deploy new code (models.py, store.py, consolidate.py, query.py, manager.py)
2. On first start, _migrate_v2() adds columns (< 1ms, no table rebuild)
3. ConsolidationScheduler polls every 30s instead of sleeping 60min
4. Gates prevent unnecessary work until real activity arrives
5. First cycle with enough new memories triggers 4-phase consolidation
6. Existing memories get last_verified_at populated as they participate in clusters
```

No manual migration steps required. No downtime.
