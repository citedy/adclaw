"""Tests for CodeQL security fixes (PR #4).

Tests call actual production code rather than reimplementing logic,
so regressions in the real code are caught.
"""
import os
import inspect
import pytest
from pathlib import Path
from unittest.mock import patch


# --- SSRF whitelist tests (skills_hub.py) ---


class TestSSRFWhitelist:
    """Test that _http_get only allows whitelisted HTTPS hosts."""

    def test_allowed_hosts_include_clawhub(self):
        from adclaw.agents.skills_hub import _allowed_hosts

        hosts = _allowed_hosts()
        assert "clawhub.ai" in hosts
        assert "api.github.com" in hosts
        assert "raw.githubusercontent.com" in hosts
        assert "github.com" in hosts
        assert "skills.sh" in hosts

    def test_allowed_hosts_include_skillsmp(self):
        from adclaw.agents.skills_hub import _allowed_hosts

        hosts = _allowed_hosts()
        assert "skillsmp.com" in hosts
        assert "www.skillsmp.com" in hosts

    def test_allowed_hosts_dynamic_hub_url(self):
        from adclaw.agents.skills_hub import _allowed_hosts

        with patch.dict(os.environ, {"ADCLAW_SKILLS_HUB_BASE_URL": "https://custom-hub.example.com/api"}):
            hosts = _allowed_hosts()
            assert "custom-hub.example.com" in hosts

    def test_http_get_rejects_http(self):
        from adclaw.agents.skills_hub import _http_get

        with pytest.raises(ValueError, match="Only https"):
            _http_get("http://api.github.com/repos")

    def test_http_get_rejects_unknown_host(self):
        from adclaw.agents.skills_hub import _http_get

        with pytest.raises(ValueError, match="not in the allowed list"):
            _http_get("https://evil.com/steal-data")

    def test_http_get_rejects_ssrf_with_userinfo(self):
        from adclaw.agents.skills_hub import _http_get

        with pytest.raises(ValueError, match="not in the allowed list"):
            _http_get("https://api.github.com@evil.com/path")


# --- Path traversal tests (skills_manager.py) ---


class TestPathTraversal:
    """Test that load_skill_file blocks path traversal via the real method."""

    def test_dotdot_blocked(self):
        from adclaw.agents.skills_manager import SkillService

        svc = SkillService()
        result = svc.load_skill_file("some_skill", "../../etc/passwd", "builtin")
        assert result is None

    def test_absolute_path_blocked(self):
        from adclaw.agents.skills_manager import SkillService

        svc = SkillService()
        result = svc.load_skill_file("some_skill", "/etc/passwd", "builtin")
        assert result is None

    def test_invalid_prefix_blocked(self):
        from adclaw.agents.skills_manager import SkillService

        svc = SkillService()
        # Must start with references/ or scripts/
        result = svc.load_skill_file("some_skill", "secrets/keys.txt", "builtin")
        assert result is None

    def test_sibling_directory_blocked(self, tmp_path):
        """Call load_skill_file with a crafted path targeting a sibling dir."""
        from adclaw.agents.skills_manager import SkillService, get_builtin_skills_dir

        # Create sibling dirs: tmp/foo/ (skill) and tmp/foobar/scripts/evil.txt
        skills_base = tmp_path / "skills"
        skill_dir = skills_base / "foo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("name: foo")
        sibling = skills_base / "foobar"
        scripts_dir = sibling / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "evil.txt").write_text("secret")

        svc = SkillService()
        # Patch get_builtin_skills_dir to use our tmp dir
        with patch("adclaw.agents.skills_manager.get_builtin_skills_dir", return_value=skills_base):
            result = svc.load_skill_file("foo", "scripts/../../../foobar/scripts/evil.txt", "builtin")
        assert result is None, "Sibling directory access should be blocked"


# --- Hash algorithm test (react_agent.py) ---


class TestPromptHash:
    """Test that the actual agent code uses sha256, not md5."""

    def test_agent_hash_method_uses_sha256(self):
        """Inspect the actual source code of _prompt_source_hash to verify sha256."""
        from adclaw.agents.react_agent import AdClawAgent

        source = inspect.getsource(AdClawAgent._prompt_source_hash)
        assert "sha256" in source, "Agent should use sha256 for prompt hash"
        assert "md5" not in source, "Agent should not use md5"


# --- URL sanitization tests (actual production code) ---


class TestURLSanitization:
    """Test URL validation in actual production functions."""

    def test_citedy_mcp_config_validates_url(self):
        """MCPClientConfig should auto-inject auth only for exact mcp.citedy.com."""
        from adclaw.config.config import MCPClientConfig

        with patch.dict(os.environ, {"CITEDY_API_KEY": "test-key-123"}):
            # Valid Citedy URL — should inject Authorization
            cfg = MCPClientConfig(
                name="citedy", transport="streamable_http",
                url="https://mcp.citedy.com/sse",
            )
            assert "Authorization" in cfg.headers

            # Evil URL — should NOT inject Authorization
            cfg2 = MCPClientConfig(
                name="evil", transport="streamable_http",
                url="https://mcp.citedy.com.evil.com/sse",
            )
            assert "Authorization" not in cfg2.headers

    def test_github_hint_rejects_fake_domain(self):
        """_github_token_hint should not trigger for non-GitHub domains."""
        from adclaw.app.routers.skills import _github_token_hint

        assert _github_token_hint("https://notgithub.com/pkg") == ""
        assert _github_token_hint("https://evilgithub.com/pkg") == ""

    def test_github_hint_matches_real_github(self):
        from adclaw.app.routers.skills import _github_token_hint

        assert "GITHUB_TOKEN" in _github_token_hint("https://github.com/user/repo")
        assert "GITHUB_TOKEN" in _github_token_hint("https://api.github.com/repos")
        assert "GITHUB_TOKEN" in _github_token_hint("https://skills.sh/bundle")


# --- Env line length limit test (actual endpoint) ---


class TestEnvLineLengthLimit:
    """Test that the bulk_import endpoint skips long lines."""

    @pytest.mark.asyncio
    async def test_long_line_skipped_in_bulk_import(self):
        """Call the actual bulk_import with a long line and verify it's skipped."""
        from adclaw.app.routers.envs import bulk_import, BulkImportRequest

        long_val = "x" * 20000
        text = f"NORMAL_KEY=normal_value\nHUGE_KEY={long_val}\nANOTHER=ok"

        with patch("adclaw.app.routers.envs.load_envs", return_value={}), \
             patch("adclaw.app.routers.envs.save_envs"):
            result = await bulk_import(BulkImportRequest(text=text, merge=False))

        keys = [ev.key for ev in result]
        assert "NORMAL_KEY" in keys, "Normal key should be imported"
        assert "ANOTHER" in keys, "Another normal key should be imported"
        assert "HUGE_KEY" not in keys, "Long line should be skipped"


# --- Workflow permissions test ---


class TestWorkflowPermissions:
    """Test that workflow files have permissions block."""

    @pytest.mark.parametrize("workflow", [
        "docker-release.yml",
        "npm-format.yml",
        "pre-commit.yml",
    ])
    def test_has_permissions(self, workflow):
        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / workflow
        if not workflow_path.exists():
            pytest.skip(f"Workflow file {workflow} not found")
        content = workflow_path.read_text()
        assert "permissions:" in content, f"{workflow} missing permissions block"
        assert "contents: read" in content, f"{workflow} missing contents: read"
