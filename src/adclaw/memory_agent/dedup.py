# -*- coding: utf-8 -*-
"""Near-duplicate detection using shingle-hash Jaccard similarity.

SHA-256 catches exact duplicates but misses paraphrases and minor edits.
This module uses k-word shingling + Jaccard coefficient to detect
semantically similar content.

Adapted from claw-compactor (github.com/aeromomo/claw-compactor).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def shingles(text: str, k: int = 2) -> Set[int]:
    """Generate k-word shingle hashes from text.

    Uses k=2 by default (bigrams) for better paraphrase detection.
    Pure word-order-dependent: "A B C" and "C B A" produce different shingles.

    Args:
        text: Input text.
        k: Number of words per shingle.

    Returns:
        Set of shingle hashes.
    """
    words = text.lower().split()
    if len(words) < k:
        return {hash(text.lower().strip())} if text.strip() else set()
    return {hash(" ".join(words[i:i + k])) for i in range(len(words) - k + 1)}


def word_overlap(text_a: str, text_b: str) -> float:
    """Word-level Jaccard (bag-of-words, order-independent).

    Better for paraphrase detection where word order changes but
    vocabulary stays similar.
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


def jaccard(a: Set[int], b: Set[int]) -> float:
    """Jaccard similarity coefficient between two sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


class ShingleCache:
    """LRU-style cache for shingle sets to avoid recomputation."""

    def __init__(self, max_size: int = 200) -> None:
        self._cache: Dict[str, Set[int]] = {}
        self._order: List[str] = []
        self._max_size = max_size

    def get_or_compute(self, key: str, text: str, k: int = 3) -> Set[int]:
        if key in self._cache:
            return self._cache[key]
        s = shingles(text, k)
        self._cache[key] = s
        self._order.append(key)
        # Evict oldest if over capacity
        while len(self._order) > self._max_size:
            old_key = self._order.pop(0)
            self._cache.pop(old_key, None)
        return s

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)
        try:
            self._order.remove(key)
        except ValueError:
            pass


def find_near_duplicate(
    new_content: str,
    existing_entries: List[Tuple[str, str]],
    threshold: float = 0.6,
    k: int = 2,
    cache: Optional[ShingleCache] = None,
) -> Optional[str]:
    """Check if new_content is near-duplicate of any existing entry.

    Uses hybrid scoring: max(shingle_jaccard, word_overlap).
    Shingle Jaccard catches copy-paste edits; word overlap catches
    paraphrases where word order changes but vocabulary is similar.

    Args:
        new_content: Content to check.
        existing_entries: List of (id, content) tuples to compare against.
        threshold: Similarity threshold (0.0-1.0). Default 0.6.
        k: Shingle size in words.
        cache: Optional ShingleCache for performance.

    Returns:
        ID of the matching existing entry, or None if no near-duplicate found.
    """
    new_shingles = shingles(new_content, k)
    if not new_shingles:
        return None

    for entry_id, entry_content in existing_entries:
        if cache:
            entry_shingles = cache.get_or_compute(entry_id, entry_content, k)
        else:
            entry_shingles = shingles(entry_content, k)

        # Hybrid: max of shingle-based and word-overlap similarity
        shingle_sim = jaccard(new_shingles, entry_shingles)
        word_sim = word_overlap(new_content, entry_content)
        sim = max(shingle_sim, word_sim)

        if sim >= threshold:
            logger.debug(
                "Near-duplicate: sim=%.3f (shingle=%.3f, word=%.3f, "
                "threshold=%.2f) with %s",
                sim, shingle_sim, word_sim, threshold, entry_id,
            )
            return entry_id

    return None


def find_duplicate_groups(
    entries: List[Tuple[str, str]],
    threshold: float = 0.6,
    k: int = 3,
) -> List[List[str]]:
    """Find groups of near-duplicate entries (O(n^2) pairwise).

    Args:
        entries: List of (id, content) tuples.
        threshold: Jaccard similarity threshold.
        k: Shingle size.

    Returns:
        List of groups, each group is a list of entry IDs.
    """
    n = len(entries)
    shingle_sets = [shingles(content, k) for _, content in entries]

    # Union-Find for grouping
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(shingle_sets[i], shingle_sets[j]) >= threshold:
                union(i, j)

    # Collect groups
    groups_map: Dict[int, List[str]] = {}
    for i in range(n):
        root = find(i)
        groups_map.setdefault(root, []).append(entries[i][0])

    return [g for g in groups_map.values() if len(g) > 1]
