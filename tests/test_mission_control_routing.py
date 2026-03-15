"""Tests for Mission Control P1: @mention persona routing."""
import pytest
from adclaw.agents.persona_manager import PersonaManager
from adclaw.config.config import PersonaConfig


class TestMentionRouting:
    """@tag resolution — the core of persona-based chat."""

    def test_at_tag_routes_to_researcher(self, persona_manager):
        assert persona_manager.resolve_tag("@researcher find AI trends") == "researcher"

    def test_at_tag_routes_to_writer(self, persona_manager):
        assert persona_manager.resolve_tag("@content-writer draft blog post") == "content-writer"

    def test_at_tag_by_name(self, persona_manager):
        """Should match persona.name (case-insensitive), not just ID."""
        assert persona_manager.resolve_tag("@Mike find trends") == "researcher"
        assert persona_manager.resolve_tag("@Mira write a post") == "content-writer"

    def test_no_tag_returns_none(self, persona_manager):
        assert persona_manager.resolve_tag("just a message") is None

    def test_unknown_tag_returns_none(self, persona_manager):
        assert persona_manager.resolve_tag("@nonexistent do stuff") is None

    def test_coordinator_is_default(self, persona_manager):
        coord = persona_manager.get_coordinator()
        assert coord is not None
        assert coord.id == "coordinator"
        assert coord.is_coordinator is True

    def test_strip_tag(self, persona_manager):
        assert persona_manager.strip_tag("@researcher find trends") == "find trends"
        assert persona_manager.strip_tag("no tag here") == "no tag here"

    def test_case_insensitive_tag(self, persona_manager):
        assert persona_manager.resolve_tag("@Researcher find trends") == "researcher"
        assert persona_manager.resolve_tag("@RESEARCHER find trends") == "researcher"


class TestSessionScoping:
    """Session IDs must be unique per persona to isolate conversations."""

    def test_persona_session_format(self):
        """Web chat tabs use format: persona_id::console--default"""
        session = "researcher::console--default"
        parts = session.split("::")
        assert parts[0] == "researcher"
        assert parts[1] == "console--default"

    def test_different_personas_different_sessions(self):
        s1 = "researcher::console--default"
        s2 = "content-writer::console--default"
        assert s1 != s2

    def test_all_tab_uses_empty_session(self):
        """'All' tab sends empty session_id -> coordinator handles it."""
        s_all = ""
        s_persona = "researcher::console--default"
        assert s_all != s_persona

    def test_telegram_session_format(self):
        """Telegram sessions: persona_id::telegram--chat_id"""
        session = "researcher::telegram--123456789"
        assert session.startswith("researcher::")


class TestTeamSummary:
    """Team summary injected into system prompt."""

    def test_team_summary_includes_all(self, persona_manager):
        summary = persona_manager.get_team_summary()
        assert "@coordinator" in summary
        assert "@researcher" in summary
        assert "@content-writer" in summary

    def test_team_summary_marks_coordinator(self, persona_manager):
        summary = persona_manager.get_team_summary()
        assert "(coordinator)" in summary

    def test_team_summary_includes_roles(self, persona_manager):
        summary = persona_manager.get_team_summary()
        assert "## Role" in summary  # soul_md first line is used as role description
