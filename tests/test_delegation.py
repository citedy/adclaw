import pytest
from unittest.mock import patch, MagicMock
from adclaw.agents.tools.delegation import make_delegate_tool, DelegationContext
from adclaw.agents.persona_manager import PersonaManager
from adclaw.config.config import PersonaConfig


class TestDelegation:
    def test_make_delegate_tool_returns_callable(self):
        personas = [PersonaConfig(id="researcher", name="Researcher", soul_md="Find facts.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        assert callable(tool_fn)

    def test_delegate_to_unknown_agent(self):
        personas = [PersonaConfig(id="researcher", name="Researcher", soul_md="Find facts.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        result = tool_fn(agent_id="nonexistent", task="do something")
        assert "not found" in result.lower()

    def test_delegation_depth_limit(self):
        ctx = DelegationContext(max_depth=3)
        assert ctx.can_delegate()
        ctx.depth = 3
        assert not ctx.can_delegate()

    def test_delegation_depth_exceeded(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=0)
        tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
        result = tool_fn(agent_id="r", task="do something")
        assert "maximum delegation depth" in result.lower()

    def test_delegation_calls_executor(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        mock_exec = MagicMock(return_value="Result from sub-agent")
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            mock_exec,
        ):
            tool_fn = make_delegate_tool(mgr)
            result = tool_fn(agent_id="r", task="do something")
            assert result == "Result from sub-agent"
            mock_exec.assert_called_once()

    def test_delegation_error_handling(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=RuntimeError("LLM down"),
        ):
            tool_fn = make_delegate_tool(mgr)
            result = tool_fn(agent_id="r", task="do something")
            assert "failed" in result.lower()

    def test_delegation_depth_resets_after_call(self):
        """Verify depth is decremented even after successful delegation."""
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=3)
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            return_value="OK",
        ):
            tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
            tool_fn(agent_id="r", task="task1")
            assert ctx.depth == 0

    def test_delegation_depth_resets_after_error(self):
        """Verify depth is decremented even after failed delegation."""
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=3)
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=RuntimeError("boom"),
        ):
            tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
            tool_fn(agent_id="r", task="task1")
            assert ctx.depth == 0

    def test_unknown_agent_lists_available(self):
        """Error message should list available agent IDs."""
        personas = [
            PersonaConfig(id="alpha", name="A", soul_md="A."),
            PersonaConfig(id="beta", name="B", soul_md="B."),
        ]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        result = tool_fn(agent_id="gamma", task="test")
        assert "alpha" in result
        assert "beta" in result
