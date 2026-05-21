# -*- coding: utf-8 -*-
# pylint: disable=protected-access,unused-argument
import asyncio
import logging
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from anyio import ClosedResourceError

# BaseExceptionGroup backport for 3.10 (builtin on 3.11+).
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup  # noqa: F401

import adclaw.app.runner.runner as runner_module
from adclaw.agents.react_agent import AdClawAgent
from adclaw.agents import react_agent as react_agent_module
from adclaw.app.mcp import manager as mcp_manager_module
from adclaw.app.mcp.manager import MCPClientManager
from adclaw.app.runner.runner import AgentRunner
from adclaw.config.config import MCPClientConfig


@contextmanager
def _capture_warnings(logger: logging.Logger):
    """Capture WARNING records from adclaw's namespaced logger.

    Adclaw sets ``propagate=False`` on its namespace logger ``adclaw``
    (see src/adclaw/utils/logging.py), so pytest's stock ``caplog`` does
    not receive the records. This helper attaches its own handler
    directly to the target logger and yields the captured messages list.
    """
    captured: list[str] = []

    class _MemHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    handler = _MemHandler(level=logging.WARNING)
    logger.addHandler(handler)
    try:
        yield captured
    finally:
        logger.removeHandler(handler)


class _FakeToolkit:
    def __init__(
        self,
        fail_once_names: set[str] | None = None,
        always_fail_names: set[str] | None = None,
        runtime_fail_names: set[str] | None = None,
        base_exc_group_fail_names: set[str] | None = None,
    ) -> None:
        self.fail_once_names = fail_once_names or set()
        self.always_fail_names = always_fail_names or set()
        self.runtime_fail_names = runtime_fail_names or set()
        self.base_exc_group_fail_names = base_exc_group_fail_names or set()
        self.calls: dict[str, int] = {}
        self.registered: list[str] = []
        self.cancel_once_names: set[str] = set()

    async def register_mcp_client(
        self,
        client,
        namesake_strategy: str = "skip",  # noqa: ARG002
    ) -> None:
        name = client.name
        self.calls[name] = self.calls.get(name, 0) + 1

        if name in self.always_fail_names:
            raise ClosedResourceError()

        if name in self.runtime_fail_names:
            raise RuntimeError("unexpected toolkit failure")

        if name in self.base_exc_group_fail_names:
            raise BaseExceptionGroup(
                "taskgroup teardown",
                [RuntimeError("HTTP 401 Unauthorized")],
            )

        if name in self.cancel_once_names and self.calls[name] == 1:
            raise asyncio.CancelledError()

        if name in self.fail_once_names and self.calls[name] == 1:
            raise ClosedResourceError()

        self.registered.append(name)


class _FakeMCPClient:
    def __init__(self, name: str, connect_ok: bool = True) -> None:
        self.name = name
        self.connect_ok = connect_ok
        self.close_calls = 0
        self.connect_calls = 0

    async def close(self) -> None:
        self.close_calls += 1

    async def connect(self) -> None:
        self.connect_calls += 1
        if not self.connect_ok:
            raise RuntimeError("connect failed")


def test_build_client_attaches_rebuild_info(tmp_path: Path) -> None:
    cfg = MCPClientConfig(
        name="mcp_everything",
        enabled=True,
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-everything"],
        env={"A": "1"},
        cwd=str(tmp_path),
    )

    client = MCPClientManager._build_client(cfg)
    rebuild_info = getattr(client, "_adclaw_rebuild_info", None)

    assert isinstance(rebuild_info, dict)
    assert rebuild_info["transport"] == "stdio"
    assert rebuild_info["command"] == "npx"
    assert rebuild_info["args"] == [
        "-y",
        "@modelcontextprotocol/server-everything",
    ]
    assert rebuild_info["env"] == {"A": "1"}
    assert rebuild_info["cwd"] == str(tmp_path)


