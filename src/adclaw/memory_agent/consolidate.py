# -*- coding: utf-8 -*-
"""ConsolidationEngine — finds patterns across memories and generates insights."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .embeddings import EmbeddingPipeline
from .models import AOMConfig, Consolidation, Memory
from .store import MemoryStore

logger = logging.getLogger(__name__)

_CONSOLIDATE_PROMPT = """You are analyzing a cluster of related memory entries.
Generate a concise insight that synthesizes the key information from these memories.

Memories:
{memories}

Write a single concise insight paragraph (2-4 sentences) that captures the most important information, patterns, or connections across these memories. Rate its importance 0.0-1.0.

Format your response as:
INSIGHT: <your insight>
IMPORTANCE: <float>"""


class ConsolidationEngine:
    """Finds related memories, clusters them, and generates LLM insights."""

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

    async def run_consolidation_cycle(self) -> List[Consolidation]:
        """Run one consolidation cycle: find clusters → generate insights."""
        memories = await self.store.get_unconsolidated_memories(limit=50)
        if len(memories) < 2:
            logger.debug("Consolidation: fewer than 2 unconsolidated memories, skipping")
            return []

        # Build clusters by finding neighbors for each memory
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

        # Generate insights for each cluster
        results: List[Consolidation] = []
        for cluster_ids in clusters:
            try:
                insight = await self._generate_insight(cluster_ids)
                if insight:
                    results.append(insight)
                    await self.store.mark_consolidated(cluster_ids)
            except Exception as exc:
                logger.warning("Insight generation failed: %s", exc)

        logger.info("Consolidation: %d clusters → %d insights", len(clusters), len(results))

        # R4: Temporal pruning — age-based cleanup
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

        return results

    async def _generate_insight(self, memory_ids: List[str]) -> Optional[Consolidation]:
        """Generate an insight from a cluster of memory IDs."""
        memories_text = []
        for mid in memory_ids:
            mem = await self.store.get_memory(mid)
            if mem:
                memories_text.append(f"- [{mem.source_type}/{mem.source_id}] {mem.content[:500]}")

        if not memories_text:
            return None

        prompt = _CONSOLIDATE_PROMPT.format(memories="\n".join(memories_text))
        raw = await self.llm_caller(prompt)

        # Parse response
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
# R4: Temporal Pruning
# ---------------------------------------------------------------------------

# Classification: green (ephemeral), yellow (useful), red (critical)
_GREEN_TYPES = {"note", "info", "chat", "manual"}
_RED_TYPES = {"decision", "critical", "config", "error"}
_GREEN_MAX_DAYS = 7
_YELLOW_MAX_DAYS = 30


def _classify_memory_color(mem: Memory) -> str:
    """Classify memory into green/yellow/red by source_type and importance."""
    st = mem.source_type.lower()
    if st in _RED_TYPES or mem.importance >= 0.8:
        return "red"
    if st in _GREEN_TYPES and mem.importance < 0.5:
        return "green"
    return "yellow"


def _memory_age_days(mem: Memory) -> float:
    """Calculate age in days from created_at string."""
    try:
        created = datetime.fromisoformat(mem.created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - created).total_seconds() / 86400
    except Exception:
        return 0.0


async def temporal_prune(store: MemoryStore) -> Dict[str, int]:
    """Age-based pruning: delete old green, condense old yellow, keep red.

    Returns:
        Stats dict with counts: deleted, condensed, kept.
    """
    stats = {"deleted": 0, "condensed": 0, "kept": 0}
    memories = await store.list_memories(limit=500, min_importance=0.0)

    for mem in memories:
        color = _classify_memory_color(mem)
        age = _memory_age_days(mem)

        if color == "red":
            stats["kept"] += 1
            continue

        if color == "green" and age > _GREEN_MAX_DAYS:
            await store.delete_memory(mem.id, hard=False)
            stats["deleted"] += 1
        elif color == "yellow" and age > _YELLOW_MAX_DAYS:
            # Condense to first line only
            first_line = mem.content.split("\n")[0][:200]
            if len(first_line) < len(mem.content):
                await store.update_memory_content(mem.id, first_line)
                stats["condensed"] += 1
            else:
                stats["kept"] += 1
        else:
            stats["kept"] += 1

    return stats


class ConsolidationScheduler:
    """Runs consolidation cycles on a schedule."""

    def __init__(
        self,
        engine: ConsolidationEngine,
        interval_minutes: int = 60,
    ) -> None:
        self.engine = engine
        self.interval_minutes = interval_minutes
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("Consolidation scheduler started (every %d min)", self.interval_minutes)

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
            await asyncio.sleep(self.interval_minutes * 60)
            try:
                await self.engine.run_consolidation_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Consolidation cycle error: %s", exc)
