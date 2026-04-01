# -*- coding: utf-8 -*-
"""Analysis-first skill security validation using LLM.

Enforces structured reasoning before verdict: ANALYSIS → FINDINGS → VERDICT.
Inspired by Claude Code's verification contract pattern.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Literal, Optional

from .skill_scanner import Finding, ScanResult, SkillSecurityScanner

logger = logging.getLogger(__name__)


def _finding_to_dict(f: Finding) -> dict:
    """Convert a static Finding to a plain dict for merged results."""
    return {
        "severity": f.severity,
        "category": f.category,
        "description": f.description,
        "file": f.file,
        "line": f.line,
    }

# ---------------------------------------------------------------------------
# Skill categories with domain-specific security criteria
# ---------------------------------------------------------------------------

SkillCategory = Literal[
    "seo", "marketing", "browser", "data", "social", "analytics", "office", "general"
]

CATEGORY_CRITERIA: dict[SkillCategory, list[str]] = {
    "seo": [
        "Respects robots.txt and crawl rate limits",
        "Does not scrape competitor sites without explicit user configuration",
        "Validates URLs before fetching (no SSRF via user-controlled input)",
    ],
    "marketing": [
        "Complies with CAN-SPAM / GDPR for any email or messaging",
        "Does not auto-post to social media without user confirmation",
        "Rate-limits any bulk outreach operations",
    ],
    "browser": [
        "No credential harvesting from forms or cookies",
        "No cross-site scripting (XSS) via injected content",
        "Respects same-origin policy and does not exfiltrate page data",
    ],
    "data": [
        "No data exfiltration to external endpoints",
        "Validates file paths to prevent directory traversal",
        "Sanitizes any SQL or query parameters",
    ],
    "social": [
        "Respects platform API rate limits and ToS",
        "Does not automate follow/unfollow or engagement farming",
        "No scraping of private or protected content",
    ],
    "analytics": [
        "Does not collect PII without explicit consent",
        "Validates data sources before processing",
        "No unauthorized access to analytics dashboards",
    ],
    "office": [
        "Does not access files outside designated workspace",
        "Validates file formats before processing",
        "No macro execution in documents",
    ],
    "general": [
        "No unexpected network access",
        "No file system writes outside working directory",
        "No environment variable access for secrets",
    ],
}

# Keyword signals for category detection
_CATEGORY_SIGNALS: dict[SkillCategory, list[str]] = {
    "seo": ["seo", "keyword", "backlink", "serp", "ranking", "crawl", "sitemap", "meta"],
    "marketing": ["email", "campaign", "newsletter", "outreach", "lead", "crm", "funnel"],
    "browser": ["browser", "playwright", "selenium", "puppeteer", "chrome", "screenshot", "navigate"],
    "data": ["csv", "json", "database", "sql", "export", "import", "parse", "transform"],
    "social": ["twitter", "linkedin", "instagram", "tiktok", "reddit", "post", "engagement"],
    "analytics": ["analytics", "metrics", "dashboard", "tracking", "report", "chart"],
    "office": ["pdf", "docx", "excel", "spreadsheet", "document", "presentation"],
}


def detect_skill_category(content: str) -> SkillCategory:
    """Detect skill category from content using keyword signals."""
    lower = content.lower()
    scores: dict[SkillCategory, int] = {cat: 0 for cat in _CATEGORY_SIGNALS}
    for cat, signals in _CATEGORY_SIGNALS.items():
        for signal in signals:
            if signal in lower:
                scores[cat] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


# ---------------------------------------------------------------------------
# LLM audit prompt
# ---------------------------------------------------------------------------

AUDIT_SYSTEM_PROMPT = """\
You are a security auditor for AI agent skills. Each skill is a YAML definition
with optional Python scripts that the agent can execute.

## Your Task
Analyze the skill code and produce a structured security assessment.

## MANDATORY Response Structure (JSON only):
{{
  "analysis": {{
    "purpose": "What does this skill do?",
    "data_flow": "What data does it read/write/send?",
    "external_interactions": "What external systems does it contact?",
    "permissions_needed": "What system permissions does it require?",
    "category_specific": "Assessment against the category criteria below"
  }},
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "description": "What is the issue",
      "file": "filename",
      "line": 0,
      "fix_suggestion": "How to fix it"
    }}
  ],
  "verdict": {{
    "safe": true|false,
    "confidence": 0.0-1.0,
    "reasoning": "Why this verdict"
  }}
}}

## Category-Specific Criteria ({category}):
{criteria}

## Static Scan Results (already completed):
{static_findings}

