# -*- coding: utf-8 -*-
"""API endpoints for environment variable management."""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...envs import load_envs, save_envs, delete_env_var

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/envs", tags=["envs"])
_MASKED_SECRET_VALUE = "********"
_SECRET_KEY_RE = re.compile(
    r"(?:^|_)(?:API_)?(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)(?:_|$)"
    r"|(?:^|_)(?:AUTH|AUTHORIZATION)(?:_(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)|$)",
    re.IGNORECASE,
)


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class EnvVar(BaseModel):
    """Single environment variable."""

    key: str = Field(..., description="Variable name")
    value: str = Field(..., description="Variable value")


class EnvKeyRef(BaseModel):
    """Reference entry: which key is needed and by which plugin."""

    key: str
    plugin: str
    description: str
    configured: bool = False


def _is_secret_key(key: str) -> bool:
    """Return True for env names whose values must not be returned to clients."""
    return bool(_SECRET_KEY_RE.search(key))


def _safe_env_value(key: str, value: str) -> str:
    """Mask secret values while preserving configured/not-configured state."""
    if value and _is_secret_key(key):
        return _MASKED_SECRET_VALUE
    return value


def _env_var_list(envs: Dict[str, str]) -> List[EnvVar]:
    """Return env vars in stable order with secret values redacted."""
    return [
        EnvVar(key=k, value=_safe_env_value(k, v))
        for k, v in sorted(envs.items())
    ]


def _clean_env_replacement(body: Dict[str, str]) -> Dict[str, str]:
    """Prepare a full env replacement without overwriting masked secrets."""
    existing = load_envs()
    cleaned: Dict[str, str] = {}
    for raw_key, raw_value in body.items():
        key = raw_key.strip()
        value = raw_value
        if _is_secret_key(key) and value == _MASKED_SECRET_VALUE and key in existing:
            value = existing[key]
        cleaned[key] = value
    return cleaned


