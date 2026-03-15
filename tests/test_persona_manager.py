import os
import pytest
import tempfile
from adclaw.agents.persona_manager import PersonaManager
from adclaw.config.config import PersonaConfig


class TestPersonaManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.personas = [
            PersonaConfig(id="researcher", name="Researcher", soul_md="## Research\nFind facts."),
            PersonaConfig(id="content", name="Content Writer", soul_md="## Writer\nCreate content."),
            PersonaConfig(id="coordinator", name="Coordinator", is_coordinator=True),
        ]
        self.manager = PersonaManager(working_dir=self.tmpdir, personas=self.personas)

    def test_init_creates_dirs(self):
        self.manager.ensure_dirs()
        assert os.path.isdir(os.path.join(self.tmpdir, "agents", "researcher"))
        assert os.path.isdir(os.path.join(self.tmpdir, "agents", "content"))
        assert os.path.isdir(os.path.join(self.tmpdir, "agents", "researcher", "memory"))
        assert os.path.isdir(os.path.join(self.tmpdir, "shared", "researcher"))

    def test_get_persona_by_id(self):
        p = self.manager.get_persona("researcher")
        assert p.name == "Researcher"

    def test_get_persona_not_found(self):
        assert self.manager.get_persona("nonexistent") is None

    def test_get_coordinator(self):
        c = self.manager.get_coordinator()
        assert c.id == "coordinator"

    def test_get_coordinator_none(self):
        mgr = PersonaManager(working_dir=self.tmpdir, personas=[PersonaConfig(id="a", name="A")])
        assert mgr.get_coordinator() is None

    def test_get_working_dir_for_persona(self):
        d = self.manager.get_working_dir("researcher")
        assert d.endswith("agents/researcher")

    def test_get_shared_dir_for_persona(self):
        d = self.manager.get_shared_dir("researcher")
        assert d.endswith("shared/researcher")

    def test_resolve_tag_from_message(self):
        assert self.manager.resolve_tag("@researcher найди тренды AI") == "researcher"

    def test_resolve_tag_no_tag(self):
        assert self.manager.resolve_tag("просто сообщение") is None

    def test_resolve_tag_unknown(self):
        assert self.manager.resolve_tag("@unknown что-то") is None

    def test_strip_tag_from_message(self):
        assert self.manager.strip_tag("@researcher найди тренды AI") == "найди тренды AI"

    def test_list_all_personas_summary(self):
        summary = self.manager.get_team_summary()
        assert "researcher" in summary
        assert "Content Writer" in summary

    def test_list_shared_files(self):
        self.manager.ensure_dirs()
        shared = self.manager.get_shared_dir("researcher")
        with open(os.path.join(shared, "report.md"), "w") as f:
            f.write("# Report")
        files = self.manager.list_shared_files("researcher")
        assert "report.md" in files

    def test_all_personas_property(self):
        assert len(self.manager.all_personas) == 3

    def test_empty_personas(self):
        mgr = PersonaManager(working_dir=self.tmpdir, personas=[])
        assert mgr.get_coordinator() is None
        assert mgr.resolve_tag("@test hi") is None
        assert mgr.all_personas == []
