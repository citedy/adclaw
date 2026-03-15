# -*- coding: utf-8 -*-
"""AOM Capture Hook — auto-captures MCP tool and skill results into AOM."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...memory_agent.ingest import IngestAgent

logger = logging.getLogger(__name__)

# Minimum result length worth capturing
_MIN_CONTENT_LENGTH = 20
# Maximum result length to capture (truncate longer)
_MAX_CONTENT_LENGTH = 10_000


class AOMCaptureHook:
    """Post-tool-execution hook that auto-ingests results into AOM.

    Usage:
        Called after tool execution in AdClawAgent._acting() to
        capture MCP tool and skill results.
    """

    def __init__(
        self,
        ingest_agent: IngestAgent,
        capture_mcp: bool = True,
        capture_skills: bool = True,
    ) -> None:
        self.ingest_agent = ingest_agent
        self.capture_mcp = capture_mcp
        self.capture_skills = capture_skills

    async def on_tool_result(
        self,
        tool_name: str,
        result: str,
        source_type: Optional[str] = None,
    ) -> None:
        """Capture a tool execution result into AOM.

        Args:
            tool_name: Name of the tool that produced the result.
            result: The string result from tool execution.
            source_type: Override source type (default: auto-detect).
        """
        if not result or len(result.strip()) < _MIN_CONTENT_LENGTH:
            return

        # Auto-detect source type
        if source_type is None:
            source_type = "mcp_tool"

        # Truncate if needed
        content = result[:_MAX_CONTENT_LENGTH]

        try:
            await self.ingest_agent.ingest(
                content=content,
                source_type=source_type,
                source_id=tool_name,
                skip_llm=False,
            )
            logger.debug("AOM captured result from %s (%d chars)", tool_name, len(content))
        except Exception as exc:
            logger.warning("AOM capture failed for %s: %s", tool_name, exc)