@pytest.mark.asyncio
async def test_register_mcp_clients_retries_once_on_closed_resource() -> None:
    toolkit = _FakeToolkit(fail_once_names={"flaky"})
    flaky = _FakeMCPClient(name="flaky", connect_ok=True)
    healthy = _FakeMCPClient(name="healthy", connect_ok=True)

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [flaky, healthy]

    await AdClawAgent.register_mcp_clients(agent)

    assert toolkit.calls["flaky"] == 2
    assert flaky.connect_calls == 1
    assert toolkit.calls["healthy"] == 1
    assert toolkit.registered == ["flaky", "healthy"]


@pytest.mark.asyncio
async def test_register_mcp_clients_skips_unrecoverable_client() -> None:
    toolkit = _FakeToolkit(always_fail_names={"broken"})
    broken = _FakeMCPClient(name="broken", connect_ok=False)
    healthy = _FakeMCPClient(name="healthy", connect_ok=True)

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [broken, healthy]

    await AdClawAgent.register_mcp_clients(agent)

    assert toolkit.calls["broken"] == 1
    assert broken.connect_calls == 1
    assert "broken" not in toolkit.registered
    assert toolkit.registered == ["healthy"]


@pytest.mark.asyncio
async def test_register_mcp_clients_handles_cancelled_error() -> None:
    toolkit = _FakeToolkit()
    toolkit.cancel_once_names = {"flaky"}
    flaky = _FakeMCPClient(name="flaky", connect_ok=True)

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [flaky]

    await AdClawAgent.register_mcp_clients(agent)

    assert toolkit.calls["flaky"] == 2
    assert flaky.connect_calls == 1
    assert toolkit.registered == ["flaky"]


@pytest.mark.asyncio
async def test_register_mcp_clients_skips_unexpected_error() -> None:
    """A broken MCP client must not crash the whole agent: log + skip,
    register the rest. Reproduces the production incident where citedy
    MCP returned 401 and every Telegram query died with RuntimeError."""
    toolkit = _FakeToolkit(runtime_fail_names={"boom"})
    boom = _FakeMCPClient(name="boom", connect_ok=True)
    healthy = _FakeMCPClient(name="healthy", connect_ok=True)

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [boom, healthy]

    with _capture_warnings(react_agent_module.logger) as captured:
        await AdClawAgent.register_mcp_clients(agent)

    assert toolkit.registered == ["healthy"]
    joined = " | ".join(captured)
    assert "boom" in joined and "unavailable" in joined


@pytest.mark.asyncio
async def test_register_mcp_clients_skips_unexpected_error_when_last() -> None:
    """Guards against a regression where `continue` is replaced by `return`/
    `break` — the loop must keep going past a failed *last* client too."""
    toolkit = _FakeToolkit(runtime_fail_names={"boom"})
    healthy_a = _FakeMCPClient(name="healthy_a", connect_ok=True)
    healthy_b = _FakeMCPClient(name="healthy_b", connect_ok=True)
    boom = _FakeMCPClient(name="boom", connect_ok=True)

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [healthy_a, boom, healthy_b]

    with _capture_warnings(react_agent_module.logger):
        await AdClawAgent.register_mcp_clients(agent)

    assert toolkit.registered == ["healthy_a", "healthy_b"]


@pytest.mark.asyncio
async def test_register_mcp_clients_skips_base_exception_group() -> None:
    """anyio TaskGroup teardown raises BaseExceptionGroup (NOT a subclass
    of Exception in Python 3.11+). Without explicit handling it leaks past
    `except Exception` and crashes the agent."""
    toolkit = _FakeToolkit(base_exc_group_fail_names={"taskgroup_broken"})
    broken = _FakeMCPClient(name="taskgroup_broken", connect_ok=True)
    healthy = _FakeMCPClient(name="healthy", connect_ok=True)

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [broken, healthy]

    with _capture_warnings(react_agent_module.logger) as captured:
        await AdClawAgent.register_mcp_clients(agent)

    assert toolkit.registered == ["healthy"]
    joined = " | ".join(captured)
    assert "taskgroup_broken" in joined
    assert "TaskGroup" in joined


