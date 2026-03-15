# -*- coding: utf-8 -*-
"""Skill quality evaluation — checks frontmatter, description, directives, jargon."""

import re
from dataclasses import dataclass, field
from pathlib import Path


DIRECTIVE_VERBS = {
    "extract", "scrape", "analyze", "generate", "create", "find", "search",
    "monitor", "track", "build", "optimize", "audit", "evaluate", "detect",
    "route", "delegate", "check", "validate", "run", "execute", "deploy",
    "configure", "install", "update", "remove", "list", "fetch", "parse",
    "transform", "convert", "filter", "sort", "rank", "score", "classify",
    "summarize", "report", "notify", "send", "receive", "connect", "sync",
    "help", "assist", "guide", "recommend", "suggest", "act", "use",
}

JARGON_PATTERNS = [
    r"\bsynerg", r"\bleverage\b", r"\bparadigm\b", r"\bholistic\b",
    r"\brobust\b", r"\bscalable\b", r"\bseamless\b", r"\bcut(?:ting)?[- ]edge\b",
    r"\bnext[- ]gen(?:eration)?\b", r"\bgame[- ]chang", r"\bworld[- ]class\b",
    r"\bbest[- ]in[- ]class\b", r"\binnovative\b", r"\bstate[- ]of[- ]the[- ]art\b",
]


def _parse_frontmatter(content: str) -> dict | None:
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    fm = {}
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


@dataclass
class QualityResult:
    passed: bool
    score: int  # 0-100
    warnings: list[str] = field(default_factory=list)
    skill_name: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "warnings": self.warnings,
            "skill_name": self.skill_name,
        }


def evaluate_skill_quality(skill_dir: Path, skill_name: str = "") -> QualityResult:
    """Run quality checks on a skill's SKILL.md."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return QualityResult(
            passed=False, score=0,
            warnings=["SKILL.md not found"],
            skill_name=skill_name or skill_dir.name,
        )

    content = skill_md.read_text(encoding="utf-8")
    warnings: list[str] = []
    score = 100
    name = skill_name or skill_dir.name

    fm = _parse_frontmatter(content)
    if fm is None:
        warnings.append("Missing YAML frontmatter (---)")
        score -= 30
    else:
        if not fm.get("name"):
            warnings.append("Missing 'name' in frontmatter")
            score -= 20
        desc = fm.get("description", "")
        if len(desc) < 40:
            warnings.append(f"Description too short ({len(desc)} chars, need >= 40)")
            score -= 15
        else:
            desc_lower = desc.lower()
            has_verb = any(
                desc_lower.startswith(v) or f" {v} " in f" {desc_lower} "
                for v in DIRECTIVE_VERBS
            )
            if not has_verb:
                warnings.append("Description lacks directive verb")
                score -= 10

    for pattern in JARGON_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            warnings.append(f"Jargon detected: '{matches[0]}'")
            score -= 5

    body = re.sub(r"^---.*?---", "", content, count=1, flags=re.DOTALL).strip()
    if len(body) < 100:
        warnings.append(f"Body too short ({len(body)} chars)")
        score -= 10

    if "## " not in body:
        warnings.append("No section headers found in body")
        score -= 10

    score = max(0, score)
    passed = score >= 60 and "not found" not in " ".join(warnings)

    return QualityResult(passed=passed, score=score, warnings=warnings, skill_name=name)
