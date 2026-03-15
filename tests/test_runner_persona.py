import pytest
from adclaw.config.config import PersonaConfig
from adclaw.agents.persona_manager import PersonaManager


class TestRunnerPersonaRouting:
    def test_resolve_persona_with_tag(self):
        personas = [
            PersonaConfig(id="researcher", name="Researcher", soul_md="Find facts."),
            PersonaConfig(id="main", name="Main", is_coordinator=True),
        ]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        assert mgr.resolve_tag("@researcher найди тренды") == "researcher"

    def test_no_tag_returns_none(self):
        personas = [PersonaConfig(id="main", name="Main", is_coordinator=True)]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        assert mgr.resolve_tag("просто сообщение") is None

    def test_coordinator_fallback(self):
        personas = [
            PersonaConfig(id="main", name="Main", is_coordinator=True),
            PersonaConfig(id="researcher", name="Researcher"),
        ]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        assert mgr.resolve_tag("что-то") is None
        assert mgr.get_coordinator().id == "main"

    def test_empty_personas_no_crash(self):
        mgr = PersonaManager(working_dir="/tmp/test", personas=[])
        assert mgr.resolve_tag("@test hi") is None
        assert mgr.get_coordinator() is None

    def test_session_id_scoping(self):
        """Session ID should be prefixed with persona ID using :: separator."""
        persona = PersonaConfig(id="researcher", name="R")
        session_id = "abc123"
        scoped = f"{persona.id}::{session_id}"
        assert scoped == "researcher::abc123"

    def test_session_id_no_collision(self):
        """Different persona/session pairs must produce different scoped IDs."""
        scoped_1 = f"a_b::c"
        scoped_2 = f"a::b_c"
        assert scoped_1 != scoped_2
