# -*- coding: utf-8 -*-
"""API routes for MCP (Model Context Protocol) clients management."""

from __future__ import annotations

import asyncio
import sys
from typing import Dict, List, Optional, Literal

import logging

# BaseExceptionGroup is a builtin in 3.11+; on 3.10 we use the
# `exceptiongroup` backport (declared in pyproject.toml only for 3.10).
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup  # noqa: F401

# Hot-reload timeout: cap connect attempts so API doesn't hang
_HOT_RELOAD_TIMEOUT = 10.0  # seconds

from fastapi import APIRouter, Body, HTTPException, Path, Request
from pydantic import BaseModel, Field

from ...config import load_config, save_config
from ...config.config import MCPClientConfig

router = APIRouter(prefix="/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)


def _get_mcp_manager(request: Request):
    """Get MCPClientManager from app state (may be None)."""
    return getattr(request.app.state, "mcp_manager", None)


class MCPClientInfo(BaseModel):
    """MCP client information for API responses."""

    key: str = Field(..., description="Unique client key identifier")
    name: str = Field(..., description="Client display name")
    description: str = Field(default="", description="Client description")
    enabled: bool = Field(..., description="Whether the client is enabled")
    connection_warning: Optional[str] = Field(
        default=None,
        description="Warning if hot-reload/disconnect failed",
    )
    transport: Literal["stdio", "streamable_http", "sse"] = Field(
        ...,
        description="MCP transport type",
    )
    url: str = Field(
        default="",
        description="Remote MCP endpoint URL (for HTTP/SSE transports)",
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers for remote transport",
    )
    command: str = Field(
        default="",
        description="Command to launch the MCP server",
    )
    args: List[str] = Field(
        default_factory=list,
        description="Command-line arguments",
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )
    cwd: str = Field(
        default="",
        description="Working directory for stdio MCP command",
    )


class MCPClientCreateRequest(BaseModel):
    """Request body for creating/updating an MCP client."""

    name: str = Field(..., description="Client display name")
    description: str = Field(default="", description="Client description")
    enabled: bool = Field(
        default=True,
        description="Whether to enable the client",
    )
    transport: Literal["stdio", "streamable_http", "sse"] = Field(
        default="stdio",
        description="MCP transport type",
    )
    url: str = Field(
        default="",
        description="Remote MCP endpoint URL (for HTTP/SSE transports)",
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers for remote transport",
    )
    command: str = Field(
        default="",
        description="Command to launch the MCP server",
    )
    args: List[str] = Field(
        default_factory=list,
        description="Command-line arguments",
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )
    cwd: str = Field(
        default="",
        description="Working directory for stdio MCP command",
    )


class MCPClientUpdateRequest(BaseModel):
    """Request body for updating an MCP client (all fields optional)."""

    name: Optional[str] = Field(None, description="Client display name")
    description: Optional[str] = Field(None, description="Client description")
    enabled: Optional[bool] = Field(
        None,
        description="Whether to enable the client",
    )
    transport: Optional[Literal["stdio", "streamable_http", "sse"]] = Field(
        None,
        description="MCP transport type",
    )
    url: Optional[str] = Field(
        None,
        description="Remote MCP endpoint URL (for HTTP/SSE transports)",
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="HTTP headers for remote transport",
    )
    command: Optional[str] = Field(
        None,
        description="Command to launch the MCP server",
    )
    args: Optional[List[str]] = Field(
        None,
        description="Command-line arguments",
    )
    env: Optional[Dict[str, str]] = Field(
        None,
        description="Environment variables",
    )
    cwd: Optional[str] = Field(
        None,
        description="Working directory for stdio MCP command",
    )


def _mask_env_value(value: str) -> str:
    """
    Mask environment variable value showing first 2-3 chars and last 4 chars.

    Examples:
        sk-proj-1234567890abcdefghij1234 -> sk-****************************1234
        abc123456789xyz -> ab***********xyz (if no dash)
        my-api-key-value -> my-************lue
        short123 -> ******** (8 chars or less, fully masked)
    """
    if not value:
        return value

    length = len(value)
    if length <= 8:
        # For short values, just mask everything
        return "*" * length

    # Show first 2-3 characters (3 if there's a dash at position 2)
    prefix_len = 3 if length > 2 and value[2] == "-" else 2
    prefix = value[:prefix_len]

    # Show last 4 characters
    suffix = value[-4:]

    # Calculate masked section length (at least 4 asterisks)
    masked_len = max(length - prefix_len - 4, 4)

    return f"{prefix}{'*' * masked_len}{suffix}"


def _build_client_info(key: str, client: MCPClientConfig) -> MCPClientInfo:
    """Build MCPClientInfo from config with masked env values."""
    # Mask environment variable values for security
    masked_env = (
        {k: _mask_env_value(v) for k, v in client.env.items()}
        if client.env
        else {}
    )
    masked_headers = (
        {k: _mask_env_value(v) for k, v in client.headers.items()}
        if client.headers
        else {}
    )

    return MCPClientInfo(
        key=key,
        name=client.name,
        description=client.description,
        enabled=client.enabled,
        transport=client.transport,
        url=client.url,
        headers=masked_headers,
        command=client.command,
        args=client.args,
        env=masked_env,
        cwd=client.cwd,
    )


async def _hot_reload_client(
    request: Request,
    client_key: str,
    client_config: MCPClientConfig,
) -> Optional[str]:
    """Connect or reconnect an MCP client immediately after config change.

    Returns None on success, warning string on failure.
    """
    if not client_config.enabled:
        return None
    manager = _get_mcp_manager(request)
    if manager is None:
        return None
    try:
        await asyncio.wait_for(
            manager.replace_client(client_key, client_config),
            timeout=_HOT_RELOAD_TIMEOUT,
        )
        logger.info("MCP client '%s' hot-reloaded successfully", client_key)
        return None
    except asyncio.TimeoutError:
        logger.warning(
            "MCP client '%s' hot-reload timed out after %.0fs "
            "(will retry via watcher)",
            client_key, _HOT_RELOAD_TIMEOUT,
        )
        # Clean up any partially-connected client to avoid resource leak
        try:
            await manager.remove_client(client_key)
        except Exception:
            pass
        return (
            f"Connection timed out after {_HOT_RELOAD_TIMEOUT:.0f}s; "
            "client will retry via background watcher"
        )
    except (Exception, BaseExceptionGroup):
        # replace_client re-raises BaseExceptionGroup from anyio TaskGroup
        # teardown (e.g. HTTP 401); without catching it here the worker
        # crashes during a hot-reload API call.
        logger.warning(
            "MCP client '%s' hot-reload failed (will retry via watcher)",
            client_key,
            exc_info=True,
        )
        return "Connection failed; client will retry via background watcher"


async def _hot_remove_client(
    request: Request,
    client_key: str,
) -> Optional[str]:
    """Disconnect an MCP client immediately after disable/delete.

    Returns None on success, warning string on failure.
    """
    manager = _get_mcp_manager(request)
    if manager is None:
        return None
    try:
        await asyncio.wait_for(
            manager.remove_client(client_key),
            timeout=_HOT_RELOAD_TIMEOUT,
        )
        logger.info("MCP client '%s' disconnected", client_key)
        return None
    except asyncio.TimeoutError:
        logger.warning(
            "MCP client '%s' disconnect timed out", client_key,
        )
        return "Disconnect timed out; client may remain active until restart"
    except Exception:
        logger.warning(
            "MCP client '%s' disconnect failed",
            client_key,
            exc_info=True,
        )
        return "Disconnect failed; client may remain active until restart"


@router.get(
    "",
    response_model=List[MCPClientInfo],
    summary="List all MCP clients",
)
async def list_mcp_clients() -> List[MCPClientInfo]:
    """Get list of all configured MCP clients."""
    config = load_config()
    return [
        _build_client_info(key, client)
        for key, client in config.mcp.clients.items()
    ]


@router.get(
    "/{client_key}",
    response_model=MCPClientInfo,
    summary="Get MCP client details",
)
async def get_mcp_client(client_key: str = Path(...)) -> MCPClientInfo:
    """Get details of a specific MCP client."""
    config = load_config()
    client = config.mcp.clients.get(client_key)
    if client is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")
    return _build_client_info(client_key, client)


@router.post(
    "",
    response_model=MCPClientInfo,
    summary="Create a new MCP client",
    status_code=201,
)
async def create_mcp_client(
    request: Request,
    client_key: str = Body(..., embed=True),
    client: MCPClientCreateRequest = Body(..., embed=True),
) -> MCPClientInfo:
    """Create a new MCP client configuration."""
    config = load_config()

    # Check if client already exists
    if client_key in config.mcp.clients:
        raise HTTPException(
            400,
            detail=f"MCP client '{client_key}' already exists. Use PUT to "
            f"update.",
        )

    # Create new client config
    new_client = MCPClientConfig(
        name=client.name,
        description=client.description,
        enabled=client.enabled,
        transport=client.transport,
        url=client.url,
        headers=client.headers,
        command=client.command,
        args=client.args,
        env=client.env,
        cwd=client.cwd,
    )

    # Add to config and save
    config.mcp.clients[client_key] = new_client
    save_config(config)

    # Hot-reload: connect client immediately if enabled
    warning = await _hot_reload_client(request, client_key, new_client)

    info = _build_client_info(client_key, new_client)
    info.connection_warning = warning
    return info


@router.put(
    "/{client_key}",
    response_model=MCPClientInfo,
    summary="Update an MCP client",
)
async def update_mcp_client(
    request: Request,
    client_key: str = Path(...),
    updates: MCPClientUpdateRequest = Body(...),
) -> MCPClientInfo:
    """Update an existing MCP client configuration."""
    config = load_config()

    # Check if client exists
    existing = config.mcp.clients.get(client_key)
    if existing is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    # Update fields if provided
    update_data = updates.model_dump(exclude_unset=True)

    # Special handling for env: merge with existing, don't replace
    if "env" in update_data and update_data["env"] is not None:
        updated_env = existing.env.copy() if existing.env else {}
        updated_env.update(update_data["env"])
        update_data["env"] = updated_env

    merged_data = existing.model_dump(mode="json")
    merged_data.update(update_data)
    updated_client = MCPClientConfig.model_validate(merged_data)
    config.mcp.clients[client_key] = updated_client

    # Save updated config
    save_config(config)

    # Hot-reload: connect or disconnect based on enabled state
    if updated_client.enabled:
        warning = await _hot_reload_client(request, client_key, updated_client)
    else:
        warning = await _hot_remove_client(request, client_key)

    info = _build_client_info(client_key, updated_client)
    info.connection_warning = warning
    return info


@router.patch(
    "/{client_key}/toggle",
    response_model=MCPClientInfo,
    summary="Toggle MCP client enabled status",
)
async def toggle_mcp_client(
    request: Request,
    client_key: str = Path(...),
) -> MCPClientInfo:
    """Toggle the enabled status of an MCP client."""
    config = load_config()

    client = config.mcp.clients.get(client_key)
    if client is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    # Toggle enabled status
    client.enabled = not client.enabled
    save_config(config)

    # Hot-reload: connect or disconnect based on new state
    if client.enabled:
        warning = await _hot_reload_client(request, client_key, client)
    else:
        warning = await _hot_remove_client(request, client_key)

    info = _build_client_info(client_key, client)
    info.connection_warning = warning
    return info


@router.delete(
    "/{client_key}",
    response_model=Dict[str, str],
    summary="Delete an MCP client",
)
async def delete_mcp_client(
    request: Request,
    client_key: str = Path(...),
) -> Dict[str, str]:
    """Delete an MCP client configuration."""
    config = load_config()

    if client_key not in config.mcp.clients:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")

    # Remove client
    del config.mcp.clients[client_key]
    save_config(config)

    # Hot-reload: disconnect client immediately
    warning = await _hot_remove_client(request, client_key)

    result = {"message": f"MCP client '{client_key}' deleted successfully"}
    if warning:
        result["connection_warning"] = warning
    return result
