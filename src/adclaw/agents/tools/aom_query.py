# -*- coding: utf-8 -*-
"""AOM Query tool — allows the agent to query long-term memory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...memory_agent.query import QueryAgent


def create_aom_query_tool(query_agent: QueryAgent):
    """Create a tool function for querying AOM long-term memory.

    Args:
        query_agent: The QueryAgent instance.

    Returns:
        An async tool function that can be registered with Toolkit.
    """

    async def query_long_term_memory(question: str) -> str:
        """Search the long-term memory store for information from past tool results,
        conversations, and ingested files. Use this when you need to recall
        previous findings, research results, or accumulated knowledge.

        Args:
            question: A natural language question about what to recall.

        Returns:
            A synthesized answer with citations to source memories.
        """
        result = await query_agent.query(question, max_results=10)
        if not result.citations:
            return "No relevant memories found in long-term storage."

        lines = [result.answer, "", "--- Sources ---"]
        for c in result.citations[:5]:
            lines.append(
                f"[{c.memory.source_type}/{c.memory.source_id}] "
                f"(score={c.score:.3f}) {c.memory.content[:200]}"
            )
        return "\n".join(lines)

    return query_long_term_memory
