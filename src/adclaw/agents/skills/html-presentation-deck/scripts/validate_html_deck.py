#!/usr/bin/env python3
"""Validate an HTML presentation deck.

Contrast parsing supports 6-digit hex (#RRGGBB) and rgb/rgba() theme tokens.
:root and .slide.theme-* rule blocks use brace counting so nested rules do not truncate.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple


IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
CSS_VAR_HEX_RE = re.compile(r"(--[A-Za-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})")
CSS_VAR_RGB_RE = re.compile(
    r"^(--[A-Za-z0-9-]+)\s*:\s*rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([\d.]+%?))?\s*\)\s*$",
    re.IGNORECASE,
)
CSS_VAR_REF_RE = re.compile(
    r"^(--[A-Za-z0-9-]+)\s*:\s*var\(\s*(--[A-Za-z0-9-]+)\s*\)\s*$",
    re.IGNORECASE,
)
SLIDE_THEME_BACKGROUNDS = {
    "theme-dark": "--ink",
    "theme-accent": "--accent",
    "theme-yellow": "--yellow",
}
ROOT_OPEN_RE = re.compile(r":root\s*\{", re.IGNORECASE)
SLIDE_THEME_RULE_RE = re.compile(r"\.slide\.theme-[a-z0-9-]+\s*\{", re.IGNORECASE)
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(?P<body>.*?)</style>", re.IGNORECASE | re.DOTALL)
STYLE_ATTR_RE = re.compile(
    r'\bstyle\s*=\s*"(?P<double>[^"]*--[A-Za-z0-9-]+[^"]*)"|\bstyle\s*=\s*\'(?P<single>[^\']*--[A-Za-z0-9-]+[^\']*)\'',
    re.DOTALL,
)
MIN_TEXT_CONTRAST = 4.5


class CssColor(NamedTuple):
    rgb: str
    alpha: float = 1.0
    ref: str | None = None


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
    # WCAG 2.x relative luminance piecewise transfer (threshold 0.03928).
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    red, green, blue = (_linear_channel(channel) for channel in _hex_to_rgb(color))
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _contrast(foreground: str, background: str) -> float:
    high, low = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _extract_braced_block_body(html: str, opener_end: int) -> str | None:
    depth = 1
    cursor = opener_end
    quote: str | None = None
    in_comment = False
    while cursor < len(html) and depth > 0:
        char = html[cursor]
        next_char = html[cursor + 1] if cursor + 1 < len(html) else ""
        if in_comment:
            if char == "*" and next_char == "/":
                in_comment = False
                cursor += 2
                continue
        elif quote:
            if char == "\\":
                cursor += 2
                continue
            if char == quote:
                quote = None
        elif char == "/" and next_char == "*":
            in_comment = True
            cursor += 2
            continue
        elif char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        cursor += 1
    if depth != 0:
        return None
    return html[opener_end : cursor - 1]


def _css_depth_at(html: str, position: int) -> int:
    depth = 0
    cursor = 0
    quote: str | None = None
    in_comment = False
    while cursor < position:
        char = html[cursor]
        next_char = html[cursor + 1] if cursor + 1 < position else ""
        if in_comment:
            if char == "*" and next_char == "/":
                in_comment = False
                cursor += 2
                continue
        elif quote:
            if char == "\\":
                cursor += 2
                continue
            if char == quote:
                quote = None
        elif char == "/" and next_char == "*":
            in_comment = True
            cursor += 2
            continue
        elif char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
        cursor += 1
    return depth


def _extract_rule_blocks(html: str, opener: re.Pattern[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in opener.finditer(html):
        if _css_depth_at(html, match.start()) != 0:
            continue
        body = _extract_braced_block_body(html, match.end())
        if body is not None:
            blocks.append((match.group(0).strip(), body))
    return blocks


def _rgb_to_hex(red: str, green: str, blue: str) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        min(255, int(red)),
        min(255, int(green)),
        min(255, int(blue)),
    )


def _parse_rgba_alpha(raw: str) -> float:
    if raw.endswith("%"):
        return max(0.0, min(1.0, float(raw[:-1]) / 100.0))
    value = float(raw)
    if value > 1.0:
        return min(1.0, value / 255.0)
    return max(0.0, value)


def _top_level_declarations(block: str) -> list[str]:
    declarations: list[str] = []
    current: list[str] = []
    depth = 0
    cursor = 0
    quote: str | None = None
    in_comment = False
    while cursor < len(block):
        char = block[cursor]
        next_char = block[cursor + 1] if cursor + 1 < len(block) else ""

        if in_comment:
            if char == "*" and next_char == "/":
                in_comment = False
                cursor += 2
                continue
        elif quote:
            current.append(char)
            if char == "\\":
                if next_char:
                    current.append(next_char)
                cursor += 2
                continue
            if char == quote:
                quote = None
        elif char == "/" and next_char == "*":
            in_comment = True
            cursor += 2
            continue
        elif char in {'"', "'"}:
            quote = char
            if depth == 0:
                current.append(char)
        elif char == "{":
            if depth == 0:
                current = []
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
        elif char == ";" and depth == 0:
            declaration = "".join(current).strip()
            if declaration:
                declarations.append(declaration)
            current = []
        elif depth == 0:
            current.append(char)

        cursor += 1

    declaration = "".join(current).strip()
    if declaration:
        declarations.append(declaration)
    return declarations


def _parse_css_variables(block: str) -> dict[str, CssColor]:
    variables: dict[str, CssColor] = {}
    for declaration in _top_level_declarations(block):
        if match := CSS_VAR_HEX_RE.fullmatch(declaration):
            variables[match.group(1)] = CssColor(match.group(2), 1.0)
            continue
        if match := CSS_VAR_RGB_RE.fullmatch(declaration):
            variables[match.group(1)] = CssColor(
                _rgb_to_hex(match.group(2), match.group(3), match.group(4)),
                _parse_rgba_alpha(match.group(5) or "1"),
            )
            continue
        if match := CSS_VAR_REF_RE.fullmatch(declaration):
            variables[match.group(1)] = CssColor("", 1.0, match.group(2))
    return variables


def _composite_over(foreground: CssColor, background: CssColor) -> str:
    if foreground.alpha >= 1.0:
        return foreground.rgb
    red_f, green_f, blue_f = (
        int(foreground.rgb[i : i + 2], 16) for i in (1, 3, 5)
    )
    red_b, green_b, blue_b = (int(background.rgb[i : i + 2], 16) for i in (1, 3, 5))
    alpha = foreground.alpha
    return _rgb_to_hex(
        str(round(alpha * red_f + (1 - alpha) * red_b)),
        str(round(alpha * green_f + (1 - alpha) * green_b)),
        str(round(alpha * blue_f + (1 - alpha) * blue_b)),
    )


def _resolve_token(
    variables: dict[str, CssColor],
    key: str,
    backdrop: CssColor | None,
    seen: set[str] | None = None,
) -> CssColor | None:
    token = variables.get(key)
    if token is None:
        return None
    if token.ref is not None:
        seen = set() if seen is None else seen
        if key in seen:
            return None
        seen.add(key)
        return _resolve_token(variables, token.ref, backdrop, seen)
    if not token.rgb:
        return None
    if backdrop is None or token.alpha >= 1.0:
        return token
    return CssColor(_composite_over(token, backdrop), 1.0)


def _resolved_hex(variables: dict[str, CssColor], key: str, backdrop: CssColor | None) -> str | None:
    token = _resolve_token(variables, key, backdrop)
    return token.rgb if token else None


def _theme_class_from_context(context_name: str) -> str | None:
    match = re.search(r"theme-[a-z0-9-]+", context_name, re.IGNORECASE)
    return match.group(0).lower() if match else None


def _theme_class_for_style_attr(html: str, style_attr_start: int) -> str | None:
    tag_start = html.rfind("<", 0, style_attr_start)
    tag_end = html.find(">", style_attr_start)
    if tag_start == -1 or tag_end == -1:
        return None
    return _theme_class_from_context(html[tag_start : tag_end + 1])


def _css_variable_contexts(html: str) -> list[tuple[str, dict[str, CssColor]]]:
    contexts: list[tuple[str, dict[str, CssColor]]] = []
    root_aggregate: dict[str, CssColor] = {}
    theme_aggregates: dict[str, dict[str, CssColor]] = {}
    style_blocks = [match.group("body") for match in STYLE_BLOCK_RE.finditer(html)]

    root_index = 1
    for css in style_blocks:
        for selector, body in _extract_rule_blocks(css, ROOT_OPEN_RE):
            variables = _parse_css_variables(body)
            if variables:
                root_aggregate.update(variables)
                contexts.append((f":root block {root_index}", dict(root_aggregate)))
                root_index += 1

    theme_index = 1
    for css in style_blocks:
        for selector, body in _extract_rule_blocks(css, SLIDE_THEME_RULE_RE):
            variables = _parse_css_variables(body)
            if variables:
                label = selector.rstrip("{").strip()
                theme_class = _theme_class_from_context(label) or label
                theme_aggregate = theme_aggregates.setdefault(theme_class, dict(root_aggregate))
                theme_aggregate.update(variables)
                merged = dict(theme_aggregate)
                contexts.append((f"slide theme rule {theme_index} ({label})", merged))
                theme_index += 1

    for index, match in enumerate(STYLE_ATTR_RE.finditer(html), start=1):
        variables = _parse_css_variables(match.group("double") or match.group("single") or "")
        if variables:
            theme_class = _theme_class_for_style_attr(html, match.start())
            base = theme_aggregates.get(theme_class or "", root_aggregate)
            merged = dict(base)
            merged.update(variables)
            suffix = f" (.{theme_class})" if theme_class else ""
            contexts.append((f"inline style {index}{suffix}", merged))

    return contexts


def _validate_slide_theme_contrast(
    context_name: str,
    variables: dict[str, CssColor],
) -> list[str]:
    theme_class = _theme_class_from_context(context_name)
    slide_bg_key = SLIDE_THEME_BACKGROUNDS.get(theme_class or "")
    slide_bg = _resolve_token(variables, slide_bg_key, None) if slide_bg_key else None
    if slide_bg is None:
        return []
    if slide_bg.alpha < 1.0:
        return [f"{context_name}: {slide_bg_key} background must be opaque for contrast validation."]

    errors: list[str] = []
    muted = variables.get("--muted")
    panel = variables.get("--panel")
    if muted is not None:
        muted_on_slide = _resolved_hex(variables, "--muted", slide_bg)
        if muted_on_slide is not None:
            ratio = _contrast(muted_on_slide, slide_bg.rgb)
            if ratio < MIN_TEXT_CONTRAST:
                errors.append(
                    f"{context_name}: muted text on slide background contrast is {ratio:.2f}:1 "
                    f"(--muted {muted_on_slide} on {slide_bg_key} {slide_bg.rgb}); "
                    f"minimum is {MIN_TEXT_CONTRAST:.1f}:1."
                )

    if muted is not None and panel is not None:
        panel_hex = _resolved_hex(variables, "--panel", slide_bg)
        if panel_hex is not None:
            panel_surface = CssColor(panel_hex, 1.0)
            muted_on_panel = _resolved_hex(variables, "--muted", panel_surface)
            if muted_on_panel is not None:
                ratio = _contrast(muted_on_panel, panel_hex)
                if ratio < MIN_TEXT_CONTRAST:
                    errors.append(
                        f"{context_name}: muted text on panel contrast is {ratio:.2f}:1 "
                        f"(--muted on --panel over {slide_bg_key}); minimum is {MIN_TEXT_CONTRAST:.1f}:1."
                    )

    return errors


def _validate_contrast(context_name: str, variables: dict[str, CssColor]) -> list[str]:
    if _theme_class_from_context(context_name) in SLIDE_THEME_BACKGROUNDS:
        return _validate_slide_theme_contrast(context_name, variables)

    checks = [
        ("--muted", "--paper", "muted text on paper"),
        ("--muted", "--panel", "muted text on panel"),
        ("--accent-text", "--paper", "accent text on paper"),
        ("--accent-text", "--panel", "accent text on panel"),
        ("--accent-on", "--accent", "text on accent background"),
    ]
    errors: list[str] = []

    for foreground_key, background_key, label in checks:
        background_token = _resolve_token(variables, background_key, None)
        if background_token is None:
            continue
        if background_token.alpha < 1.0:
            errors.append(
                f"{context_name}: {background_key} background must be opaque for contrast validation."
            )
            continue
        background = background_token.rgb
        foreground = _resolved_hex(variables, foreground_key, background_token)
        if not foreground:
            continue
        ratio = _contrast(foreground, background)
        if ratio < MIN_TEXT_CONTRAST:
            errors.append(
                f"{context_name}: {label} contrast is {ratio:.2f}:1 "
                f"({foreground_key} {foreground} on {background_key} {background}); "
                f"minimum is {MIN_TEXT_CONTRAST:.1f}:1."
            )

    if (
        "--accent" in variables
        and "--panel" in variables
        and "--accent-text" not in variables
    ):
        panel = _resolve_token(variables, "--panel", None)
        accent = _resolved_hex(variables, "--accent", panel)
        if accent is not None and panel is not None and panel.alpha >= 1.0:
            ratio = _contrast(accent, panel.rgb)
            if ratio < MIN_TEXT_CONTRAST:
                errors.append(
                    f"{context_name}: --accent on --panel contrast is {ratio:.2f}:1. "
                    "Add a contrast-safe --accent-text token for labels, metrics, and annotations."
                )

    if "--accent" in variables and "--paper" in variables and "--accent-text" not in variables:
        paper = _resolve_token(variables, "--paper", None)
        accent = _resolved_hex(variables, "--accent", paper)
        if accent is not None and paper is not None and paper.alpha >= 1.0:
            ratio = _contrast(accent, paper.rgb)
            if ratio < MIN_TEXT_CONTRAST:
                errors.append(
                    f"{context_name}: --accent on --paper contrast is {ratio:.2f}:1. "
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
