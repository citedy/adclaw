# -*- coding: utf-8 -*-
import pytest
from adclaw.config.config import PersonaConfig, PersonaCronConfig
from adclaw.app.crons.persona_sync import build_persona_cron_jobs, get_persona_cron_job_ids


class TestPersonaCron:
    def test_build_jobs_from_personas(self):
        personas = [
            PersonaConfig(id="researcher", name="Researcher", cron=PersonaCronConfig(
                enabled=True, schedule="0 8,14,20 * * *", prompt="Scan for trends", output="both"
            )),
            PersonaConfig(id="content", name="Content"),  # no cron
            PersonaConfig(id="seo", name="SEO", cron=PersonaCronConfig(
                enabled=False, schedule="0 9 * * *", prompt="Check rankings"
            )),  # disabled
        ]
        jobs = build_persona_cron_jobs(personas)
        assert len(jobs) == 1
        assert jobs[0]["id"] == "persona_researcher"
        assert jobs[0]["schedule"] == "0 8,14,20 * * *"
        assert jobs[0]["output_mode"] == "both"

    def test_empty_personas(self):
        assert build_persona_cron_jobs([]) == []

    def test_cron_missing_schedule(self):
        personas = [PersonaConfig(id="x", name="X", cron=PersonaCronConfig(enabled=True, prompt="do it"))]
        jobs = build_persona_cron_jobs(personas)
        assert len(jobs) == 0  # missing schedule

    def test_cron_missing_prompt(self):
        personas = [PersonaConfig(id="x", name="X", cron=PersonaCronConfig(enabled=True, schedule="0 8 * * *"))]
        jobs = build_persona_cron_jobs(personas)
        assert len(jobs) == 0  # missing prompt

    def test_get_job_ids(self):
        personas = [
            PersonaConfig(id="a", name="A", cron=PersonaCronConfig(enabled=True, schedule="0 8 * * *", prompt="do a")),
            PersonaConfig(id="b", name="B"),
        ]
        ids = get_persona_cron_job_ids(personas)
        assert ids == {"persona_a"}

    def test_multiple_cron_personas(self):
        personas = [
            PersonaConfig(id="a", name="A", cron=PersonaCronConfig(enabled=True, schedule="0 8 * * *", prompt="a")),
            PersonaConfig(id="b", name="B", cron=PersonaCronConfig(enabled=True, schedule="0 9 * * *", prompt="b")),
        ]
        jobs = build_persona_cron_jobs(personas)
        assert len(jobs) == 2
        ids = {j["id"] for j in jobs}
        assert ids == {"persona_a", "persona_b"}
