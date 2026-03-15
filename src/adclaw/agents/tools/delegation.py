import logging
from typing import Optional
from ..persona_manager import PersonaManager

logger = logging.getLogger(__name__)


class DelegationContext:
    """Tracks delegation depth to prevent infinite loops."""
    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self.depth = 0

    def can_delegate(self) -> bool:
        return self.depth < self.max_depth


def make_delegate_tool(persona_manager: PersonaManager, delegation_ctx: Optional[DelegationContext] = None):
    """Create a delegate_to_agent tool function bound to the persona manager."""
    ctx = delegation_ctx or DelegationContext()

    def delegate_to_agent(agent_id: str, task: str) -> str:
        """Delegate a task to a specific agent persona and return their response.

        Use this when a task is better handled by a specialist on your team.

        Args:
            agent_id: The persona ID to delegate to (e.g., "researcher", "content")
            task: The task description / prompt for the agent

        Returns:
            The agent's response text
        """
        persona = persona_manager.get_persona(agent_id)
        if persona is None:
            available = [p.id for p in persona_manager.all_personas]
            return f"Error: Agent '{agent_id}' not found. Available: {available}"

        if not ctx.can_delegate():
            return f"Error: Maximum delegation depth ({ctx.max_depth}) reached. Handle this task directly."

        ctx.depth += 1
        try:
            from .delegation_executor import execute_delegation
            result = execute_delegation(persona, task, persona_manager)
            return result
        except Exception as e:
            logger.exception(f"Delegation to {agent_id} failed: {e}")
            return f"Error: Delegation to '{agent_id}' failed: {str(e)}"
        finally:
            ctx.depth -= 1

    return delegate_to_agent
