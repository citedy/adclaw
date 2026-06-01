#!/usr/bin/env python3
"""Validate an HTML presentation deck."""

from __future__ import annotations

import re
import sys
from pathlib import Path


IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _term(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


BANNED_TERMS = [
    _term(103, 117, 105, 122, 97, 110, 103),
    _term(111, 112, 55, 52, 49, 56),
    _term(112, 112, 116, 45, 115, 107, 105, 108, 108),
    _term(122, 104, 45, 67, 78),
    _term(78, 111, 116, 111, 32, 83, 97, 110, 115, 32, 83, 67),
    _term(78, 111, 116, 111, 32, 83, 101, 114, 105, 102, 32, 83, 67),
]
BANNED_RE = re.compile(
    "|".join(
        rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
        for term in BANNED_TERMS
    ),
    re.IGNORECASE,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_html_deck.py <deck.html>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.is_file() or path.suffix.lower() != ".html":
        print(f"Invalid HTML deck path: {path}", file=sys.stderr)
        return 2

    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Could not read HTML deck: {path} ({exc})", file=sys.stderr)
        return 2

    errors: list[str] = []

    if IDEOGRAPH_RE.search(html):
        errors.append("Deck contains non-English ideograph characters.")
    if match := BANNED_RE.search(html):
        errors.append(f"Deck contains banned term: {match.group(0)}")
    if "<!-- SLIDES_HERE -->" in html:
        errors.append("Template marker <!-- SLIDES_HERE --> was not replaced.")
    if "Replace with deck title" in html:
        errors.append("Title placeholder was not replaced.")

    slides = re.findall(
        r"<section\b[^>]*\bclass\s*=\s*(['\"])[^'\"]*\bslide\b[^'\"]*\1",
        html,
    )
    if not slides:
        errors.append('No <section class="slide"> elements found.')

    local_images = re.findall(
        r"<img\b[^>]*\bsrc\s*=\s*(['\"])(images/[^'\"]+)\1[^>]*>",
        html,
    )
    for _, src in local_images:
        image_path = path.parent / src
        if not image_path.exists():
            errors.append(f"Missing local image: {src}")

    if errors:
        print("HTML deck validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"HTML deck validation passed: {len(slides)} slide(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