@pytest.mark.asyncio
async def test_register_mcp_clients_rebuilds_client_when_reconnect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = _FakeToolkit(always_fail_names={"broken"})
    broken = _FakeMCPClient(name="broken", connect_ok=False)
    rebuilt = _FakeMCPClient(name="rebuilt", connect_ok=True)

    monkeypatch.setattr(
        AdClawAgent,
        "_rebuild_mcp_client",
        staticmethod(lambda client: rebuilt),  # noqa: ARG005
    )

    agent = object.__new__(AdClawAgent)
    agent.toolkit = toolkit
    agent._mcp_clients = [broken]

    await AdClawAgent.register_mcp_clients(agent)

    assert broken.connect_calls == 1
    assert rebuilt.connect_calls == 1
    assert toolkit.registered == ["rebuilt"]
    assert agent._mcp_clients[0] is broken
    assert agent._mcp_clients[0].name == "rebuilt"


@pytest.mark.asyncio
async def test_add_client_closes_partial_client_on_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `connect()` raises, the partially-built client must still be
    `close()`d so that any half-initialised network/process resources
    are released, matching `replace_client`'s behaviour."""
    closed: list[str] = []

    class _ExplodingClient:
        def __init__(self, name: str) -> None:
            self.name = name

        async def connect(self) -> None:
            raise RuntimeError("connect failed")

        async def close(self) -> None:
            closed.append(self.name)

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: _ExplodingClient(cfg.name)),
    )

    manager = MCPClientManager()
    cfg = MCPClientConfig(
        name="leaky_mcp",
        enabled=True,
        transport="streamable_http",
        url="https://example.invalid/mcp",
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        await manager._add_client("leaky", cfg)

    assert closed == ["leaky_mcp"]


@pytest.mark.asyncio
async def test_close_all_swallows_cancelled_error_during_shutdown() -> None:
    class _CancellingClient:
        def __init__(self, name: str) -> None:
            self.name = name
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1
            raise asyncio.CancelledError()

    manager = MCPClientManager()
    client = _CancellingClient("cancelled_mcp")
    manager._clients["cancelled"] = client

    await manager.close_all()

    assert client.close_calls == 1
    assert manager._clients == {}


@pytest.mark.asyncio
async def test_close_all_reraises_external_task_cancellation() -> None:
    close_started = asyncio.Event()
    allow_close_to_finish = asyncio.Event()

    class _BlockingClient:
        async def close(self) -> None:
            close_started.set()
            await allow_close_to_finish.wait()

    manager = MCPClientManager()
    manager._clients["blocked"] = _BlockingClient()

    close_task = asyncio.create_task(manager.close_all())
    await asyncio.wait_for(close_started.wait(), timeout=1)

    close_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await close_task

    allow_close_to_finish.set()


@pytest.mark.asyncio
async def test_close_all_uses_strict_close_when_supported() -> None:
    class _StrictCloseClient:
        def __init__(self) -> None:
            self.ignore_errors_values: list[bool] = []

        async def close(self, ignore_errors: bool = True) -> None:
            self.ignore_errors_values.append(ignore_errors)

    manager = MCPClientManager()
    client = _StrictCloseClient()
    manager._clients["strict"] = client

    await manager.close_all()

    assert client.ignore_errors_values == [False]


@pytest.mark.asyncio
async def test_close_all_downgrades_benign_cancel_scope_noise() -> None:
    class _NoisyClient:
        async def close(self, ignore_errors: bool = True) -> None:
            raise RuntimeError(
                "Attempted to exit a cancel scope that isn't the current "
                "tasks's current cancel scope"
            )

    manager = MCPClientManager()
    manager._clients["agent_browser"] = _NoisyClient()

    with _capture_warnings(mcp_manager_module.logger) as captured:
        await manager.close_all()

    assert captured == []


@pytest.mark.asyncio
async def test_close_all_warns_on_non_benign_base_exception_group() -> None:
    class _GroupedClient:
        async def close(self, ignore_errors: bool = True) -> None:
            raise BaseExceptionGroup(
                "taskgroup teardown",
                [RuntimeError("socket closed unexpectedly")],
            )

    manager = MCPClientManager()
    manager._clients["grouped"] = _GroupedClient()

    with _capture_warnings(mcp_manager_module.logger) as captured:
        await manager.close_all()

    assert captured == [
        "MCP client 'grouped' close raised BaseExceptionGroup during "
        "manager shutdown: taskgroup teardown (1 sub-exception)"
    ]


@pytest.mark.asyncio
async def test_close_all_downgrades_grouped_cancelled_error() -> None:
    class _GroupedClient:
        async def close(self, ignore_errors: bool = True) -> None:
            raise BaseExceptionGroup(
                "taskgroup teardown",
                [asyncio.CancelledError()],
            )

    manager = MCPClientManager()
    manager._clients["grouped"] = _GroupedClient()

    with _capture_warnings(mcp_manager_module.logger) as captured:
        await manager.close_all()

    assert captured == []


@pytest.mark.asyncio
async def test_replace_client_releases_lock_before_old_close_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_started = asyncio.Event()
    allow_close_to_finish = asyncio.Event()

    class _OldClient:
        async def close(self) -> None:
            close_started.set()
            await allow_close_to_finish.wait()

    class _NewClient:
        async def connect(self) -> None:
            return

        async def close(self) -> None:
            return

    manager = MCPClientManager()
    manager._clients["demo"] = _OldClient()
    new_client = _NewClient()

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: new_client),
    )

    replace_task = asyncio.create_task(
        manager.replace_client(
            "demo",
            MCPClientConfig(
                name="demo",
                enabled=True,
                transport="streamable_http",
                url="https://example.invalid/mcp",
            ),
        )
    )

    await asyncio.wait_for(close_started.wait(), timeout=1)

    clients = await asyncio.wait_for(manager.get_clients(), timeout=0.1)
    assert clients == [new_client]

    allow_close_to_finish.set()
    await replace_task


