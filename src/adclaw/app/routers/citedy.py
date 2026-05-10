# -*- coding: utf-8 -*-
"""Citedy integration endpoints — balance check, API key status."""

import logging
import os
from urllib.request import Request, urlopen
from urllib.error import URLError
import json

from fastapi import APIRouter, HTTPException

from ...envs.store import load_envs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/citedy", tags=["citedy"])

CITEDY_API_BASE = "https://www.citedy.com"
CITEDY_DEVELOPER_URL = "https://www.citedy.com/developer"
CITEDY_BILLING_URL = "https://www.citedy.com/dashboard/billing"


def _get_citedy_api_key() -> str:
    """Get Citedy API key from environment variables."""
    envs = load_envs()
    return envs.get("CITEDY_API_KEY", "") or os.getenv("CITEDY_API_KEY", "")


@router.get("/status")
async def citedy_status():
    """Check Citedy integration status — API key configured, balance, etc."""
    api_key = _get_citedy_api_key()
    if not api_key:
        return {
            "configured": False,
            "api_key_prefix": None,
            "balance": None,
            "developer_url": CITEDY_DEVELOPER_URL,
            "billing_url": CITEDY_BILLING_URL,
        }

    # Try to fetch agent info from Citedy
    try:
        req = Request(
            f"{CITEDY_API_BASE}/api/agent/me",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AdClaw/1.0",
            },
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        balance_info = data.get("tenant_balance", {})
        return {
            "configured": True,
            "api_key_prefix": api_key[:20] + "..." if len(api_key) > 20 else api_key,
            "agent_name": data.get("agent_name"),
            "status": data.get("status"),
            "balance": {
                "credits": balance_info.get("credits", 0),
                "status": balance_info.get("status", "unknown"),
            },
            "developer_url": CITEDY_DEVELOPER_URL,
            "billing_url": CITEDY_BILLING_URL,
        }
    except URLError as e:
        logger.warning("Failed to fetch Citedy status: %s", e)
        return {
            "configured": True,
            "api_key_prefix": api_key[:20] + "..." if len(api_key) > 20 else api_key,
            "balance": None,
            "error": "Could not connect to Citedy API",
            "developer_url": CITEDY_DEVELOPER_URL,
            "billing_url": CITEDY_BILLING_URL,
        }
    except Exception as e:
        logger.warning("Citedy status check failed: %s", e)
        return {
            "configured": True,
            "api_key_prefix": api_key[:20] + "..." if len(api_key) > 20 else api_key,
            "balance": None,
            "error": f"Could not check Citedy status ({type(e).__name__})",
            "developer_url": CITEDY_DEVELOPER_URL,
            "billing_url": CITEDY_BILLING_URL,
        }


@router.post("/save-api-key")
async def save_citedy_api_key(body: dict):
    """Save Citedy API key to environment variables and enable Citedy MCP."""
    api_key = body.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Save to env vars
    envs = load_envs()
    envs["CITEDY_API_KEY"] = api_key
    from ...envs.store import save_envs
    save_envs(envs)
    os.environ["CITEDY_API_KEY"] = api_key

    # Enable Citedy MCP client in config.json
    try:
        from ...config.utils import load_config, save_config
        from ...config.config import MCPClientConfig

        config = load_config()
        config.mcp.clients["citedy"] = MCPClientConfig(
            name="citedy_mcp",
            description="Citedy SEO & Marketing Tools (59 tools)",
            enabled=True,
            transport="streamable_http",
            url="https://mcp.citedy.com/mcp",
            headers={},
            env={"CITEDY_API_KEY": api_key},
        )
        save_config(config)
        logger.info("Citedy MCP client enabled in config.json")
    except Exception as e:
        logger.warning("Failed to update MCP config: %s", e)

    return {"saved": True, "api_key_prefix": api_key[:20] + "..."}
