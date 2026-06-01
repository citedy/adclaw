import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from adclaw.agents.skill_scanner import SkillSecurityScanner


SKILL_DIR = Path(__file__).resolve().parents[1] / "src/adclaw/agents/skills/html-presentation-deck"


def _load_validate_html_deck_module():
    spec = importlib.util.spec_from_file_location(
        "validate_html_deck",
        SKILL_DIR / "scripts" / "validate_html_deck.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
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
PRODUCT_GRID_TEST_CSS = (
    ".deck{display:flex}.slide{display:block}.stage{display:block}"
    ".progress{display:block}.nav{display:block}.index{display:block}"
)


def test_html_presentation_deck_has_no_non_english_markers_or_banned_terms():
    for path in SKILL_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".html", ".py", ".json", ".txt"}:
            text = path.read_text(encoding="utf-8")
            assert not IDEOGRAPH_RE.search(text), f"Non-English ideograph found in {path.relative_to(SKILL_DIR)}"
            assert not BANNED_RE.search(text), f"Banned term found in {path.relative_to(SKILL_DIR)}"


def test_html_presentation_deck_assets_exist():
    expected = [
        "assets/screenshot-backgrounds/editorial/ink-paper.webp",
        "assets/screenshot-backgrounds/editorial/indigo-porcelain.webp",
        "assets/screenshot-backgrounds/editorial/forest-ledger.webp",
        "assets/screenshot-backgrounds/editorial/warm-archive.webp",
        "assets/screenshot-backgrounds/editorial/sand-gallery.webp",
        "assets/screenshot-backgrounds/clean-grid/blue-anchor.webp",
        "assets/screenshot-backgrounds/clean-grid/lemon-signal.webp",
        "assets/screenshot-backgrounds/clean-grid/lime-circuit.webp",
        "assets/screenshot-backgrounds/clean-grid/orange-marker.webp",
    ]
    for rel_path in expected:
        path = SKILL_DIR / rel_path
        assert path.exists(), f"Missing generated asset: {rel_path}"
        assert path.stat().st_size > 1024, f"Generated asset is unexpectedly small: {rel_path}"


def test_html_presentation_deck_referenced_assets_resolve():
    reference = SKILL_DIR / "references/screenshot-framing.md"
    text = reference.read_text(encoding="utf-8")
    referenced_assets = sorted(set(re.findall(r"`(screenshot-backgrounds/[^`]+\.webp)`", text)))

    assert len(referenced_assets) == 9
    for rel_path in referenced_assets:
        path = (reference.parent / "../assets" / rel_path).resolve()
        assert path.is_file(), f"Broken screenshot background reference: {rel_path}"


def test_html_presentation_deck_static_scan_is_safe():
    result = SkillSecurityScanner().scan_skill(SKILL_DIR)
    assert result.safe is True
    assert result.critical_count == 0