@pytest.mark.asyncio
async def test_init_from_config_handles_base_exception_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_from_config must not let BaseExceptionGroup (raised by anyio
    TaskGroup teardown when MCP HTTP returns 401) propagate to FastAPI
    lifespan — that crashes the whole app with 'startup failed'."""
    from adclaw.config.config import MCPConfig

    class _ExplodingClient:
        def __init__(self, name: str) -> None:
            self.name = name

        async def connect(self) -> None:
            raise BaseExceptionGroup(
                "taskgroup teardown",
                [RuntimeError("HTTP 401 Unauthorized")],
            )

        async def close(self) -> None:
            return

    class _OkClient:
        def __init__(self, name: str) -> None:
            self.name = name

        async def connect(self) -> None:
            return

        async def close(self) -> None:
            return

    def fake_build(cfg: MCPClientConfig) -> object:
        if cfg.name == "broken_mcp":
            return _ExplodingClient(cfg.name)
        return _OkClient(cfg.name)

    monkeypatch.setattr(
        MCPClientManager, "_build_client", staticmethod(fake_build)
    )

    config = MCPConfig(
        clients={
            "broken": MCPClientConfig(
                name="broken_mcp",
                enabled=True,
                transport="streamable_http",
                url="https://example.invalid/mcp",
            ),
            "healthy": MCPClientConfig(
                name="healthy_mcp",
                enabled=True,
                transport="streamable_http",
                url="https://example.invalid/mcp2",
            ),
        }
    )

    manager = MCPClientManager()

    with _capture_warnings(mcp_manager_module.logger) as captured:
        await manager.init_from_config(config)

    clients = await manager.get_clients()
    names = [c.name for c in clients]
    assert names == ["healthy_mcp"]
    joined = " | ".join(captured)
    assert "broken" in joined
    assert "Failed to initialize" in joined


@pytest.mark.asyncio
async def test_app_schedules_initial_mcp_connect_without_blocking_startup() -> None:
    """Hosted startup must not wait for slow external MCP transports."""
    from adclaw.app._app import _schedule_mcp_initialization

    class _SlowManager:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def init_from_config(self, config) -> None:  # noqa: ANN001
            self.started.set()
            await self.release.wait()

    manager = _SlowManager()
    task = _schedule_mcp_initialization(manager, SimpleNamespace(clients={}))

    await asyncio.wait_for(manager.started.wait(), timeout=1)
    assert not task.done()

    manager.release.set()
    await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_initial_mcp_add_does_not_replace_newer_hot_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow startup connect must not overwrite a newer hot-reload client."""
    startup_started = asyncio.Event()
    startup_release = asyncio.Event()
    closed_clients: list[str] = []

    class _GateClient:
        def __init__(self, name: str) -> None:
            self.name = name

        async def connect(self) -> None:
            if self.name == "startup":
                startup_started.set()
                await startup_release.wait()

        async def close(self) -> None:
            closed_clients.append(self.name)

    def fake_build(client_config: MCPClientConfig) -> _GateClient:
        return _GateClient(client_config.name)

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(fake_build),
    )

    manager = MCPClientManager()
    startup_cfg = MCPClientConfig(
        name="startup",
        enabled=True,
        transport="streamable_http",
        url="https://example.invalid/startup",
    )
    reload_cfg = MCPClientConfig(
        name="reload",
        enabled=True,
        transport="streamable_http",
        url="https://example.invalid/reload",
    )

    startup_task = asyncio.create_task(
        manager._add_client("citedy", startup_cfg),
    )
    await asyncio.wait_for(startup_started.wait(), timeout=1)

    await manager.replace_client("citedy", reload_cfg)
    startup_release.set()
    await asyncio.wait_for(startup_task, timeout=1)

    clients = await manager.get_clients()
    assert [client.name for client in clients] == ["reload"]
    assert closed_clients == ["startup"]


