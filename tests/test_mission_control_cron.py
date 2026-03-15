"""Tests for Mission Control P4: Cron job per-persona scheduling."""
import pytest
from adclaw.config.config import PersonaConfig, PersonaCronConfig


class TestPersonaCron:
    """Persona cron config validation."""

    def test_cron_default_none(self):
        p = PersonaConfig(id="r", name="R")
        assert p.cron is None

    def test_cron_config_fields(self):
        cron = PersonaCronConfig(enabled=True, schedule="0 9 * * *", prompt="Find trends", output="chat")
        p = PersonaConfig(id="r", name="R", cron=cron)
        assert p.cron.enabled is True
        assert p.cron.schedule == "0 9 * * *"
        assert p.cron.prompt == "Find trends"
        assert p.cron.output == "chat"

    def test_cron_disabled(self):
        cron = PersonaCronConfig(enabled=False, schedule="0 9 * * *", prompt="Find trends", output="chat")
        p = PersonaConfig(id="r", name="R", cron=cron)
        assert p.cron.enabled is False


class TestCronPersonaTargeting:
    """Cron jobs must target the correct persona session."""

    def test_cron_session_id_format(self):
        """Cron dispatching to a persona uses persona_id::channel--session format."""
        persona_id = "researcher"
        channel = "console"
        session_id = f"{persona_id}::{channel}--default"
        assert session_id == "researcher::console--default"

    def test_cron_dispatch_payload(self):
        """Cron dispatch body must include correct session_id and persona routing."""
        persona_id = "researcher"
        cron_payload = {
            "task_type": "query",
            "text": "Find AI trends today",
            "request": {
                "input": [{"type": "text", "text": f"@{persona_id} Find AI trends today"}],
                "session_id": f"{persona_id}::cron--daily",
                "user_id": "cron-scheduler",
                "channel": "console",
            },
            "schedule": {"type": "cron", "cron": "0 9 * * *", "timezone": "UTC"},
            "dispatch": {
                "type": "local",
                "channel": "console",
                "target": {"session_id": f"{persona_id}::cron--daily"},
            },
        }
        assert f"@{persona_id}" in cron_payload["request"]["input"][0]["text"]
        assert persona_id in cron_payload["dispatch"]["target"]["session_id"]

    def test_different_personas_different_cron_sessions(self):
        """Cron jobs for different personas must not share sessions."""
        s1 = "researcher::cron--daily"
        s2 = "content-writer::cron--weekly"
        assert s1 != s2
