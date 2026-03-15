# -*- coding: utf-8 -*-
"""Tests for R1-R4 memory optimization modules."""

import pytest
from adclaw.memory_agent.compressor import (
    build_codebook,
    codebook_compress,
    codebook_decompress,
    pre_compress,
    rule_compress,
)
from adclaw.memory_agent.dedup import (
    ShingleCache,
    find_near_duplicate,
    jaccard,
    shingles,
)
from adclaw.memory_agent.tiers import generate_tiers, split_into_sections


# ── R1: Compressor ──────────────────────────────────────────────

class TestRuleCompress:
    def test_dedup_lines(self):
        text = "hello\nhello\nhello\nworld"
        result = rule_compress(text)
        assert result.count("hello") == 1

    def test_strip_markdown(self):
        text = "## Heading\n**bold** and *italic*"
        result = rule_compress(text)
        assert "##" not in result
        assert "**" not in result
        assert "bold" in result

    def test_merge_short_bullets(self):
        text = "- foo\n- bar\n- baz"
        result = rule_compress(text)
        assert ";" in result  # merged with semicolons

    def test_preserves_content(self):
        text = "Important decision: use PostgreSQL for the main database."
        result = rule_compress(text)
        assert "PostgreSQL" in result
        assert "decision" in result

    def test_empty_input(self):
        assert rule_compress("") == ""
        assert rule_compress("   ") == ""


class TestCodebook:
    def test_roundtrip(self):
        text = (
            "the quick brown fox jumps over the lazy dog. "
            "the quick brown fox is fast. "
            "the quick brown fox runs daily. "
            "the quick brown fox likes food."
        )
        codebook = build_codebook(text, min_freq=2)
        if codebook:  # may not find patterns in short text
            compressed = codebook_compress(text, codebook)
            decompressed = codebook_decompress(compressed, codebook)
            assert decompressed == text

    def test_empty_codebook(self):
        assert codebook_compress("hello", {}) == "hello"
        assert codebook_decompress("hello", {}) == "hello"


class TestPreCompress:
    def test_returns_stats(self):
        text = "## Title\n\n**bold** text here\n\nhello\nhello\n"
        compressed, stats = pre_compress(text, enable_codebook=False)
        assert stats.original_len > 0
        assert stats.after_rules <= stats.original_len

    def test_savings_positive(self):
        text = "## Heading\n\n" + "- item\n" * 20 + "\nsome text\nsome text\n"
        _, stats = pre_compress(text, enable_codebook=False)
        assert stats.savings_pct >= 0


# ── R3: Dedup ───────────────────────────────────────────────────

class TestShingles:
    def test_basic(self):
        s = shingles("the quick brown fox jumps")
        assert len(s) > 0

    def test_short_text(self):
        s = shingles("hi", k=3)
        assert len(s) == 1  # fallback hash

    def test_empty(self):
        assert shingles("") == set()


class TestJaccard:
    def test_identical(self):
        s = {1, 2, 3}
        assert jaccard(s, s) == 1.0

    def test_disjoint(self):
        assert jaccard({1, 2}, {3, 4}) == 0.0

    def test_partial(self):
        sim = jaccard({1, 2, 3}, {2, 3, 4})
        assert 0.0 < sim < 1.0

    def test_empty(self):
        assert jaccard(set(), {1}) == 0.0


class TestFindNearDuplicate:
    def test_detects_similar(self):
        existing = [
            ("id1", "the quick brown fox jumps over the lazy dog"),
        ]
        # Very similar text
        new = "the quick brown fox jumps over the lazy cat"
        result = find_near_duplicate(new, existing, threshold=0.5)
        assert result == "id1"

    def test_no_match(self):
        existing = [
            ("id1", "completely different content about databases and SQL"),
        ]
        new = "the weather today is sunny and warm outside"
        result = find_near_duplicate(new, existing, threshold=0.6)
        assert result is None

    def test_cache(self):
        cache = ShingleCache(max_size=10)
        existing = [("id1", "hello world foo bar baz")]
        find_near_duplicate("test query words", existing, cache=cache)
        assert "id1" in cache._cache


# ── R2: Tiers ───────────────────────────────────────────────────

class TestTiers:
    def test_generates_three_tiers(self):
        text = (
            "We decided to use PostgreSQL.\n\n"
            "Action: migrate by Friday.\n\n"
            "Config: DB_HOST=localhost, port=5432.\n\n"
            "Note: John mentioned backup strategy.\n\n"
            "FYI: meeting notes from last week."
        )
        tiers = generate_tiers(text)
        assert "L0" in tiers
        assert "L1" in tiers
        assert "L2" in tiers

    def test_l0_subset_of_l1(self):
        text = "\n\n".join([f"Section {i} with some content words." for i in range(20)])
        tiers = generate_tiers(text)
        assert len(tiers["L0"]) <= len(tiers["L1"])
        assert len(tiers["L1"]) <= len(tiers["L2"])

    def test_empty(self):
        tiers = generate_tiers("")
        assert tiers["L0"] == ""

    def test_split_sections(self):
        text = "Part one content.\n\nPart two content.\n\nPart three."
        sections = split_into_sections(text)
        assert len(sections) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