IMPORTANT: You MUST analyze before concluding. The analysis section is mandatory.
Output ONLY valid JSON. No markdown, no explanation outside JSON.
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Structured result of skill validation."""

    analysis: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    verdict: dict = field(default_factory=lambda: {"safe": True, "confidence": 0.0, "reasoning": ""})
    category: SkillCategory = "general"
    static_result: Optional[ScanResult] = field(default=None, repr=False)

    @property
    def should_block(self) -> bool:
        """True if any critical finding exists (static or LLM)."""
        if self.static_result and self.static_result.critical_count > 0:
            return True
        return any(f.get("severity") == "critical" for f in self.findings)

    @property
    def needs_acknowledgment(self) -> bool:
        """True if medium+ findings exist but no criticals."""
        if self.should_block:
            return False
        has_medium_plus = any(
            f.get("severity") in ("high", "medium") for f in self.findings
        )
        return has_medium_plus

    @property
    def is_clean(self) -> bool:
        return not self.should_block and not self.needs_acknowledgment

    def to_dict(self) -> dict:
        return {
            "analysis": self.analysis,
            "findings": self.findings,
            "verdict": self.verdict,
            "category": self.category,
            "should_block": self.should_block,
            "needs_acknowledgment": self.needs_acknowledgment,
            "is_clean": self.is_clean,
        }


_REQUIRED_ANALYSIS_KEYS = ("purpose", "data_flow", "external_interactions", "permissions_needed", "category_specific")


def _parse_llm_response(response_text: str) -> dict:
    """Parse structured JSON from LLM response."""
    # Try to extract JSON from markdown fences
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
    else:
        # Try to find raw JSON (first { to last })
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start >= 0 and end > start:
            raw = response_text[start : end + 1]
        else:
            raw = response_text.strip()

    data = json.loads(raw)

    # Validate required structure
    for key in ("analysis", "findings", "verdict"):
        if key not in data:
            raise ValueError(f"Missing required key: {key}")

    analysis = data["analysis"]
    if not isinstance(analysis, dict):
        raise ValueError(f"analysis must be a dict, got: {type(analysis).__name__}")
    for subkey in _REQUIRED_ANALYSIS_KEYS:
        if subkey not in analysis:
            raise ValueError(f"Missing analysis.{subkey}")

    return data


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------


async def validate_skill(
    skill_content: str,
    skill_name: str,
    llm_caller: Callable[[str], Coroutine[Any, Any, str]],
    scripts: Optional[dict[str, Any]] = None,
) -> ValidationResult:
    """Run analysis-first validation on a skill.

    1. Static pattern scan (instant)
    2. If critical found → block immediately (no LLM needed)
    3. Detect category → inject criteria
    4. LLM audit with structured prompt
    5. Parse and merge findings

    Args:
        skill_content: SKILL.md content
        skill_name: Name of the skill
        llm_caller: Async LLM function
        scripts: Optional dict of script filenames → content

    Returns:
        ValidationResult with analysis, findings, verdict
    """
    scanner = SkillSecurityScanner()

    # 1. Static scan — SKILL.md content + scripts separately
    static_result = scanner.scan_content(skill_content, skill_name)
    if scripts:
        # Use scan_scripts_content for Python scripts (AST + pattern analysis)
        scripts_result = scanner.scan_scripts_content(scripts, skill_name)
        static_result.findings.extend(scripts_result.findings)
        static_result.safe = static_result.safe and scripts_result.safe

    # 2. Critical short-circuit
    if static_result.critical_count > 0:
        logger.warning(
            "Skill '%s' blocked: %d critical findings from static scan",
            skill_name,
            static_result.critical_count,
        )
        return ValidationResult(
            analysis={"purpose": "Blocked before LLM audit", "data_flow": "N/A",
                       "external_interactions": "N/A", "permissions_needed": "N/A",
                       "category_specific": "N/A"},
            findings=[_finding_to_dict(f) for f in static_result.findings],
            verdict={"safe": False, "confidence": 1.0,
                     "reasoning": f"Blocked: {static_result.critical_count} critical findings from static scan"},
            category="general",
            static_result=static_result,
        )

    # 3. Detect category
    category = detect_skill_category(skill_content)
    criteria = CATEGORY_CRITERIA.get(category, CATEGORY_CRITERIA["general"])

    # 4. Build LLM prompt
    if static_result.findings:
        static_findings_text = "\n".join(
            f"- [{f.severity}] {f.description} ({f.file}:{f.line})"
            for f in static_result.findings
        )
    else:
        static_findings_text = "None"

    prompt = AUDIT_SYSTEM_PROMPT.format(
        category=category,
        criteria="\n".join(f"- {c}" for c in criteria),
        static_findings=static_findings_text,
    )

    user_content = f"## Skill: {skill_name}\n\n```yaml\n{skill_content[:5000]}\n```"
    if scripts:
        for fname, sc in list(scripts.items())[:3]:
            if isinstance(sc, str):
                user_content += f"\n\n## Script: {fname}\n```python\n{sc[:3000]}\n```"

    full_prompt = f"{prompt}\n\n{user_content}"

    # 5. Call LLM
    try:
        response_text = await llm_caller(full_prompt)
        data = _parse_llm_response(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM audit parse failed for '%s': %s", skill_name, exc)
        return ValidationResult(
            analysis={"purpose": "LLM audit failed", "data_flow": "Unknown",
                       "external_interactions": "Unknown", "permissions_needed": "Unknown",
                       "category_specific": "Unable to assess"},
            findings=[_finding_to_dict(f) for f in static_result.findings],
            verdict={"safe": static_result.safe, "confidence": 0.3,
                     "reasoning": f"LLM audit failed: {exc}. Static scan only."},
            category=category,
            static_result=static_result,
        )
    except Exception as exc:
        logger.exception("LLM audit error for '%s': %s", skill_name, exc)
        return ValidationResult(
            findings=[_finding_to_dict(f) for f in static_result.findings],
            verdict={"safe": static_result.safe, "confidence": 0.2,
                     "reasoning": f"LLM audit error: {exc}"},
            category=category,
            static_result=static_result,
        )

    # 6. Merge static + LLM findings
    merged_findings = [_finding_to_dict(f) for f in static_result.findings]
    merged_findings.extend(data.get("findings", []))

    return ValidationResult(
        analysis=data.get("analysis", {}),
        findings=merged_findings,
        verdict=data.get("verdict", {"safe": True, "confidence": 0.0, "reasoning": ""}),
        category=category,
        static_result=static_result,
    )
