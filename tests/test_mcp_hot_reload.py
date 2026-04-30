# -*- coding: utf-8 -*-
"""Tests for MCP API hot-reload: create/update/delete/toggle trigger manager."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# BaseExceptionGroup backport for 3.10 (builtin on 3.11+).
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup  # noqa: F401

from adclaw.app.routers.mcp import (
    _hot_reload_client,
    _hot_remove_client,
    _get_mcp_manager,
)
from adclaw.config.config import MCPClientConfig


def _make_request(manager=None):
    """Create a fake Request with app.state.mcp_manager."""
    request = MagicMock()
    request.app.state.mcp_manager = manager
    return request


def _make_client_config(enabled=True):
    return MCPClientConfig(
        name="test_mcp",
        enabled=enabled,
        command="echo",
        args=["hello"],
    )


# --- _hot_reload_client ---


@pytest.mark.asyncio
async def test_hot_reload_calls_replace_client():
    """Creating/updating enabled client calls manager.replace_client."""
    manager = MagicMock()
    manager.replace_client = AsyncMock()
    request = _make_request(manager)
    cfg = _make_client_config(enabled=True)

    result = await _hot_reload_client(request, "test_key", cfg)

    manager.replace_client.assert_called_once_with("test_key", cfg)
    assert result is None  # success → no warning


@pytest.mark.asyncio
async def test_hot_reload_skips_disabled_client():
    """Disabled client should not be connected."""
    manager = MagicMock()
    manager.replace_client = AsyncMock()
    request = _make_request(manager)
    cfg = _make_client_config(enabled=False)

    result = await _hot_reload_client(request, "test_key", cfg)

    manager.replace_client.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_hot_reload_returns_warning_on_error():
    """If manager.replace_client raises, return warning string."""
    manager = MagicMock()
    manager.replace_client = AsyncMock(side_effect=Exception("conn failed"))
    request = _make_request(manager)
    cfg = _make_client_config(enabled=True)

    result = await _hot_reload_client(request, "test_key", cfg)

    manager.replace_client.assert_called_once()
    assert result is not None
    assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_hot_reload_returns_warning_on_base_exception_group():
    """anyio TaskGroup teardown raises BaseExceptionGroup (NOT subclass of
    Exception in 3.11+). Must be caught here, otherwise the FastAPI worker
    crashes on a single bad client config during a hot-reload API call."""
    manager = MagicMock()
    manager.replace_client = AsyncMock(
        side_effect=BaseExceptionGroup(
            "taskgroup teardown",
            [RuntimeError("HTTP 401 Unauthorized")],
        )
    )
    request = _make_request(manager)
    cfg = _make_client_config(enabled=True)

    result = await _hot_reload_client(request, "test_key", cfg)

    manager.replace_client.assert_called_once()
    assert result is not None
    assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_hot_reload_no_manager():
    """If manager is None (not initialized), should silently skip."""
    request = _make_request(manager=None)
    cfg = _make_client_config(enabled=True)

    result = await _hot_reload_client(request, "test_key", cfg)
    assert result is None


# --- _hot_remove_client ---


@pytest.mark.asyncio
async def test_hot_remove_calls_remove_client():
    """Deleting/disabling client calls manager.remove_client."""
    manager = MagicMock()
    manager.remove_client = AsyncMock()
    request = _make_request(manager)

    result = await _hot_remove_client(request, "test_key")

    manager.remove_client.assert_called_once_with("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_hot_remove_returns_warning_on_error():
    """If manager.remove_client raises, return warning string."""
    manager = MagicMock()
    manager.remove_client = AsyncMock(side_effect=Exception("not found"))
    request = _make_request(manager)

    result = await _hot_remove_client(request, "test_key")

    manager.remove_client.assert_called_once()
    assert result is not None
    assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_hot_remove_no_manager():
    """If manager is None, remove should silently skip."""
    request = _make_request(manager=None)

    result = await _hot_remove_client(request, "test_key")
    assert result is None


# --- _get_mcp_manager ---


def test_get_mcp_manager_returns_manager():
    """_get_mcp_manager extracts from app.state."""
    manager = MagicMock()
    request = _make_request(manager)
    assert _get_mcp_manager(request) is manager


def test_get_mcp_manager_returns_none_if_missing():
    """_get_mcp_manager returns None if state has no manager."""
    request = MagicMock(spec=[])
    request.app = MagicMock(spec=[])
    request.app.state = MagicMock(spec=[])
    assert _get_mcp_manager(request) is None