@pytest.mark.asyncio
async def test_reconnect_mcp_client_respects_timeout() -> None:
    class _SlowClient:
        async def close(self) -> None:
            return

        async def connect(self) -> None:
            await asyncio.sleep(0.1)

    ok = await AdClawAgent._reconnect_mcp_client(
        _SlowClient(),
        timeout=0.01,
    )
    assert ok is False


@pytest.mark.asyncio
async def test_query_handler_skips_session_save_when_load_not_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeAgent:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ARG002
            pass

        async def register_mcp_clients(self) -> None:
            raise ClosedResourceError()

        def set_console_output_enabled(
            self,
            enabled: bool,
        ) -> None:  # noqa: ARG002
            return

    class _FakeSession:
        def __init__(self) -> None:
            self.load_calls = 0
            self.save_calls = 0

        async def load_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.load_calls += 1

        async def save_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.save_calls += 1

    class _DummyInputMsg:
        def get_text_content(self) -> str:
            return "你好"

    cfg = SimpleNamespace(
        agents=SimpleNamespace(
            running=SimpleNamespace(max_iters=1, max_input_length=2048),
        ),
    )

    monkeypatch.setattr(runner_module, "AdClawAgent", _FakeAgent)
    monkeypatch.setattr(runner_module, "load_config", lambda: cfg)
    monkeypatch.setattr(
        runner_module,
        "build_env_context",
        lambda **kwargs: "env",
    )
    monkeypatch.setattr(
        runner_module,
        "write_query_error_dump",
        lambda **kwargs: None,
    )

    runner = AgentRunner()
    fake_session = _FakeSession()
    runner.session = fake_session

    request = SimpleNamespace(
        session_id="s1",
        user_id="u1",
        channel="console",
    )

    with pytest.raises(ClosedResourceError):
        async for _ in runner.query_handler(
            [_DummyInputMsg()],
            request=request,
        ):
            pass

    assert fake_session.load_calls == 0
    assert fake_session.save_calls == 0


