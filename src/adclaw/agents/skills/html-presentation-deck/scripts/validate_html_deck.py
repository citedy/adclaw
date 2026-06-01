#!/usr/bin/env python3
"""Validate an HTML presentation deck.

Contrast parsing only supports 6-digit hex CSS variables (#RRGGBB).
:root blocks are extracted with brace counting so nested rules do not truncate.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
# Deck templates use 6-digit hex theme tokens only.
CSS_VAR_RE = re.compile(r"(--[A-Za-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})")
ROOT_OPEN_RE = re.compile(r":root\s*\{", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(
    r'\bstyle\s*=\s*(["\'])(?P<body>[^"\']*--[A-Za-z0-9-]+[^"\']*)\1',
    re.DOTALL,
)
MIN_TEXT_CONTRAST = 4.5


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


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _linear_channel(channel: float) -> float:
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    red, green, blue = (_linear_channel(channel) for channel in _hex_to_rgb(color))
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _contrast(foreground: str, background: str) -> float:
    high, low = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _extract_root_block_bodies(html: str) -> list[str]:
    bodies: list[str] = []
    for match in ROOT_OPEN_RE.finditer(html):
        index = match.end()
        depth = 1
        cursor = index
        while cursor < len(html) and depth > 0:
            char = html[cursor]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            cursor += 1
        if depth == 0:
            bodies.append(html[index : cursor - 1])
    return bodies


def _parse_css_variables(block: str) -> dict[str, str]:
    return dict(CSS_VAR_RE.findall(block))


def _css_variable_contexts(html: str) -> list[tuple[str, dict[str, str]]]:
    contexts: list[tuple[str, dict[str, str]]] = []
    root_aggregate: dict[str, str] = {}

    for index, body in enumerate(_extract_root_block_bodies(html), start=1):
        variables = _parse_css_variables(body)
        if variables:
            root_aggregate.update(variables)
            contexts.append((f":root block {index}", dict(root_aggregate)))

    for index, match in enumerate(STYLE_ATTR_RE.finditer(html), start=1):
        variables = _parse_css_variables(match.group("body"))
        if variables:
            merged = dict(root_aggregate)
            merged.update(variables)
            contexts.append((f"inline style {index}", merged))

    return contexts


def _validate_contrast(context_name: str, variables: dict[str, str]) -> list[str]:
    checks = [
        ("--muted", "--paper", "muted text on paper"),
        ("--muted", "--panel", "muted text on panel"),
        ("--accent-text", "--paper", "accent text on paper"),
        ("--accent-text", "--panel", "accent text on panel"),
        ("--accent-on", "--accent", "text on accent background"),
    ]
    errors: list[str] = []

    for foreground_key, background_key, label in checks:
        foreground = variables.get(foreground_key)
        background = variables.get(background_key)
        if not foreground or not background:
            continue
        ratio = _contrast(foreground, background)
        if ratio < MIN_TEXT_CONTRAST:
            errors.append(
                f"{context_name}: {label} contrast is {ratio:.2f}:1 "
                f"({foreground_key} {foreground} on {background_key} {background}); "
                f"minimum is {MIN_TEXT_CONTRAST:.1f}:1."
            )

    if "--accent" in variables and "--panel" in variables and "--accent-text" not in variables:
        ratio = _contrast(variables["--accent"], variables["--panel"])
        if ratio < MIN_TEXT_CONTRAST:
            errors.append(
                f"{context_name}: --accent on --panel contrast is {ratio:.2f}:1. "
                "Add a contrast-safe --accent-text token for labels, metrics, and annotations."
            )

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/validate_html_deck.py <deck.html>", file=sys.stderr)
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

    for context_name, variables in _css_variable_contexts(html):
        errors.extend(_validate_contrast(context_name, variables))

    if errors:
        print("HTML deck validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"HTML deck validation passed: {len(slides)} slide(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())