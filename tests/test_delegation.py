import asyncio
import inspect
from unittest.mock import patch, MagicMock

import pytest
from adclaw.agents.tools.delegation import make_delegate_tool, DelegationContext
from adclaw.agents.persona_manager import PersonaManager
from adclaw.config.config import PersonaConfig


def _tool_text(response) -> str:
    parts = []
    for block in response.content:
        if isinstance(block, dict):
            parts.append(block.get("text", ""))
        else:
            parts.append(getattr(block, "text", ""))
    return "".join(parts)


def test_delegation_executor_text_from_content_normalizes_none():
    from adclaw.agents.tools.delegation_executor import _text_from_content

    assert _text_from_content(None) == ""


class TestDelegation:
    def test_make_delegate_tool_returns_callable(self):
        personas = [PersonaConfig(id="researcher", name="Researcher", soul_md="Find facts.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        assert callable(tool_fn)
        if hasattr(inspect, "markcoroutinefunction"):
            assert inspect.iscoroutinefunction(tool_fn)

    def test_delegate_to_unknown_agent_sync_compatibility(self):
        personas = [PersonaConfig(id="researcher", name="Researcher", soul_md="Find facts.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        result = tool_fn(agent_id="nonexistent", task="do something")
        assert isinstance(result, str)
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_delegate_to_unknown_agent(self):
        personas = [PersonaConfig(id="researcher", name="Researcher", soul_md="Find facts.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        result = _tool_text(
            await tool_fn(agent_id="nonexistent", task="do something"),
        )
        assert "not found" in result.lower()

    def test_delegation_depth_limit(self):
        ctx = DelegationContext(max_depth=3)
        assert ctx.can_delegate()
        ctx.depth = 3
        assert not ctx.can_delegate()

    @pytest.mark.asyncio
    async def test_delegation_depth_exceeded(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=0)
        tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
        result = _tool_text(await tool_fn(agent_id="r", task="do something"))
        assert "maximum delegation depth" in result.lower()

    @pytest.mark.asyncio
    async def test_delegation_calls_executor(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        async def _mock_exec(*args, **kwargs):  # noqa: ARG001
            return "Result from sub-agent"

        mock_exec = MagicMock(side_effect=_mock_exec)
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            mock_exec,
        ):
            tool_fn = make_delegate_tool(mgr)
            result = _tool_text(await tool_fn(agent_id="r", task="do something"))
            assert result == "Result from sub-agent"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegation_accepts_display_name(self):
        personas = [
            PersonaConfig(
                id="content-writer",
                name="Content Writer",
                soul_md="Test.",
            ),
        ]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        async def _mock_exec(*args, **kwargs):  # noqa: ARG001
            return "OK"

        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=_mock_exec,
        ):
            tool_fn = make_delegate_tool(mgr)
            result = _tool_text(
                await tool_fn(agent_id="content writer", task="draft"),
            )
            assert result == "OK"

    @pytest.mark.asyncio
    async def test_delegation_error_handling(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=RuntimeError("LLM down"),
        ):
            tool_fn = make_delegate_tool(mgr)
            result = _tool_text(await tool_fn(agent_id="r", task="do something"))
            assert "failed" in result.lower()
            assert "LLM down" not in result

    @pytest.mark.asyncio
    async def test_delegation_depth_resets_after_call(self):
        """Verify depth is decremented even after successful delegation."""
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=3)
        async def _mock_exec(*args, **kwargs):  # noqa: ARG001
            return "OK"

        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=_mock_exec,
        ):
            tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
            await tool_fn(agent_id="r", task="task1")
            assert ctx.depth == 0

    @pytest.mark.asyncio
    async def test_delegation_depth_is_task_scoped(self):
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=1)

        async def _mock_exec(*args, **kwargs):  # noqa: ARG001
            await asyncio.sleep(0)
            return "OK"

        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=_mock_exec,
        ):
            tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
            first, second = await asyncio.gather(
                tool_fn(agent_id="r", task="task1"),
                tool_fn(agent_id="r", task="task2"),
            )

        assert _tool_text(first) == "OK"
        assert _tool_text(second) == "OK"
        assert ctx.depth == 0

    @pytest.mark.asyncio
    async def test_delegation_depth_resets_after_error(self):
        """Verify depth is decremented even after failed delegation."""
        personas = [PersonaConfig(id="r", name="R", soul_md="Test.")]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        ctx = DelegationContext(max_depth=3)
        with patch(
            "adclaw.agents.tools.delegation_executor.execute_delegation",
            side_effect=RuntimeError("boom"),
        ):
            tool_fn = make_delegate_tool(mgr, delegation_ctx=ctx)
            await tool_fn(agent_id="r", task="task1")
            assert ctx.depth == 0

    @pytest.mark.asyncio
    async def test_unknown_agent_lists_available(self):
        """Error message should list available agent IDs."""
        personas = [
            PersonaConfig(id="alpha", name="A", soul_md="A."),
            PersonaConfig(id="beta", name="B", soul_md="B."),
        ]
        mgr = PersonaManager(working_dir="/tmp/test", personas=personas)
        tool_fn = make_delegate_tool(mgr)
        result = _tool_text(await tool_fn(agent_id="gamma", task="test"))
        assert "alpha" in result
        assert "beta" in result
