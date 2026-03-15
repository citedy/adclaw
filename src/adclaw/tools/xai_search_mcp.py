#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight MCP server wrapping xAI Responses API (web_search + x_search).

Run as stdio MCP server:
    python -m adclaw.tools.xai_search_mcp

Requires XAI_API_KEY environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

XAI_API_URL = "https://api.x.ai/v1/responses"
XAI_MODEL = "grok-4-1-fast-non-reasoning"


def _call_xai(query: str, tools: list[dict], api_key: str) -> dict:
    """Call xAI Responses API synchronously (urllib, no deps)."""
    from urllib.request import Request, urlopen

    body = json.dumps({
        "model": XAI_MODEL,
        "input": [{"role": "user", "content": query}],
        "tools": tools,
    }).encode()
    req = Request(
        XAI_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AdClaw/1.0",
        },
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _extract_result(data: dict) -> str:
    """Extract text + citations from xAI response."""
    parts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text = c.get("text", "")
                    parts.append(text)
                    annotations = c.get("annotations", [])
                    if annotations:
                        seen: set[str] = set()
                        sources: list[str] = []
                        for a in annotations:
                            url = a.get("url", "")
                            title = a.get("title", url)
                            if url and url not in seen:
                                seen.add(url)
                                sources.append(f"- [{title}]({url})")
                        if sources:
                            parts.append("\n**Sources:**\n" + "\n".join(sources))
    return "\n".join(parts) if parts else "No results found."


# --- MCP Protocol (JSON-RPC over stdio) ---

TOOLS = [
    {
        "name": "xai_web_search",
        "description": (
            "Search the web using xAI Grok. Returns summarized results "
            "with source citations. Use for real-time web information, "
            "news, research, competitor analysis."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "xai_x_search",
        "description": (
            "Search X (Twitter) posts using xAI Grok. Returns summarized "
            "results with citations. Use for social media trends, opinions, "
            "brand mentions, influencer content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for X/Twitter",
                },
                "handles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional: only search posts from these X handles "
                        "(max 10, without @)"
                    ),
                },
                "from_date": {
                    "type": "string",
                    "description": "Optional: start date (YYYY-MM-DD)",
                },
                "to_date": {
                    "type": "string",
                    "description": "Optional: end date (YYYY-MM-DD)",
                },
            },
            "required": ["query"],
        },
    },
]


def _handle_request(req: dict, api_key: str) -> dict:
    """Handle a single JSON-RPC request."""
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "xai-search",
                    "version": "1.0.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None  # notification, no response

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        query = args.get("query", "")

        if not query:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": "Error: query is required"}
                    ],
                    "isError": True,
                },
            }

        try:
            if tool_name == "xai_web_search":
                data = _call_xai(query, [{"type": "web_search"}], api_key)
            elif tool_name == "xai_x_search":
                tool_cfg: dict[str, Any] = {"type": "x_search"}
                if args.get("handles"):
                    tool_cfg["allowed_x_handles"] = args["handles"][:10]
                if args.get("from_date"):
                    tool_cfg["from_date"] = args["from_date"]
                if args.get("to_date"):
                    tool_cfg["to_date"] = args["to_date"]
                data = _call_xai(query, [tool_cfg], api_key)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Unknown tool: {tool_name}",
                            }
                        ],
                        "isError": True,
                    },
                }

            result_text = _extract_result(data)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"xAI search error: {e}"}
                    ],
                    "isError": True,
                },
            }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    """Run MCP server over stdio."""
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        print(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32000,
                        "message": "XAI_API_KEY not set",
                    },
                }
            ),
            flush=True,
        )
        sys.exit(1)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        resp = _handle_request(req, api_key)
        if resp is not None:
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
