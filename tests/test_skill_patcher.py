# -*- coding: utf-8 -*-
"""Tests for self-patching skills."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from adclaw.agents.tools.skill_patcher import (
    patch_skill_script,
    get_patch_history,
    reset_session_counts,
    _MAX_PATCHES_PER_SESSION,
)


@pytest.fixture(autouse=True)
def _reset_counts():
    """Reset session patch counters before each test."""
    reset_session_counts()
    yield
    reset_session_counts()


@pytest.fixture
def skill_dirs(tmp_path):
    """Create mock customized and active skill directories."""
    customized = tmp_path / "customized_skills"
    active = tmp_path / "active_skills"
    customized.mkdir()
    active.mkdir()

    # Create a test skill
    skill_dir = customized / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Test Skill")
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "process.py").write_text(
        'def process(data):\n    return data.split(",")\n'
    )

    # Also in active
    active_skill = active / "test_skill"
    active_skill.mkdir()
    active_scripts = active_skill / "scripts"
    active_scripts.mkdir()
    (active_scripts / "process.py").write_text(
        'def process(data):\n    return data.split(",")\n'
    )

    return customized, active


class TestSkillPatcher:
    def test_patch_creates_backup(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            result = patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content='def process(data):\n    return data.strip().split(",")\n',
                error_traceback="AttributeError: ...",
                fix_description="Added strip() before split",
            )
            assert result["success"] is True
            assert "backup_path" in result

            # Verify backup exists
            backups = list(
                (customized / "test_skill" / "scripts").glob("*.bak.*")
            )
            assert len(backups) == 1

    def test_patch_updates_content(self, skill_dirs):
        customized, active = skill_dirs
        new_code = 'def process(data):\n    return data.strip().split(",")\n'
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content=new_code,
            )
            content = (
                customized / "test_skill" / "scripts" / "process.py"
            ).read_text()
            assert "strip()" in content

    def test_patch_updates_active_copy(self, skill_dirs):
        customized, active = skill_dirs
        new_code = 'def process(data):\n    return data.strip().split(",")\n'
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content=new_code,
            )
            active_content = (
                active / "test_skill" / "scripts" / "process.py"
            ).read_text()
            assert "strip()" in active_content

    def test_patch_saves_record(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content="# fixed\n",
                error_traceback="Error: ...",
                fix_description="Fixed it",
            )
            patches_dir = customized / "test_skill" / ".patches"
            assert patches_dir.exists()
            records = list(patches_dir.glob("*.json"))
            assert len(records) == 1
            data = json.loads(records[0].read_text())
            assert data["script"] == "scripts/process.py"

    def test_rate_limit_enforced(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            for i in range(_MAX_PATCHES_PER_SESSION):
                result = patch_skill_script(
                    skill_name="test_skill",
                    script_path="scripts/process.py",
                    new_content=f"# version {i}\n",
                )
                assert result["success"] is True

            # Next attempt should be blocked
            result = patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content="# too many\n",
            )
            assert result["success"] is False
            assert "Maximum" in result["message"]

    def test_nonexistent_skill(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            result = patch_skill_script(
                skill_name="nonexistent",
                script_path="scripts/x.py",
                new_content="# nope\n",
            )
            assert result["success"] is False

    def test_path_traversal_blocked(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            result = patch_skill_script(
                skill_name="test_skill",
                script_path="../../etc/passwd",
                new_content="hacked\n",
            )
            assert result["success"] is False

    def test_get_patch_history(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content="# v1\n",
                fix_description="First fix",
            )
            patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content="# v2\n",
                fix_description="Second fix",
            )
            history = get_patch_history("test_skill")
            assert len(history) == 2

    def test_attempts_remaining(self, skill_dirs):
        customized, active = skill_dirs
        with patch(
            "adclaw.agents.tools.skill_patcher._get_skill_dirs",
            return_value=(customized, active),
        ):
            result = patch_skill_script(
                skill_name="test_skill",
                script_path="scripts/process.py",
                new_content="# v1\n",
            )
            assert result["attempts_remaining"] == _MAX_PATCHES_PER_SESSION - 1
