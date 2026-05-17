# -*- coding: utf-8 -*-
"""Tests for runner MemoryManager safety patterns."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_react_agent_import_does_not_eagerly_import_reme():
    """Importing the agent module must not pull in ReMe until enabled."""
    import importlib
    import sys

    sys.modules.pop("reme", None)
    sys.modules.pop("reme.reme_copaw", None)
    sys.modules.pop("adclaw.agents.memory.memory_manager", None)

    importlib.import_module("adclaw.agents.react_agent")

    assert "reme" not in sys.modules
    assert "reme.reme_copaw" not in sys.modules
    assert "adclaw.agents.memory.memory_manager" not in sys.modules


def test_memory_manager_safe_defaults_use_sqlite_fts_without_embeddings(
    monkeypatch,
):
    """ReMe should default to the cheap sqlite/FTS path without vector envs."""
    from adclaw.app.runner.runner import AgentRunner

    for key in (
        "MEMORY_STORE_BACKEND",
        "FTS_ENABLED",
        "EMBEDDING_API_KEY",
        "EMBEDDING_MODEL_NAME",
    ):
        monkeypatch.delenv(key, raising=False)

    runner = AgentRunner()
    runner._apply_memory_manager_safe_defaults()

    assert os.environ["MEMORY_STORE_BACKEND"] == "sqlite"
    assert os.environ["FTS_ENABLED"] == "true"
    assert os.environ["EMBEDDING_API_KEY"] == ""
    assert os.environ["EMBEDDING_MODEL_NAME"] == ""


@pytest.mark.asyncio
async def test_approx_token_counter_is_lightweight():
    """Approx counter avoids HuggingFace tokenizer startup in ReMe safe mode."""
    from adclaw.app.runner.runner import _ApproxTokenCounter

    count = await _ApproxTokenCounter().count(
        [{"role": "user", "content": "hello world"}],
    )

    assert count >= 1


def test_memory_manager_load_guard_skips_high_load(monkeypatch):
    """High load should skip background ReMe startup before heavy imports."""
    from adclaw.app.runner import runner as runner_module
    from adclaw.app.runner.runner import AgentRunner

    monkeypatch.setenv("ADCLAW_MEMORY_MANAGER_MAX_LOADAVG", "2.0")
    monkeypatch.setattr(runner_module.os, "getloadavg", lambda: (2.5, 2.0, 1.0))

    assert AgentRunner()._memory_manager_load_too_high() is True


def test_memory_manager_load_guard_records_status(monkeypatch):
    """The runner should expose ReMe skip state for diagnostics."""
    from adclaw.app.runner import runner as runner_module
    from adclaw.app.runner.runner import AgentRunner

    monkeypatch.setenv("ADCLAW_MEMORY_MANAGER_MAX_LOADAVG", "2.0")
    monkeypatch.setattr(runner_module.os, "getloadavg", lambda: (2.5, 2.0, 1.0))

    runner = AgentRunner()

    assert runner._memory_manager_load_too_high() is True
    assert runner.memory_manager_status == "skipped"
    assert "loadavg 2.50 exceeds 2.00" == runner.memory_manager_status_detail


@pytest.mark.asyncio
async def test_diagnostics_health_reports_reme_state():
    """Health output should tell clients whether ReMe is active or pending."""
    from adclaw.app.routers.diagnostics import health

    runner = MagicMock()
    runner.memory_manager_status = "scheduled"
    runner.memory_manager_status_detail = "background"
    runner.memory_manager = None
    runner._memory_manager_start_task = object()

    request = MagicMock()
    request.app.state.runner = runner
    request.app.state.channel_manager.channels = []
    request.app.state.mcp_manager._clients = {}
    request.app.state.cron_manager._scheduler.get_jobs.return_value = []
    request.app.state.aom_manager = None
    request.app.state.watchdog = None

    result = await health(request)

    reme = result.subsystems["reme"]
    assert reme.status == "ok"
    assert reme.detail["state"] == "scheduled"
    assert reme.detail["enabled"] is False
    assert reme.detail["pending"] is True


@pytest.mark.asyncio
async def test_memory_manager_requires_explicit_reme_enable(monkeypatch):
    """Runner startup should not import/build ReMe unless explicitly enabled."""
    from adclaw.app.runner.runner import AgentRunner

    monkeypatch.setenv("ADCLAW_ENABLE_REME", "0")
    monkeypatch.delenv("ADCLAW_DISABLE_MEMORY_MANAGER", raising=False)

    runner = AgentRunner()
    await runner.init_handler()

    assert runner.memory_manager is None
    assert runner._memory_manager_start_task is None
    assert runner.memory_manager_status == "disabled"
    assert runner.memory_manager_status_detail == "ADCLAW_ENABLE_REME not set"


def test_memory_manager_null_on_failure_pattern():
    """After start() failure, memory_manager should be set to None.

    Tests the pattern used in Runner.init_handler: if start() raises,
    set memory_manager = None so downstream code knows it's unavailable.
    """
    mm = MagicMock()
    mm.start = AsyncMock(side_effect=RuntimeError("db locked"))

    # Simulate the init_handler pattern
    memory_manager = mm
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(memory_manager.start())
    except RuntimeError:
        memory_manager = None

    assert memory_manager is None


def test_memory_manager_none_is_safe_for_agent():
    """AdClawAgent handles memory_manager=None gracefully."""
    from adclaw.agents.react_agent import AdClawAgent
    import inspect

    sig = inspect.signature(AdClawAgent.__init__)
    param = sig.parameters.get("memory_manager")
    assert param is not None, "AdClawAgent must accept memory_manager"
    assert param.default is None, "memory_manager must default to None"


@pytest.mark.asyncio
async def test_hot_reload_returns_warning_string():
    """_hot_reload_client returns warning string on failure (Finding #5)."""
    from adclaw.app.routers.mcp import _hot_reload_client
    from adclaw.config.config import MCPClientConfig

    manager = MagicMock()
    manager.replace_client = AsyncMock(side_effect=Exception("timeout"))
    request = MagicMock()
    request.app.state.mcp_manager = manager
    cfg = MCPClientConfig(name="test", enabled=True, command="echo", args=[])

    result = await _hot_reload_client(request, "k", cfg)

    assert result is not None
    assert isinstance(result, str)
    assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_hot_reload_returns_none_on_success():
    """_hot_reload_client returns None on success."""
    from adclaw.app.routers.mcp import _hot_reload_client
    from adclaw.config.config import MCPClientConfig

    manager = MagicMock()
    manager.replace_client = AsyncMock()
    request = MagicMock()
    request.app.state.mcp_manager = manager
    cfg = MCPClientConfig(name="test", enabled=True, command="echo", args=[])

    result = await _hot_reload_client(request, "k", cfg)
    assert result is None


@pytest.mark.asyncio
async def test_hot_remove_returns_warning_string():
    """_hot_remove_client returns warning string on failure."""
    from adclaw.app.routers.mcp import _hot_remove_client

    manager = MagicMock()
    manager.remove_client = AsyncMock(side_effect=Exception("err"))
    request = MagicMock()
    request.app.state.mcp_manager = manager

    result = await _hot_remove_client(request, "k")

    assert result is not None
    assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_hot_remove_returns_none_on_success():
    """_hot_remove_client returns None on success."""
    from adclaw.app.routers.mcp import _hot_remove_client

    manager = MagicMock()
    manager.remove_client = AsyncMock()
    request = MagicMock()
    request.app.state.mcp_manager = manager

    result = await _hot_remove_client(request, "k")
    assert result is None
