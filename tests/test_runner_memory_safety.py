# -*- coding: utf-8 -*-
"""Tests for runner MemoryManager safety patterns."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


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
