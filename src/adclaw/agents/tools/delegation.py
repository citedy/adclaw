import asyncio
import contextvars
import inspect
import logging
from typing import Optional

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..persona_manager import PersonaManager

logger = logging.getLogger(__name__)


class DelegationContext:
    """Tracks delegation depth to prevent infinite loops."""
    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self._depth_var = contextvars.ContextVar(
            f"adclaw_delegation_depth_{id(self)}",
            default=0,
        )

    @property
    def depth(self) -> int:
        return self._depth_var.get()

    @depth.setter
    def depth(self, value: int) -> None:
        self._depth_var.set(value)

    def can_delegate(self) -> bool:
        return self.depth < self.max_depth

    def enter(self):
        return self._depth_var.set(self.depth + 1)

    def reset(self, token) -> None:
        self._depth_var.reset(token)


def make_delegate_tool(persona_manager: PersonaManager, delegation_ctx: Optional[DelegationContext] = None):
    """Create a delegate_to_agent tool function bound to the persona manager."""
    ctx = delegation_ctx or DelegationContext()

    def _response(text: str) -> ToolResponse:
        return ToolResponse(
            content=[TextBlock(type="text", text=text)],
        )

    def _response_text(response: ToolResponse) -> str:
        parts: list[str] = []
        for block in response.content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(getattr(block, "text", ""))
        return "".join(parts)

    async def _delegate_to_agent_async(agent_id: str, task: str) -> ToolResponse:
        """Delegate a task to a specific agent persona and return their response.

        Use this when a task is better handled by a specialist on your team.

        Args:
            agent_id: Persona id, display name, or slug
                (e.g., "researcher", "content writer", "content-writer")
            task: The task description / prompt for the agent

        Returns:
            The agent's response text
        """
        resolved_id = persona_manager.resolve_reference(agent_id)
        persona = persona_manager.get_persona(resolved_id) if resolved_id else None
        if persona is None:
            available = [p.id for p in persona_manager.all_personas]
            return _response(
                f"Error: Agent '{agent_id}' not found. Available: {available}",
            )

        if not ctx.can_delegate():
            return _response(
                "Error: Maximum delegation depth "
                f"({ctx.max_depth}) reached. Handle this task directly.",
            )

        depth_token = ctx.enter()
        try:
            from .delegation_executor import execute_delegation
            result = await execute_delegation(persona, task, persona_manager)
            return _response(result)
        except Exception as e:
            logger.exception(f"Delegation to {agent_id} failed: {e}")
            return _response(
                f"Error: Delegation to '{agent_id}' failed.",
            )
        finally:
            ctx.reset(depth_token)

    def delegate_to_agent(agent_id: str, task: str):
        """Delegate to another persona.

        AgentScope calls this from an active event loop and receives an
        awaitable ToolResponse. Legacy direct callers outside an event loop get
        the plain text result synchronously, matching the previous helper API.
        """
        coro = _delegate_to_agent_async(agent_id=agent_id, task=task)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _response_text(asyncio.run(coro))
        return coro

    if hasattr(inspect, "markcoroutinefunction"):
        inspect.markcoroutinefunction(delegate_to_agent)

    return delegate_to_agent
