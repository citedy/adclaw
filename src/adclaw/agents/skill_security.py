"""Security score computation and caching for skills."""
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .skill_scanner import ScanResult

logger = logging.getLogger(__name__)

SEVERITY_DEDUCTIONS = {
    "critical": 25,
    "high": 15,
    "medium": 8,
    "low": 3,
}

CACHE_FILE = ".scan.json"


def compute_security_score(scan_result: ScanResult) -> int:
    """Compute 0-100 security score from scan findings."""
    score = 100
    for f in scan_result.findings:
        score -= SEVERITY_DEDUCTIONS.get(f.severity, 3)
    return max(0, score)


def _file_hash(skill_dir: Path) -> str:
    """Hash all scannable files in skill dir."""
    h = hashlib.sha256()
    for f in sorted(skill_dir.rglob("*")):
        if f.is_file() and f.name != CACHE_FILE and not f.name.endswith(".bak"):
            h.update(f.read_bytes())
    return h.hexdigest()


def write_scan_cache(skill_dir: Path, data: dict) -> None:
    """Write scan result cache."""
    data["file_hash"] = _file_hash(skill_dir)
    data["scanned_at"] = datetime.now(timezone.utc).isoformat()
    cache_path = skill_dir / CACHE_FILE
    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_scan_cache(skill_dir: Path) -> Optional[dict]:
    """Read cached scan result. Returns None if stale or missing."""
    cache_path = skill_dir / CACHE_FILE
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if data.get("file_hash") != _file_hash(skill_dir):
            return None
        return data
    except (json.JSONDecodeError, KeyError):
        return None


def scan_and_cache(skill_dir: Path, skill_name: str) -> dict:
    """Run pattern scan, compute score, cache result."""
    from .skill_scanner import SkillSecurityScanner

    cached = read_scan_cache(skill_dir)
    if cached is not None:
        return cached

    scanner = SkillSecurityScanner()
    result = scanner.scan_skill(skill_dir, skill_name)
    score = compute_security_score(result)

    data = {
        "score": score,
        "pattern_scan": "pass" if result.safe else "fail",
        "llm_audit": "pending",
        "auto_healed": False,
        "findings_count": len(result.findings),
        "findings": [
            {"severity": f.severity, "category": f.category, "description": f.description}
            for f in result.findings
        ],
    }
    write_scan_cache(skill_dir, data)
    return data
