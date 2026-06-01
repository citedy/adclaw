#!/usr/bin/env python3
"""Quality gate for strict HTML presentation decks."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ALLOWED_LAYOUTS = {
    "PG01",
    "PG02",
    "PG03",
    "PG04",
    "PG05",
    "PG06",
    "PG07",
    "PG08",
    "PG09",
    "PG10",
    "PG11",
    "PG12",
    "PG13",
    "PG14",
}

IMAGE_SLOT_BY_LAYOUT = {
    "PG01": {"pg01-hero-16x9"},
    "PG04": {"pg04-main-16x10"},
    "PG09": {"pg09-evidence-16x9"},
}

REQUIRED_IMAGE_BY_LAYOUT = {
    "PG04": {"pg04-main-16x10"},
}

ALLOWED_GLOBAL_CLASSES = {
    "slide",
    "theme-dark",
    "theme-accent",
    "theme-yellow",
}

TEXT_ALIGN_CENTER_OK = {"PG02", "PG10", "PG12"}
REQUIRED_TEMPLATE_CLASSES = {"deck", "slide", "stage", "progress", "nav", "index"}

IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
CLASS_SELECTOR_RE = re.compile(r"(?<![A-Za-z0-9_-])\.([A-Za-z_][A-Za-z0-9_-]*)")
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>([\s\S]*?)</style>", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r"style\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
DECORATIVE_CSS_RE = re.compile(r"linear-gradient|box-shadow|filter\s*:", re.IGNORECASE)
SECTION_RE = re.compile(
    r"(?P<tag><section\b(?P<attrs>[^>]*)>)(?P<html>[\s\S]*?)</section>",
    re.IGNORECASE,
)


class ImgParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []
        self.classes: list[str] = []
        self.svg_text_count = 0
        self._in_svg = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if "class" in attr:
            self.classes.extend(part for part in attr["class"].split() if part)
        if tag.lower() == "img":
            self.images.append(attr)
        if tag.lower() == "svg":
            self._in_svg = True
        if self._in_svg and tag.lower() == "text":
            self.svg_text_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "svg":
            self._in_svg = False


FETCH_ATTRS = {"src", "href", "srcset", "poster", "data", "xlink:href"}
FETCH_TAGS = {"script", "img", "image", "video", "audio", "source", "iframe", "embed", "object"}
EXTERNAL_URL_PREFIXES = ("http://", "https://", "//")
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)((?:https?:)?//[^'\"\s)]+)\1\s*\)", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?(['\"]?)((?:https?:)?//[^'\"\s)]+)\1", re.IGNORECASE)
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets/template-product-grid.html"


def contains_external_css(css: str) -> bool:
    return bool(CSS_URL_RE.search(css) or CSS_IMPORT_RE.search(css))


def is_external_url(value: str) -> bool:
    return value.strip().lower().startswith(EXTERNAL_URL_PREFIXES)


class ExternalRefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_external = False
        self._in_style = False
        self._style_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr = {key.lower(): value or "" for key, value in attrs}

        if tag_lower == "style":
            self._in_style = True

        style = attr.get("style", "")
        if style and contains_external_css(style):
            self.has_external = True

        for name, value in attr.items():
            if not value or name.startswith("xmlns"):
                continue
            if name == "srcset":
                candidates = [part.strip().split()[0] for part in value.split(",") if part.strip()]
                if any(is_external_url(candidate) for candidate in candidates):
                    self.has_external = True
            elif name in FETCH_ATTRS and (tag_lower in FETCH_TAGS or name != "href" or tag_lower in {"base", "link"}):
                if is_external_url(value):
                    self.has_external = True

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._style_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            if contains_external_css("".join(self._style_chunks)):
                self.has_external = True
            self._style_chunks.clear()
            self._in_style = False


def has_external_fetch_reference(html: str) -> bool:
    parser = ExternalRefParser()
    parser.feed(html)
    return parser.has_external


def attr_value(attrs: str, name: str) -> str | None:
    match = re.search(rf"\b{name}\s*=\s*(['\"])(.*?)\1", attrs, re.IGNORECASE)
    return match.group(2) if match else None


def css_classes(html: str) -> set[str]:
    classes: set[str] = set()
    for block in STYLE_BLOCK_RE.findall(html):
        classes.update(CLASS_SELECTOR_RE.findall(block))
    return classes


def css_markup(html: str) -> str:
    style_blocks = STYLE_BLOCK_RE.findall(html)
    style_attrs = [match.group(2) for match in STYLE_ATTR_RE.finditer(html)]
    return "\n".join(style_blocks + style_attrs)


def registered_css_classes() -> tuple[set[str], str | None]:
    if not TEMPLATE_PATH.is_file():
        return set(), f"Template CSS source not found: {TEMPLATE_PATH}"
    classes = css_classes(TEMPLATE_PATH.read_text(encoding="utf-8"))
    if not classes:
        return set(), f"Template CSS source has no registered classes: {TEMPLATE_PATH}"
    return classes, None


def check_file(path: Path) -> tuple[list[str], list[str]]:
    html = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    if "<!-- SLIDES_HERE -->" in html:
        errors.append("Template marker <!-- SLIDES_HERE --> was not replaced.")
    if "Replace with deck title" in html:
        errors.append("Title placeholder was not replaced.")
    if IDEOGRAPH_RE.search(html):
        errors.append("Deck contains ideograph characters; this skill is English-only unless explicitly overridden.")
    if has_external_fetch_reference(html):
        errors.append("Deck contains external http(s) references; strict decks must work offline.")
    if re.search(r"letter-spacing\s*:\s*-[^;]+", html, re.IGNORECASE):
        errors.append("Negative letter-spacing is not allowed in strict Product Grid decks.")
    if DECORATIVE_CSS_RE.search(css_markup(html)):
        errors.append("Decorative gradients, shadows, and filters are not allowed in Product Grid decks.")

    defined_classes = css_classes(html)
    missing_template_classes = sorted(REQUIRED_TEMPLATE_CLASSES - defined_classes)
    if missing_template_classes:
        errors.append(f"Deck is missing copied Product Grid template CSS class(es): {', '.join(missing_template_classes)}.")
    registered_classes, registered_error = registered_css_classes()
    if registered_error:
        errors.append(registered_error)
    else:
        deck_local_classes = sorted(defined_classes - registered_classes)
        if deck_local_classes:
            errors.append(f"Deck defines unregistered CSS class(es): {', '.join(deck_local_classes)}.")
        defined_classes = registered_classes
    slides = [
        match
        for match in SECTION_RE.finditer(html)
        if re.search(r"\bclass\s*=\s*(['\"])[^'\"]*\bslide\b[^'\"]*\1", match.group("tag"), re.IGNORECASE)
    ]
    if not slides:
        errors.append('No <section class="slide"> elements found.')

    layout_sequence: list[str] = []
    used_layouts: set[str] = set()

    for idx, match in enumerate(slides, start=1):
        attrs = match.group("attrs")
        tag_html = match.group("tag")
        slide_html = match.group(0)
        section_html = match.group("html")
        slide_markup = f"{tag_html}{section_html}"
        layout = attr_value(attrs, "data-layout")
        system = attr_value(attrs, "data-system")
        layout_sequence.append(layout or "")

        if system != "product-grid":
            errors.append(f"Slide {idx}: missing data-system=\"product-grid\".")
        if not layout:
            errors.append(f"Slide {idx}: missing data-layout.")
        elif layout not in ALLOWED_LAYOUTS:
            errors.append(f"Slide {idx}: data-layout=\"{layout}\" is not registered.")
        else:
            used_layouts.add(layout)

        parser = ImgParser()
        parser.feed(slide_html)

        if re.search(r"<section\b", section_html, re.IGNORECASE):
            errors.append(f"Slide {idx}: nested <section> elements are not allowed.")

        undefined = sorted(
            {
                cls
                for cls in parser.classes
                if cls not in defined_classes and cls not in ALLOWED_GLOBAL_CLASSES
            }
        )
        if undefined:
            errors.append(f"Slide {idx}: undefined CSS class(es): {', '.join(undefined)}.")

        if parser.svg_text_count:
            errors.append(f"Slide {idx}: SVG contains visible <text>; use HTML labels instead.")

        if layout not in TEXT_ALIGN_CENTER_OK and re.search(r"text-align\s*:\s*center", slide_html, re.IGNORECASE):
            errors.append(f"Slide {idx}: text-align:center is not allowed for {layout or 'unregistered layout'}.")
        if "theme-yellow" in slide_html and re.search(r"rgb\(22,\s*92,\s*255\)|#165cff", slide_markup, re.IGNORECASE):
            # CSS variables on the template are allowed; this catches slide-local blue accents.
            if re.search(r"style\s*=\s*(['\"])[^'\"]*(?:#165cff|rgb\(22,\s*92,\s*255\))", slide_markup, re.IGNORECASE):
                errors.append(f"Slide {idx}: yellow theme contains slide-local blue accent styling.")

        if re.search(r"style\s*=\s*(['\"])[^'\"]*font-size\s*:", slide_markup, re.IGNORECASE):
            errors.append(f"Slide {idx}: inline font-size override found; edit copy or use a registered component.")

        if re.search(r"style\s*=\s*(['\"])[^'\"]*height\s*:\s*\d+(?:\.\d+)?vh", slide_markup, re.IGNORECASE):
            errors.append(f"Slide {idx}: fixed vh height found; use registered ratio classes.")

        seen_slots: set[str] = set()
        for image_num, image in enumerate(parser.images, start=1):
            src = image.get("src", "")
            alt = image.get("alt", "")
            slot = image.get("data-image-slot", "")
            local_src = src[2:] if src.startswith("./images/") else src
            if not alt.strip():
                errors.append(f"Slide {idx}: image {image_num} is missing alt text.")
            if local_src.startswith("images/"):
                if not (path.parent / local_src).exists():
                    errors.append(f"Slide {idx}: missing local image {local_src}.")
                if not slot:
                    errors.append(f"Slide {idx}: local image {image_num} missing data-image-slot.")
                else:
                    seen_slots.add(slot)
                    allowed_slots = IMAGE_SLOT_BY_LAYOUT.get(layout or "", set())
                    if slot not in allowed_slots:
                        errors.append(f"Slide {idx}: image slot {slot} is not allowed for {layout or 'unregistered layout'}.")
            elif src and not is_external_url(src):
                errors.append(f"Slide {idx}: image {image_num} must use a local images/ path.")

        for required in REQUIRED_IMAGE_BY_LAYOUT.get(layout or "", set()):
            if required not in seen_slots:
                errors.append(f"Slide {idx}: required image slot {required} is missing.")

    for i in range(2, len(layout_sequence)):
        if layout_sequence[i] and layout_sequence[i] == layout_sequence[i - 1] == layout_sequence[i - 2]:
            errors.append(f"Slides {i - 1}-{i + 1}: same layout repeated three times.")

    if 5 <= len(slides) < 8 and len(used_layouts) < 5:
        warnings.append("Decks under 8 slides should use at least 5 distinct layouts.")
    if len(slides) >= 8 and len(used_layouts) < 7:
        warnings.append("Decks with 8 or more slides should use at least 7 distinct layouts.")

    return errors, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_deck_quality.py <deck.html>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.is_file() or path.suffix.lower() != ".html":
        print(f"Invalid HTML deck path: {path}", file=sys.stderr)
        return 2

    errors, warnings = check_file(path)

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("HTML deck quality validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("HTML deck quality validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