async def test_query_handler_uses_model_factory_for_provider_fallback(monkeypatch):
    """A primary provider timeout should use the fallback model factory."""
    import httpx
    from agentscope.message import Msg
    from openai import APITimeoutError

    from adclaw.providers import store as provider_store

    class _FakeAgent:
        def __init__(self, **kwargs) -> None:
            self.model = kwargs.get(
                "model",
                SimpleNamespace(model_name="primary-model"),
            )
            self._env_context = kwargs.get("env_context")
            self._mcp_clients = kwargs.get("mcp_clients", [])
            self._namesake_strategy = "skip"
            self._persona = kwargs.get("persona")
            self._team_summary = kwargs.get("team_summary", "")

        async def register_mcp_clients(self) -> None:
            return

        def set_console_output_enabled(self, enabled: bool) -> None:  # noqa: ARG002
            return

        def rebuild_sys_prompt(self) -> None:
            return

        def __call__(self, msgs):  # noqa: ANN001
            return self

    class _FakeSession:
        def __init__(self) -> None:
            self.load_calls = 0
            self.save_calls = 0

        async def load_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.load_calls += 1

        async def save_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.save_calls += 1

    class _FakePersonaManager:
        all_personas = ()

        def __init__(self, **kwargs) -> None:  # noqa: ARG002
            return

        def ensure_dirs(self) -> None:
            return

        def resolve_tag(self, msg_text: str):  # noqa: ANN201, ARG002
            return None

        def get_coordinator(self):  # noqa: ANN201
            return None

        def get_team_summary(self) -> str:
            return ""

    class _DummyInputMsg:
        content = "hello"

        def get_text_content(self) -> str:
            return "hello"

    cfg = SimpleNamespace(
        agents=SimpleNamespace(
            running=SimpleNamespace(max_iters=1, max_input_length=2048),
            personas=[],
        ),
    )
    fallback_cfg = SimpleNamespace(enabled=True, timeout_seconds=1)
    resolved_fallback = SimpleNamespace(
        provider_id="fallback-provider",
        model="fallback-model",
    )
    factory_calls = []
    stream_calls = 0

    def _fake_create_model_and_formatter(model_cfg, timeout_seconds=None):
        factory_calls.append((model_cfg, timeout_seconds))
        return SimpleNamespace(model_name=model_cfg.model), object()

    async def _fake_stream_printing_messages(*, agents, coroutine_task):  # noqa: ARG001
        nonlocal stream_calls
        stream_calls += 1
        if stream_calls == 1:
            raise APITimeoutError(
                request=httpx.Request("POST", "https://llm.example.test"),
            )
        yield Msg(name="assistant", role="assistant", content="fallback reply"), True

    async def _empty_context(**kwargs) -> str:  # noqa: ARG001
        return ""

    async def _noop_capture(**kwargs) -> None:  # noqa: ARG001
        return

    monkeypatch.setattr(runner_module, "AdClawAgent", _FakeAgent)
    monkeypatch.setattr(runner_module, "PersonaManager", _FakePersonaManager)
    monkeypatch.setattr(runner_module, "load_config", lambda: cfg)
    monkeypatch.setattr(
        runner_module,
        "build_env_context",
        lambda **kwargs: "env",
    )
    monkeypatch.setattr(
        runner_module,
        "stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        provider_store,
        "get_fallback_config",
        lambda: fallback_cfg,
    )
    monkeypatch.setattr(
        provider_store,
        "get_active_llm_config",
        lambda: SimpleNamespace(
            provider_id="primary-provider",
            model="primary-model",
        ),
    )
    monkeypatch.setattr(
        provider_store,
        "resolve_fallback_chain",
        lambda: [resolved_fallback],
    )
    monkeypatch.setattr(
        runner_module,
        "create_model_and_formatter",
        _fake_create_model_and_formatter,
    )

    runner = AgentRunner()
    runner.session = _FakeSession()
    runner._build_shared_persona_memory_context = _empty_context
    runner._capture_chat_memory = _noop_capture

    request = SimpleNamespace(
        session_id="s1",
        user_id="u1",
        channel="telegram",
    )

    events = []
    async for msg, last in runner.query_handler(
        [_DummyInputMsg()],
        request=request,
    ):
        events.append((getattr(msg, "content", ""), last))

    assert stream_calls == 2
    assert factory_calls == [(resolved_fallback, 1)]
    assert any("Switching to fallback-model" in str(content) for content, _ in events)
    assert ("fallback reply", True) in events
    assert runner.session.load_calls == 1
    assert runner.session.save_calls == 1


