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
