import pytest
import json
from pathlib import Path
from adclaw.agents.skill_scanner import Finding, ScanResult


def test_compute_score_clean():
    from adclaw.agents.skill_security import compute_security_score
    scan = ScanResult(safe=True, skill_name="test", findings=[], files_scanned=3)
    assert compute_security_score(scan) == 100


def test_compute_score_critical():
    from adclaw.agents.skill_security import compute_security_score
    findings = [Finding(severity="critical", description="exec found")]
    scan = ScanResult(safe=False, skill_name="test", findings=findings, files_scanned=1)
    assert compute_security_score(scan) == 75


def test_compute_score_multiple():
    from adclaw.agents.skill_security import compute_security_score
    findings = [
        Finding(severity="critical", description="a"),
        Finding(severity="high", description="b"),
        Finding(severity="medium", description="c"),
        Finding(severity="low", description="d"),
    ]
    scan = ScanResult(safe=False, skill_name="test", findings=findings, files_scanned=2)
    assert compute_security_score(scan) == 49


def test_compute_score_floor_zero():
    from adclaw.agents.skill_security import compute_security_score
    findings = [Finding(severity="critical", description="x")] * 5
    scan = ScanResult(safe=False, skill_name="test", findings=findings, files_scanned=1)
    assert compute_security_score(scan) == 0


def test_cache_write_and_read(tmp_path):
    from adclaw.agents.skill_security import write_scan_cache, read_scan_cache
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# Test")

    data = {
        "score": 100,
        "pattern_scan": "pass",
        "llm_audit": "pending",
        "auto_healed": False,
        "findings": [],
    }
    write_scan_cache(skill_dir, data)

    cached = read_scan_cache(skill_dir)
    assert cached is not None
    assert cached["score"] == 100


def test_cache_invalidated_on_change(tmp_path):
    from adclaw.agents.skill_security import write_scan_cache, read_scan_cache
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# V1")

    write_scan_cache(skill_dir, {"score": 100})

    (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# V2")

    cached = read_scan_cache(skill_dir)
    assert cached is None


def test_scan_and_cache_integration(tmp_path):
    from adclaw.agents.skill_security import scan_and_cache

    skill_dir = tmp_path / "safe-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: safe-skill\ndescription: Safe.\n---\n# Safe")

    result = scan_and_cache(skill_dir, "safe-skill")
    assert result["score"] == 100
    assert result["pattern_scan"] == "pass"

    result2 = scan_and_cache(skill_dir, "safe-skill")
    assert result2["score"] == 100
