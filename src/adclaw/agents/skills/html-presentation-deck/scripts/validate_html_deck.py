#!/usr/bin/env python3
"""Validate an AdClaw HTML presentation deck."""

from __future__ import annotations

import re
import sys
from pathlib import Path


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
BANNED_TERMS = [
    "gui" + "zang",
    "sw" + "iss",
    "zh" + "-CN",
    "Noto Sans " + "SC",
    "Noto Serif " + "SC",
]
BANNED_RE = re.compile("|".join(re.escape(term) for term in BANNED_TERMS), re.IGNORECASE)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_html_deck.py <deck.html>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists() or path.suffix.lower() != ".html":
        print(f"Invalid HTML deck path: {path}", file=sys.stderr)
        return 2

    html = path.read_text(encoding="utf-8")
    errors: list[str] = []

    if CJK_RE.search(html):
        errors.append("Deck contains CJK characters.")
    if match := BANNED_RE.search(html):
        errors.append(f"Deck contains banned term: {match.group(0)}")
    if "<!-- SLIDES_HERE -->" in html:
        errors.append("Template marker <!-- SLIDES_HERE --> was not replaced.")
    if "Replace with deck title" in html:
        errors.append("Title placeholder was not replaced.")

    slides = re.findall(r"<section\b[^>]*\bclass=\"[^\"]*\bslide\b[^\"]*\"", html)
    if not slides:
        errors.append('No <section class="slide"> elements found.')

    local_images = re.findall(r"<img\b[^>]*src=\"(images/[^\"]+)\"[^>]*>", html)
    for src in local_images:
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
