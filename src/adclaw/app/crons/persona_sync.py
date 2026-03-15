# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from ...config.config import PersonaConfig

logger = logging.getLogger(__name__)


def build_persona_cron_jobs(personas: list[PersonaConfig]) -> list[dict]:
    """Build cron job specifications from persona configs.

    Returns list of dicts with job details for personas that have cron enabled.
    These can be used to create/update jobs via the cron REST API.
    """
    jobs = []
    for persona in personas:
        if not persona.cron or not persona.cron.enabled:
            continue
        if not persona.cron.schedule or not persona.cron.prompt:
            logger.warning(
                "Persona '%s' has cron enabled but missing schedule/prompt",
                persona.id,
            )
            continue
        jobs.append({
            "id": f"persona_{persona.id}",
            "name": f"Persona: {persona.name}",
            "enabled": True,
            "schedule": persona.cron.schedule,
            "prompt": persona.cron.prompt,
            "persona_id": persona.id,
            "output_mode": persona.cron.output,
        })
    return jobs


def get_persona_cron_job_ids(personas: list[PersonaConfig]) -> set[str]:
    """Get set of expected cron job IDs for all personas."""
    return {f"persona_{p.id}" for p in personas if p.cron and p.cron.enabled}
