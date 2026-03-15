import pytest
from pydantic import ValidationError
from adclaw.config.config import PersonaConfig, PersonaCronConfig, AgentsConfig, Config, validate_single_coordinator


class TestPersonaConfig:
    def test_persona_defaults(self):
        p = PersonaConfig(id="researcher", name="Researcher")
        assert p.id == "researcher"
        assert p.name == "Researcher"
        assert p.soul_md == ""
        assert p.model_provider == ""
        assert p.model_name == ""
        assert p.skills == []
        assert p.mcp_clients == []
        assert p.is_coordinator is False
        assert p.cron is None

    def test_persona_with_cron(self):
        p = PersonaConfig(
            id="news",
            name="News Agent",
            soul_md="## Role\nYou find news.",
            cron=PersonaCronConfig(enabled=True, schedule="0 8 * * *", prompt="Find trending news", output="both"),
        )
        assert p.cron.enabled is True
        assert p.cron.output == "both"

    def test_agents_config_empty_personas(self):
        ac = AgentsConfig()
        assert ac.personas == []

    def test_agents_config_with_personas(self):
        ac = AgentsConfig(personas=[
            PersonaConfig(id="r", name="R"),
            PersonaConfig(id="c", name="C", is_coordinator=True),
        ])
        assert len(ac.personas) == 2

    def test_config_round_trip(self):
        cfg = Config(agents=AgentsConfig(personas=[
            PersonaConfig(id="test", name="Test", soul_md="Be helpful.", model_provider="aliyun-intl", model_name="qwen3.5-plus")
        ]))
        data = cfg.model_dump()
        cfg2 = Config(**data)
        assert len(cfg2.agents.personas) == 1
        assert cfg2.agents.personas[0].soul_md == "Be helpful."

    def test_persona_id_validation(self):
        with pytest.raises(ValidationError):
            PersonaConfig(id="bad id!", name="Bad")

    def test_persona_id_valid_chars(self):
        p = PersonaConfig(id="my-agent_01", name="Agent")
        assert p.id == "my-agent_01"

    def test_only_one_coordinator(self):
        personas = [
            PersonaConfig(id="a", name="A", is_coordinator=True),
            PersonaConfig(id="b", name="B", is_coordinator=True),
        ]
        with pytest.raises(ValueError):
            validate_single_coordinator(personas)

    def test_single_coordinator_ok(self):
        personas = [
            PersonaConfig(id="a", name="A", is_coordinator=True),
            PersonaConfig(id="b", name="B"),
        ]
        validate_single_coordinator(personas)  # should not raise
