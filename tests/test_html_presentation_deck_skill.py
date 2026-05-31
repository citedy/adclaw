from pathlib import Path
import re

from adclaw.agents.skill_scanner import SkillSecurityScanner


SKILL_DIR = Path(__file__).resolve().parents[1] / "src/adclaw/agents/skills/html-presentation-deck"
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
BANNED_TERMS = [
    "gui" + "zang",
    "sw" + "iss",
    "zh" + "-CN",
    "Noto Sans " + "SC",
    "Noto Serif " + "SC",
]
BANNED_RE = re.compile("|".join(re.escape(term) for term in BANNED_TERMS), re.IGNORECASE)


def test_html_presentation_deck_has_no_cjk_or_banned_terms():
    for path in SKILL_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".html", ".py", ".json", ".txt"}:
            text = path.read_text(encoding="utf-8")
            assert not CJK_RE.search(text), f"CJK text found in {path.relative_to(SKILL_DIR)}"
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


def test_html_presentation_deck_static_scan_is_safe():
    result = SkillSecurityScanner().scan_skill(SKILL_DIR)
    assert result.safe is True
    assert result.critical_count == 0
