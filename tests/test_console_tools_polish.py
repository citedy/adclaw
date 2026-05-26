from urllib.error import HTTPError

import pytest

from adclaw.agents.skills_manager import SkillInfo


def _skill(name: str, source: str) -> SkillInfo:
    return SkillInfo(
        name=name,
        content=f"---\nname: {name}\ndescription: Test.\n---\n# {name}",
        source=source,
        path=f"/tmp/{source}/{name}",
        references={},
        scripts={},
    )


def test_effective_skills_prefers_customized_over_builtin_duplicate():
    from adclaw.app.routers.skills import _effective_skills

    result = _effective_skills(
        [
            _skill("seo-plan", "builtin"),
            _skill("seo-plan", "customized"),
            _skill("seo-audit", "builtin"),
        ],
    )

    by_name = {skill.name: skill for skill in result}
    assert set(by_name) == {"seo-plan", "seo-audit"}
    assert by_name["seo-plan"].source == "customized"
    assert by_name["seo-audit"].source == "builtin"


@pytest.mark.asyncio
async def test_citedy_status_marks_unauthorized_key_as_invalid(monkeypatch):
    from adclaw.app.routers import citedy

    def fake_urlopen(*_args, **_kwargs):
        raise HTTPError(
            url="https://www.citedy.com/api/agent/me",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(citedy, "load_envs", lambda: {"CITEDY_API_KEY": "citedy_agent_secret"})
    monkeypatch.setattr(citedy, "urlopen", fake_urlopen)

    result = await citedy.citedy_status()

    assert result["configured"] is True
    assert result["status"] == "invalid"
    assert result["balance"] is None
    assert result["error"] == "Citedy key needs reconnect"
