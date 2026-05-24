import asyncio
from pathlib import Path

import pytest

from adclaw.agents.react_agent import AdClawAgent
from adclaw.app.mcp.manager import MCPClientManager
from adclaw.app.runner import runner as runner_module


class FakeToolkit:
    def __init__(self):
        self.registered = []

    def register_agent_skill(self, path):
        self.registered.append(Path(path).name)


def test_persona_selected_skills_register_from_builtin(monkeypatch, tmp_path):
    active = tmp_path / "active"
    customized = tmp_path / "customized"
    builtin = tmp_path / "builtin"
    for base in (active, customized, builtin):
        base.mkdir()
    (builtin / "seo").mkdir()
    (builtin / "seo" / "SKILL.md").write_text("# SEO\n", encoding="utf-8")
    (builtin / "ads").mkdir()
    (builtin / "ads" / "SKILL.md").write_text("# Ads\n", encoding="utf-8")

    monkeypatch.setattr(
        "adclaw.agents.react_agent.ensure_skills_initialized",
        lambda: None,
    )
    monkeypatch.setattr(
        "adclaw.agents.react_agent.get_working_skills_dir",
        lambda: active,
    )
    monkeypatch.setattr(
        "adclaw.agents.react_agent.get_customized_skills_dir",
        lambda: customized,
    )
    monkeypatch.setattr(
        "adclaw.agents.react_agent.get_builtin_skills_dir",
        lambda: builtin,
    )
    monkeypatch.setattr(
        "adclaw.agents.react_agent.list_available_skills",
        lambda: ["ads"],
    )

    agent = AdClawAgent.__new__(AdClawAgent)
    agent._persona_skill_names = ("seo",)
    toolkit = FakeToolkit()

    agent._register_skills(toolkit)

    assert toolkit.registered == ["seo"]


def test_persona_skill_resolution_rejects_path_traversal(tmp_path):
    resolved = AdClawAgent._resolve_skill_dir(tmp_path, "../../etc")

    assert resolved == tmp_path / "__invalid_skill_name__"


@pytest.mark.asyncio
async def test_mcp_manager_can_return_selected_clients_only():
    manager = MCPClientManager()
    manager._clients = {"citedy": object(), "exa": object()}

    selected = await manager.get_clients(["citedy"])

    assert selected == [manager._clients["citedy"]]


def test_empty_persona_mcp_clients_preserve_all_client_default():
    class Persona:
        mcp_clients = []

    assert runner_module._persona_mcp_client_keys(Persona()) is None


def test_refresh_persisted_envs_for_query_overwrites_managed_guardrail(monkeypatch):
    monkeypatch.setenv("ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS", "10")

    def fake_load_envs_into_environ():
        return {"ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS": "55"}

    monkeypatch.setattr(
        runner_module,
        "load_envs_into_environ",
        fake_load_envs_into_environ,
    )

    runner_module._refresh_persisted_envs_for_query()

    assert runner_module._env_float("ADCLAW_AGENT_QUERY_TIMEOUT_SECONDS", 0.0) == 55


def test_refresh_persisted_envs_for_query_swallows_loader_errors(monkeypatch):
    def fake_load_envs_into_environ():
        raise RuntimeError("env store unavailable")

    monkeypatch.setattr(
        runner_module,
        "load_envs_into_environ",
        fake_load_envs_into_environ,
    )

    runner_module._refresh_persisted_envs_for_query()


@pytest.mark.asyncio
async def test_stream_agent_messages_timeout_interrupts_agent(monkeypatch):
    class FakeAgent:
        interrupted = False

        async def __call__(self, msgs):
            return msgs

        async def interrupt(self):
            self.interrupted = True

    async def hanging_stream(*args, **kwargs):
        coroutine_task = kwargs.get("coroutine_task")
        if coroutine_task is not None:
            coroutine_task.close()
        await asyncio.sleep(10)
        yield None, False

    monkeypatch.setattr(
        runner_module,
        "stream_printing_messages",
        hanging_stream,
    )
    agent = FakeAgent()

    with pytest.raises(runner_module.AgentQueryTimeoutError):
        async for _ in runner_module._stream_agent_messages(
            agent,
            [],
            timeout_seconds=0.01,
        ):
            pass

    assert agent.interrupted is True


@pytest.mark.asyncio
async def test_stream_agent_messages_preserves_inner_timeout(monkeypatch):
    class FakeAgent:
        interrupted = False

        async def __call__(self, msgs):
            return msgs

        async def interrupt(self):
            self.interrupted = True

    async def provider_timeout_stream(*args, **kwargs):
        coroutine_task = kwargs.get("coroutine_task")
        if coroutine_task is not None:
            coroutine_task.close()
        raise TimeoutError("provider read timed out")
        yield None, False

    monkeypatch.setattr(
        runner_module,
        "stream_printing_messages",
        provider_timeout_stream,
    )
    agent = FakeAgent()

    with pytest.raises(TimeoutError, match="provider read timed out"):
        async for _ in runner_module._stream_agent_messages(
            agent,
            [],
            timeout_seconds=10,
        ):
            pass

    assert agent.interrupted is False