async def test_query_handler_skips_duplicate_active_fallback(monkeypatch):
    """Fallback chain should not retry the active provider/model slot."""
    import httpx
    from agentscope.message import Msg
    from openai import APITimeoutError

    from adclaw.providers import store as provider_store

    class _FakeAgent:
        def __init__(self, **kwargs) -> None:
            self.model = kwargs.get(
                "model",
                SimpleNamespace(model_name="primary-model"),
            )
            self._env_context = kwargs.get("env_context")
            self._mcp_clients = kwargs.get("mcp_clients", [])
            self._namesake_strategy = "skip"
            self._persona = kwargs.get("persona")
            self._team_summary = kwargs.get("team_summary", "")

        async def register_mcp_clients(self) -> None:
            return

        def set_console_output_enabled(self, enabled: bool) -> None:  # noqa: ARG002
            return

        def rebuild_sys_prompt(self) -> None:
            return

        def __call__(self, msgs):  # noqa: ANN001
            return self

    class _FakeSession:
        def __init__(self) -> None:
            self.load_calls = 0
            self.save_calls = 0

        async def load_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.load_calls += 1

        async def save_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.save_calls += 1

    class _FakePersonaManager:
        all_personas = []

        def __init__(self, **kwargs) -> None:  # noqa: ARG002
            return

        def ensure_dirs(self) -> None:
            return

        def resolve_tag(self, msg_text: str):  # noqa: ANN201, ARG002
            return None

        def get_coordinator(self):  # noqa: ANN201
            return None

        def get_team_summary(self) -> str:
            return ""

    class _DummyInputMsg:
        content = "hello"

        def get_text_content(self) -> str:
            return "hello"

    cfg = SimpleNamespace(
        agents=SimpleNamespace(
            running=SimpleNamespace(max_iters=1, max_input_length=2048),
            personas=[],
        ),
    )
    fallback_cfg = SimpleNamespace(enabled=True, timeout_seconds=1)
    duplicate = SimpleNamespace(
        provider_id="adclaw-host-ai",
        model="@cf/google/gemma-4-26b-a4b-it",
    )
    fallback = SimpleNamespace(
        provider_id="customer-openai",
        model="gpt-4.1-mini",
    )
    factory_calls = []
    stream_calls = 0

    def _fake_create_model_and_formatter(model_cfg, timeout_seconds=None):
        factory_calls.append((model_cfg, timeout_seconds))
        return SimpleNamespace(model_name=model_cfg.model), object()

    async def _fake_stream_printing_messages(*, agents, coroutine_task):  # noqa: ARG001
        nonlocal stream_calls
        stream_calls += 1
        if stream_calls == 1:
            raise APITimeoutError(
                request=httpx.Request("POST", "https://llm.example.test"),
            )
        yield Msg(name="assistant", role="assistant", content="fallback reply"), True

    async def _empty_context(**kwargs) -> str:  # noqa: ARG001
        return ""

    async def _noop_capture(**kwargs) -> None:  # noqa: ARG001
        return

    monkeypatch.setattr(runner_module, "AdClawAgent", _FakeAgent)
    monkeypatch.setattr(runner_module, "PersonaManager", _FakePersonaManager)
    monkeypatch.setattr(runner_module, "load_config", lambda: cfg)
    monkeypatch.setattr(
        runner_module,
        "build_env_context",
        lambda **kwargs: "env",
    )
    monkeypatch.setattr(
        runner_module,
        "stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        provider_store,
        "get_fallback_config",
        lambda: fallback_cfg,
    )
    monkeypatch.setattr(
        provider_store,
        "get_active_llm_config",
        lambda: duplicate,
    )
    monkeypatch.setattr(
        provider_store,
        "resolve_fallback_chain",
        lambda: [duplicate, fallback],
    )
    monkeypatch.setattr(
        runner_module,
        "create_model_and_formatter",
        _fake_create_model_and_formatter,
    )

    runner = AgentRunner()
    runner.session = _FakeSession()
    runner._build_shared_persona_memory_context = _empty_context
    runner._capture_chat_memory = _noop_capture

    request = SimpleNamespace(
        session_id="s1",
        user_id="u1",
        channel="telegram",
    )

    events = []
    async for msg, last in runner.query_handler(
        [_DummyInputMsg()],
        request=request,
    ):
        events.append((getattr(msg, "content", ""), last))

    assert factory_calls == [(fallback, 1)]
    assert any("Switching to gpt-4.1-mini" in str(content) for content, _ in events)
    assert ("fallback reply", True) in events