def test_html_deck_validator_accepts_single_quoted_html_and_generic_region_word(tmp_path):
    deck = tmp_path / "deck.html"
    regional_word = "".join(chr(code) for code in [83, 119, 105, 115, 115])
    deck.write_text(
        f"""<!doctype html>
<html lang='en'>
<head><title>Runtime test</title></head>
<body>
<section class='slide'><h1>{regional_word} market readout</h1></section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_html_deck.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_html_deck_validator_handles_invalid_path_cleanly(tmp_path):
    directory = tmp_path / "deck.html"
    directory.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_html_deck.py"),
            str(directory),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Invalid HTML deck path" in result.stderr


def test_html_deck_validator_merges_inline_tokens_with_root_for_contrast(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        """<!doctype html>
<html lang="en">
<head>
<style>
:root { --muted: #777777; --paper: #ffffff; --panel: #f5f5f5; --accent: #ff5500; }
</style>
</head>
<body>
<section class="slide" style="--panel:#151515">
  <p class="muted">Low contrast body</p>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts" / "validate_html_deck.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout
    assert "muted text on panel" in result.stderr


def test_html_deck_contrast_helpers():
    mod = _load_validate_html_deck_module()
    assert mod._luminance("#ffffff") > mod._luminance("#000000")
    assert mod._contrast("#000000", "#ffffff") == 21.0


def test_html_deck_css_variable_contexts_nested_root_and_shorthand_hex():
    mod = _load_validate_html_deck_module()
    html = """
<style>
:root {
  --paper: #ffffff;
  --muted: #888888;
  --accent-text: #ffcc00;
  @media (min-width: 1px) { --panel: #111111; }
}
</style>
<section class="slide" style="--panel:#222222"></section>
"""
    contexts = mod._css_variable_contexts(html)
    assert any(name.startswith(":root") for name, _ in contexts)
    root_contexts = [vars for name, vars in contexts if name.startswith(":root")]
    assert len(root_contexts) == 1
    assert "--paper" in root_contexts[0]
    inline_vars = next(vars for name, vars in contexts if name.startswith("inline"))
    assert inline_vars["--muted"] == "#888888"
    assert inline_vars["--panel"] == "#222222"

    shorthand_only = mod._parse_css_variables(":root { --paper: #fff; }")
    assert shorthand_only == {}


def test_html_deck_root_contexts_use_cumulative_aggregate():
    mod = _load_validate_html_deck_module()
    html = """
<style>
:root { --muted: #595959; --paper: #ffffff; }
:root { --panel: #f0f0f0; }
</style>
"""
    contexts = mod._css_variable_contexts(html)
    second_root = [vars for name, vars in contexts if name == ":root block 2"][0]
    assert second_root["--muted"] == "#595959"
    assert second_root["--panel"] == "#f0f0f0"


def test_html_deck_validate_contrast_flags_accent_text_on_paper():
    mod = _load_validate_html_deck_module()
    errors = mod._validate_contrast(
        "test",
        {
            "--accent-text": "#cccccc",
            "--paper": "#ffffff",
            "--muted": "#777777",
            "--panel": "#f0f0f0",
        },
    )
    assert any("accent text on paper" in error for error in errors)


def test_html_deck_validator_parses_nested_root_block(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        """<!doctype html>
<html lang="en">
<head>
<style>
:root {
  --muted: #595959;
  --paper: #ffffff;
  --panel: #f0f0f0;
  --accent-text: #0b5d1e;
  @supports (display: grid) { --panel: #e8e8e8; }
}
</style>
</head>
<body>
<section class="slide"><p>ok</p></section>
</body>
</html>
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts/validate_html_deck.py"), str(deck)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_product_grid_quality_validator_ignores_xmlns_urls(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><svg xmlns="http://www.w3.org/2000/svg"></svg></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_product_grid_quality_validator_rejects_external_and_unregistered_image_slots(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "local.png").write_bytes(b"png")
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage">
    <img src="https://example.com/remote.png" alt="Remote">
    <img src="images/local.png" alt="Local" data-image-slot="pg04-main-16x10">
  </div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external http(s) references" in result.stderr
    assert "image slot pg04-main-16x10 is not allowed for PG02" in result.stderr


def test_product_grid_quality_validator_does_not_warn_when_fewer_than_five_slides(tmp_path):
    deck = tmp_path / "deck.html"
    slides = "\n".join(
        f"""<section class="slide" data-system="product-grid" data-layout="{layout}">
  <div class="stage"><p>Slide {idx}</p></div>
</section>"""
        for idx, layout in enumerate(["PG02", "PG03", "PG05", "PG06"], start=1)
    )
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
{slides}
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Decks under 8 slides should use at least 5 distinct layouts" not in result.stdout


def test_product_grid_quality_validator_allows_responsive_template_css(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}.title{{font-size:clamp(32px,5vw,72px)}}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><p>Responsive template CSS is allowed.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_product_grid_quality_validator_rejects_deck_local_css_classes(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        """<!doctype html>
<html lang="en">
<head><style>.stage{display:block}.one-off{color:red}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage one-off"><p>Custom classes are not allowed.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Deck defines unregistered CSS class(es): one-off" in result.stderr


def test_product_grid_quality_validator_rejects_missing_copied_template_css(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        """<!doctype html>
<html lang="en">
<head><style>.stage{display:block}</style></head>
<body>
<main class="deck" id="deck">
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><p>Template CSS must be copied.</p></div>
</section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing copied Product Grid template CSS class(es)" in result.stderr


def test_product_grid_quality_validator_rejects_uppercase_external_url_schemes(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><img src="HTTPS://example.com/remote.png" alt="Remote"></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external http(s) references" in result.stderr


def test_product_grid_quality_validator_rejects_nested_sections(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><section><p>Nested section</p></section></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "nested <section> elements are not allowed" in result.stderr


def test_product_grid_quality_validator_rejects_remote_base_href(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <base href="https://cdn.example/">
  <style>.stage{display:block}</style>
</head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><p>Remote base URLs are not allowed.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external http(s) references" in result.stderr


def test_product_grid_quality_validator_rejects_protocol_relative_urls(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><img src="//cdn.example.com/remote.png" alt="Remote"></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external http(s) references" in result.stderr


def test_product_grid_quality_validator_rejects_svg_image_href(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><svg><image href="https://example.com/remote.png"></image></svg></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external http(s) references" in result.stderr


def test_product_grid_quality_validator_checks_dot_prefixed_local_images(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG01">
  <div class="stage"><img src="./images/hero.png" alt="Hero"></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing local image images/hero.png" in result.stderr
    assert "local image 1 missing data-image-slot" in result.stderr


def test_product_grid_quality_validator_rejects_non_images_local_paths(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG01">
  <div class="stage"><img src="assets/hero.png" alt="Hero" data-image-slot="pg01-hero-16x9"></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "image 1 must use a local images/ path" in result.stderr


def test_product_grid_quality_validator_allows_font_size_in_style_blocks(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}.stage{{font-size:18px}}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><p>Template CSS owns type sizing.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_product_grid_quality_validator_allows_filter_as_body_copy(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><p class="body">Filter: tenant knowledge</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_product_grid_quality_validator_rejects_slide_level_inline_style(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02" style="font-size:10px;height:100vh">
  <div class="stage"><p>Slide-level inline style is not allowed.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "inline font-size override" in result.stderr
    assert "fixed vh height" in result.stderr


def test_product_grid_quality_validator_rejects_yellow_section_blue_accent(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide theme-yellow" data-system="product-grid" data-layout="PG02" style="color:#165cff">
  <div class="stage"><p>Yellow slides cannot use blue local accents.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "yellow theme contains slide-local blue accent styling" in result.stderr


def test_product_grid_quality_validator_allows_yellow_section_var_accent(tmp_path):
    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide theme-yellow" data-system="product-grid" data-layout="PG02" style="color:var(--accent)">
  <div class="stage"><p>Yellow theme remaps accent to ink.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts/validate_deck_quality.py"),
            str(deck),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_product_grid_quality_validator_fails_when_template_classes_are_unavailable(tmp_path, monkeypatch):
    module_path = SKILL_DIR / "scripts/validate_deck_quality.py"
    spec = importlib.util.spec_from_file_location("validate_deck_quality_for_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    deck = tmp_path / "deck.html"
    deck.write_text(
        f"""<!doctype html>
<html lang="en">
<head><style>{PRODUCT_GRID_TEST_CSS}</style></head>
<body>
<section class="slide" data-system="product-grid" data-layout="PG02">
  <div class="stage"><p>Template class registry must load.</p></div>
</section>
</body>
</html>
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "TEMPLATE_PATH", tmp_path / "missing-template.html")

    errors, warnings = module.check_file(deck)

    assert not warnings
    assert any("Template CSS source not found" in error for error in errors)


def test_product_grid_template_requires_horizontal_touch_intent():
    template = (SKILL_DIR / "assets/template-product-grid.html").read_text(encoding="utf-8")

    assert "event.touches[0].clientY" in template
    assert "Math.abs(deltaX) > Math.abs(deltaY)" in template


def test_product_grid_template_uses_horizontal_wheel_direction_for_horizontal_intent():
    template = (SKILL_DIR / "assets/template-product-grid.html").read_text(encoding="utf-8")

    assert "const direction = horizontalIntent ? event.deltaX : event.deltaY;" in template
    assert "event.deltaX > 0 || event.deltaY > 0" not in template