class BulkImportRequest(BaseModel):
    """Raw .env text for bulk import."""

    text: str = Field(..., description="Contents of .env file")
    merge: bool = Field(
        True,
        description="Merge with existing vars (True) or replace all (False)",
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get(
    "",
    response_model=List[EnvVar],
    summary="List all environment variables",
)
async def list_envs() -> List[EnvVar]:
    """Return all configured env vars."""
    envs = load_envs()
    return _env_var_list(envs)


@router.put(
    "",
    response_model=List[EnvVar],
    summary="Batch save environment variables",
    description="Replace all environment variables with "
    "the provided dict. Keys not present are removed.",
)
async def batch_save_envs(
    body: Dict[str, str],
) -> List[EnvVar]:
    """Batch save – full replacement of all env vars."""
    # Validate keys
    for key in body:
        if not key.strip():
            raise HTTPException(
                400,
                detail="Key cannot be empty",
            )
    cleaned = _clean_env_replacement(body)
    save_envs(cleaned)
    return _env_var_list(cleaned)


@router.delete(
    "/{key}",
    response_model=List[EnvVar],
    summary="Delete an environment variable",
)
async def delete_env(key: str) -> List[EnvVar]:
    """Delete a single env var."""
    envs = load_envs()
    if key not in envs:
        raise HTTPException(
            404,
            detail=f"Env var '{key}' not found",
        )
    envs = delete_env_var(key)
    return _env_var_list(envs)


# ------------------------------------------------------------------
# API key reference & bulk import
# ------------------------------------------------------------------

# Registry of all API keys used by built-in MCP plugins.
# Kept here (not in config.py) to avoid circular imports and to
# provide human-readable descriptions for the UI.
_KEY_REGISTRY: List[Dict[str, str]] = [
    # Search & SEO
    {"key": "TAVILY_API_KEY", "plugin": "Tavily Search", "description": "Web search API key (tavily.com)"},
    {"key": "AHREFS_API_KEY", "plugin": "Ahrefs", "description": "SEO: backlinks, keywords, traffic (ahrefs.com)"},
    {"key": "DATAFORSEO_LOGIN", "plugin": "DataForSEO", "description": "SERP & keyword API login (dataforseo.com)"},
    {"key": "DATAFORSEO_PASSWORD", "plugin": "DataForSEO", "description": "SERP & keyword API password"},
    # Marketing & Content
    {"key": "CITEDY_API_KEY", "plugin": "Citedy", "description": "SEO & marketing tools — 59 tools (citedy.com)"},
    # Advertising
    {"key": "GOOGLE_ADS_DEVELOPER_TOKEN", "plugin": "Google Ads", "description": "Google Ads API developer token"},
    {"key": "META_ADS_ACCESS_TOKEN", "plugin": "Meta Ads", "description": "Facebook & Instagram ads access token"},
    # Analytics
    # (Google Analytics uses OAuth, no static key needed)
    # Social Media
    {"key": "TWITTER_API_KEY", "plugin": "Twitter/X", "description": "Twitter API key (developer.x.com)"},
    {"key": "TWITTER_API_SECRET", "plugin": "Twitter/X", "description": "Twitter API secret"},
    {"key": "TWITTER_ACCESS_TOKEN", "plugin": "Twitter/X", "description": "Twitter access token"},
    {"key": "TWITTER_ACCESS_SECRET", "plugin": "Twitter/X", "description": "Twitter access token secret"},
    {"key": "YOUTUBE_API_KEY", "plugin": "YouTube", "description": "YouTube Data API key"},
    {"key": "INSTAGRAM_ACCESS_TOKEN", "plugin": "Instagram", "description": "Instagram Graph API access token"},
    # Email
    {"key": "SENDGRID_API_KEY", "plugin": "SendGrid", "description": "SendGrid email API key (sendgrid.com)"},
    # CRM
    {"key": "HUBSPOT_ACCESS_TOKEN", "plugin": "HubSpot", "description": "HubSpot CRM private app token"},
    # Browser & Scraping
    {"key": "BROWSERBASE_API_KEY", "plugin": "Browserbase", "description": "Browserbase cloud browser API key"},
    {"key": "BROWSERBASE_PROJECT_ID", "plugin": "Browserbase", "description": "Browserbase project ID"},
    {"key": "FIRECRAWL_API_KEY", "plugin": "Firecrawl", "description": "Firecrawl web scraping API key"},
]


@router.get(
    "/keys",
    response_model=List[EnvKeyRef],
    summary="List all known API keys with plugin info",
)
async def list_key_references() -> List[EnvKeyRef]:
    """Return a reference list of all API keys needed by built-in plugins,
    with a flag indicating whether each is already configured."""
    envs = load_envs()
    return [
        EnvKeyRef(
            key=entry["key"],
            plugin=entry["plugin"],
            description=entry["description"],
            configured=bool(envs.get(entry["key"])),
        )
        for entry in _KEY_REGISTRY
    ]


_ENV_LINE_RE = re.compile(
    r"""^\s*(?:export\s+)?      # optional 'export '
    ([A-Za-z_][A-Za-z0-9_]*)    # key
    \s*=\s*                     # =
    (?:"([^"]*)"|'([^']*)'|(.*))\s*$  # value: "quoted", 'quoted', or bare
    """,
    re.VERBOSE,
)


@router.post(
    "/bulk-import",
    response_model=List[EnvVar],
    summary="Bulk import from .env text",
)
async def bulk_import(body: BulkImportRequest) -> List[EnvVar]:
    """Parse .env formatted text and save all variables.

    Lines starting with # are ignored. Supports KEY=VALUE,
    KEY="VALUE", KEY='VALUE', and export KEY=VALUE formats.
    """
    parsed: Dict[str, str] = {}
    skipped: list[str] = []
    for line in body.text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if len(stripped) > 10000:
            key = stripped.split("=", 1)[0] if "=" in stripped else "(unparseable)"
            skipped.append(key)
            logger.warning("Skipping env line exceeding 10000 chars: %s", key)
            continue
        m = _ENV_LINE_RE.match(stripped)
        if m:
            key = m.group(1)
            value = m.group(2) if m.group(2) is not None else (
                m.group(3) if m.group(3) is not None else (m.group(4) or "")
            )
            parsed[key] = value

    if not parsed and not skipped:
        raise HTTPException(400, detail="No valid KEY=VALUE lines found")
    if not parsed and skipped:
        raise HTTPException(
            400,
            detail=f"All lines skipped (exceeding 10000 chars): {', '.join(skipped)}",
        )

    if body.merge:
        envs = load_envs()
        envs.update(parsed)
    else:
        envs = parsed

    save_envs(envs)
    return _env_var_list(envs)