async def test_query_handler_renders_host_ai_limit_without_generic_error(monkeypatch):
    """Host AI quota 429 should produce a stable limit message."""
    import httpx
    from openai import RateLimitError

    from adclaw.providers import store as provider_store

    class _FakeAgent:
        def __init__(self, **kwargs) -> None:
            self.model = SimpleNamespace(
                model_name="@cf/google/gemma-4-26b-a4b-it",
            )
            self._env_context = kwargs.get("env_context")
            self._mcp_clients = kwargs.get("mcp_clients", [])
            self._namesake_strategy = "skip"
            self._persona = kwargs.get("persona")
            self._team_summary = kwargs.get("team_summary", "")

        async def register_mcp_clients(self) -> None:
            return

        def set_console_output_enabled(self, enabled: bool) -> None:  # noqa: ARG002
            return

        def rebuild_sys_prompt(self) -> None:
            return

        def __call__(self, msgs):  # noqa: ANN001
            return self

    class _FakeSession:
        def __init__(self) -> None:
            self.load_calls = 0
            self.save_calls = 0

        async def load_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.load_calls += 1

        async def save_session_state(self, **kwargs) -> None:  # noqa: ARG002
            self.save_calls += 1

    class _FakePersonaManager:
        all_personas = []

        def __init__(self, **kwargs) -> None:  # noqa: ARG002
            return

        def ensure_dirs(self) -> None:
            return

        def resolve_tag(self, msg_text: str):  # noqa: ANN201, ARG002
            return None

        def get_coordinator(self):  # noqa: ANN201
            return None

        def get_team_summary(self) -> str:
            return ""

    class _DummyInputMsg:
        content = "hello"

        def get_text_content(self) -> str:
            return "hello"

    cfg = SimpleNamespace(
        agents=SimpleNamespace(
            running=SimpleNamespace(max_iters=1, max_input_length=2048),
            personas=[],
        ),
    )
    response = httpx.Response(
        429,
        request=httpx.Request(
            "POST",
            "https://real.adclaw.app/api/host-ai/v1/chat/completions",
        ),
    )
    quota_error = RateLimitError(
        "adclaw_host_ai_limit_reached",
        response=response,
        body={"error": {"code": "adclaw_host_ai_limit_reached"}},
    )

    async def _fake_stream_printing_messages(*, agents, coroutine_task):  # noqa: ARG001
        if False:
            yield None
        raise quota_error

    async def _empty_context(**kwargs) -> str:  # noqa: ARG001
        return ""

    async def _noop_capture(**kwargs) -> None:  # noqa: ARG001
        return

    monkeypatch.setattr(runner_module, "AdClawAgent", _FakeAgent)
    monkeypatch.setattr(runner_module, "PersonaManager", _FakePersonaManager)
    monkeypatch.setattr(runner_module, "load_config", lambda: cfg)
    monkeypatch.setattr(
        runner_module,
        "build_env_context",
        lambda **kwargs: "env",
    )
    monkeypatch.setattr(
        runner_module,
        "stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        provider_store,
        "get_fallback_config",
        lambda: SimpleNamespace(enabled=False, timeout_seconds=1),
    )

    runner = AgentRunner()
    runner.session = _FakeSession()
    runner._build_shared_persona_memory_context = _empty_context
    runner._capture_chat_memory = _noop_capture

    request = SimpleNamespace(
        session_id="s1",
        user_id="u1",
        channel="telegram",
    )

    events = []
    async for msg, last in runner.query_handler(
        [_DummyInputMsg()],
        request=request,
    ):
        events.append((getattr(msg, "content", ""), last))

    assert len(events) == 1
    assert events[0][1] is True
    assert "Included AdClaw Host AI messages" in str(events[0][0])
    assert "fallback model" not in str(events[0][0]).lower()
    assert runner.session.load_calls == 1
    assert runner.session.save_calls == 1
