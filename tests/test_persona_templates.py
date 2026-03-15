import pytest
from adclaw.agents.persona_templates import TEMPLATES, get_template
from adclaw.config.config import PersonaConfig


class TestPersonaTemplates:
    def test_five_templates_exist(self):
        assert len(TEMPLATES) == 5

    def test_template_ids(self):
        ids = {t["id"] for t in TEMPLATES}
        assert ids == {"researcher", "content-writer", "seo-specialist", "ads-manager", "social-media"}

    def test_get_template_by_id(self):
        t = get_template("researcher")
        assert t is not None
        assert t["name"] == "Researcher"
        assert len(t["soul_md"]) > 50

    def test_get_unknown_template(self):
        assert get_template("nope") is None

    def test_templates_have_required_fields(self):
        for t in TEMPLATES:
            assert "id" in t
            assert "name" in t
            assert "soul_md" in t
            assert "skills" in t
            assert "mcp_clients" in t

    def test_all_templates_valid_personas(self):
        for t in TEMPLATES:
            p = PersonaConfig(**t)
            assert p.id
            assert p.name

    def test_get_template_returns_copy(self):
        t1 = get_template("researcher")
        t2 = get_template("researcher")
        t1["name"] = "Modified"
        assert t2["name"] == "Researcher"
