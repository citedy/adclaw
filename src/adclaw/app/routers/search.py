# -*- coding: utf-8 -*-
"""Search provider configuration endpoints — Exa, xAI (web search)."""

import logging
import os

from fastapi import APIRouter, HTTPException

from ...envs.store import load_envs, save_envs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def _get_search_status() -> dict:
    """Return current search provider configuration status."""
    envs = load_envs()
    exa_key = envs.get("EXA_API_KEY", "") or os.getenv("EXA_API_KEY", "")
    xai_key = envs.get("XAI_API_KEY", "") or os.getenv("XAI_API_KEY", "")
    return {
        "exa": {
            "configured": bool(exa_key),
            "api_key_prefix": (exa_key[:12] + "...") if exa_key else None,
        },
        "xai": {
            "configured": bool(xai_key),
            "api_key_prefix": (xai_key[:12] + "...") if xai_key else None,
        },
    }


@router.get("/status")
async def search_status():
    """Check search provider configuration status."""
    return _get_search_status()


@router.post("/save-keys")
async def save_search_keys(body: dict):
    """Save search API keys and enable corresponding MCP clients."""
    exa_key = body.get("exa_api_key", "").strip()
    xai_key = body.get("xai_api_key", "").strip()

    if not exa_key and not xai_key:
        raise HTTPException(
            status_code=400,
            detail="At least one API key is required",
        )

    envs = load_envs()
    saved = []

    # --- Exa ---
    if exa_key:
        envs["EXA_API_KEY"] = exa_key
        os.environ["EXA_API_KEY"] = exa_key
        try:
            from ...config.config import MCPClientConfig
            from ...config.utils import load_config, save_config

            config = load_config()
            config.mcp.clients["exa"] = MCPClientConfig(
                name="exa_mcp",
                description="Exa AI search: web, code, people, companies",
                enabled=True,
                command="npx",
                args=["-y", "exa-mcp-server"],
                env={"EXA_API_KEY": exa_key},
            )
            save_config(config)
            logger.info("Exa MCP client enabled in config.json")
        except Exception as e:
            logger.warning("Failed to update Exa MCP config: %s", e)
        saved.append("exa")

    # --- xAI search (web_search + x_search via Responses API) ---
    if xai_key:
        envs["XAI_API_KEY"] = xai_key
        os.environ["XAI_API_KEY"] = xai_key
        # Enable xai_search MCP client
        try:
            from ...config.config import MCPClientConfig
            from ...config.utils import load_config, save_config

            config = load_config()
            config.mcp.clients["xai_search"] = MCPClientConfig(
                name="xai_search_mcp",
                description="xAI Grok: web search + X/Twitter search",
                enabled=True,
                command="python3",
                args=["-m", "adclaw.tools.xai_search_mcp"],
                env={"XAI_API_KEY": xai_key},
            )
            save_config(config)
            logger.info("xAI search MCP client enabled in config.json")
        except Exception as e:
            logger.warning("Failed to update xAI search MCP config: %s", e)
        # Also save as LLM provider for optional use
        try:
            from ...providers.store import update_provider_settings

            update_provider_settings("xai", api_key=xai_key)
        except Exception as e:
            logger.warning("Failed to update xAI provider: %s", e)
        saved.append("xai")

    save_envs(envs)
    return {"saved": saved, **_get_search_status()}
