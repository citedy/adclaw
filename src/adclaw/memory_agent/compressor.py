# -*- coding: utf-8 -*-
"""Deterministic pre-compression for memory content.

Zero-LLM-cost text compression applied BEFORE LLM summarization to reduce
token count. Two passes:

1. Rule-based cleanup: normalize whitespace, strip markdown cruft, dedup
   lines, merge short bullets.
2. N-gram codebook: frequent multi-word phrases replaced with $XX codes
   (lossless roundtrip).

Adapted from claw-compactor (github.com/aeromomo/claw-compactor).
"""

from __future__ import annotations

import re
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CompressionStats:
    original_len: int = 0
    after_rules: int = 0
    after_codebook: int = 0
    savings_pct: float = 0.0
    codebook_size: int = 0


# ---------------------------------------------------------------------------
# Pass 1: Rule-based compression
# ---------------------------------------------------------------------------

def rule_compress(text: str) -> str:
    """Apply deterministic rule-based compression passes."""
    if not text:
        return text

    # 1. Normalize whitespace
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    # 2. Strip markdown formatting noise
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings → plain
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)  # bold/italic
    text = re.sub(r"`([^`]+)`", r"\1", text)  # inline code
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links → text

    # 3. Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # 4. Dedup consecutive identical lines
    lines = text.split("\n")
    deduped: List[str] = []
    for line in lines:
        stripped = line.strip()
        if deduped and deduped[-1].strip() == stripped and stripped:
            continue
        deduped.append(line)
    text = "\n".join(deduped)

    # 5. Remove empty sections (header followed by nothing)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. Merge short bullet lines (< 40 chars each, consecutive)
    lines = text.split("\n")
    merged: List[str] = []
    bullet_buf: List[str] = []
    for line in lines:
        stripped = line.strip()
        is_bullet = stripped.startswith(("- ", "* ", "+ "))
        if is_bullet and len(stripped) < 40:
            bullet_buf.append(stripped[2:].strip())
        else:
            if bullet_buf:
                merged.append("- " + "; ".join(bullet_buf))
                bullet_buf = []
            merged.append(line)
    if bullet_buf:
        merged.append("- " + "; ".join(bullet_buf))
    text = "\n".join(merged)

    # 7. Strip trailing whitespace per line
    text = "\n".join(l.rstrip() for l in text.split("\n"))

    return text.strip()


# ---------------------------------------------------------------------------
# Pass 2: N-gram codebook compression
# ---------------------------------------------------------------------------

def _extract_ngrams(text: str, min_n: int = 2, max_n: int = 5) -> Counter:
    """Extract word n-grams and count frequencies."""
    words = text.split()
    counter: Counter = Counter()
    for n in range(min_n, max_n + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            if len(phrase) >= 8:  # only worthwhile phrases
                counter[phrase] += 1
    return counter


def build_codebook(
    text: str,
    max_codes: int = 50,
    min_freq: int = 3,
) -> Dict[str, str]:
    """Build n-gram codebook: phrase → $XX code.

    Selects phrases by savings = (freq - 1) * (len(phrase) - len(code)).
    Greedy: skip phrases that overlap with already-selected ones.
    """
    ngrams = _extract_ngrams(text)
    candidates: List[Tuple[str, int, int]] = []

    code_idx = 0
    for phrase, freq in ngrams.items():
        if freq < min_freq:
            continue
        code_len = 3 if code_idx < 26 else 4  # $A..$Z then $AA..
        savings = (freq - 1) * (len(phrase) - code_len)
        if savings > 0:
            candidates.append((phrase, freq, savings))

    candidates.sort(key=lambda x: -x[2])

    codebook: Dict[str, str] = {}
    used_phrases: List[str] = []
    code_idx = 0

    for phrase, freq, savings in candidates:
        if code_idx >= max_codes:
            break
        # Check overlap with already selected phrases
        if any(phrase in p or p in phrase for p in used_phrases):
            continue
        # Generate code
        if code_idx < 26:
            code = f"${chr(65 + code_idx)}"
        else:
            code = f"${chr(65 + (code_idx - 26) // 26)}{chr(65 + (code_idx - 26) % 26)}"
        codebook[phrase] = code
        used_phrases.append(phrase)
        code_idx += 1

    return codebook


def codebook_compress(text: str, codebook: Dict[str, str]) -> str:
    """Replace phrases with codebook codes. Longest phrases first."""
    if not codebook:
        return text
    # Escape existing $ signs
    text = text.replace("$", "$$")
    # Replace longest phrases first
    for phrase in sorted(codebook.keys(), key=len, reverse=True):
        text = text.replace(phrase, codebook[phrase])
    return text


def codebook_decompress(text: str, codebook: Dict[str, str]) -> str:
    """Reverse codebook substitution."""
    if not codebook:
        return text
    reverse = {v: k for k, v in codebook.items()}
    # Replace shortest codes first to avoid partial matches
    for code in sorted(reverse.keys(), key=len, reverse=True):
        text = text.replace(code, reverse[code])
    # Unescape $
    text = text.replace("$$", "$")
    return text


def codebook_header(codebook: Dict[str, str]) -> str:
    """Generate codebook header for prepending to compressed text."""
    if not codebook:
        return ""
    lines = [f"{code}={phrase}" for phrase, code in codebook.items()]
    return "[CODEBOOK]\n" + "\n".join(lines) + "\n[/CODEBOOK]\n"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def pre_compress(text: str, enable_codebook: bool = True) -> Tuple[str, CompressionStats]:
    """Apply full pre-compression pipeline.

    Returns:
        Tuple of (compressed_text, stats).
    """
    stats = CompressionStats(original_len=len(text))

    # Pass 1: Rule-based
    text = rule_compress(text)
    stats.after_rules = len(text)

    # Pass 2: Codebook (only for larger texts)
    if enable_codebook and len(text) > 500:
        codebook = build_codebook(text)
        if codebook:
            header = codebook_header(codebook)
            text = header + codebook_compress(text, codebook)
            stats.codebook_size = len(codebook)
    stats.after_codebook = len(text)

    # Calculate savings
    if stats.original_len > 0:
        stats.savings_pct = (1 - stats.after_codebook / stats.original_len) * 100

    logger.debug(
        "Pre-compression: %d → %d chars (%.1f%% saved, %d codebook entries)",
        stats.original_len,
        stats.after_codebook,
        stats.savings_pct,
        stats.codebook_size,
    )

    return text, stats
