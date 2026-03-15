import os
import tempfile
import pytest
from pathlib import Path
from adclaw.agents.prompt import PromptBuilder
from adclaw.config.config import PersonaConfig


class TestPromptBuilderPersona:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "AGENTS.md"), "w") as f:
            f.write("## Rules\nFollow instructions.")
        with open(os.path.join(self.tmpdir, "SOUL.md"), "w") as f:
            f.write("## Default Soul\nBe helpful.")
        with open(os.path.join(self.tmpdir, "PROFILE.md"), "w") as f:
            f.write("## Profile\nUser: test")

    def test_default_build_unchanged(self):
        builder = PromptBuilder(working_dir=Path(self.tmpdir))
        prompt = builder.build()
        assert "Default Soul" in prompt
        assert "AGENTS.md" in prompt

    def test_persona_overrides_soul(self):
        persona = PersonaConfig(id="researcher", name="Researcher", soul_md="## Researcher Soul\nYou find facts only.")
        builder = PromptBuilder(working_dir=Path(self.tmpdir), persona=persona)
        prompt = builder.build()
        assert "Researcher Soul" in prompt
        assert "Default Soul" not in prompt
        assert "AGENTS.md" in prompt
        assert "Profile" in prompt

    def test_persona_empty_soul_uses_file(self):
        persona = PersonaConfig(id="test", name="Test", soul_md="")
        builder = PromptBuilder(working_dir=Path(self.tmpdir), persona=persona)
        prompt = builder.build()
        assert "Default Soul" in prompt

    def test_team_summary_injected(self):
        builder = PromptBuilder(working_dir=Path(self.tmpdir), team_summary="## Your Team\n- @researcher: finds facts")
        prompt = builder.build()
        assert "Your Team" in prompt
        assert "@researcher" in prompt

    def test_persona_and_team_summary(self):
        persona = PersonaConfig(id="r", name="R", soul_md="## Custom\nCustom soul.")
        builder = PromptBuilder(working_dir=Path(self.tmpdir), persona=persona, team_summary="## Team\n- @r: custom")
        prompt = builder.build()
        assert "Custom soul" in prompt
        assert "Team" in prompt
        assert "Default Soul" not in prompt
