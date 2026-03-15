# -*- coding: utf-8 -*-
"""AdClaw Agents Module.

This module provides the main agent implementation and supporting utilities
for building AI agents with tools, skills, and memory management.

Public API:
- AdClawAgent: Main agent class
- create_model_and_formatter: Factory for creating models and formatters

Example:
    >>> from adclaw.agents import AdClawAgent, create_model_and_formatter
    >>> agent = AdClawAgent()
    >>> # Or with custom model
    >>> model, formatter = create_model_and_formatter()
"""

# AdClawAgent is lazy-loaded so that importing agents.skills_manager (e.g.
# from CLI init_cmd/skills_cmd) does not pull react_agent, agentscope, tools.
# pylint: disable=undefined-all-variable
__all__ = ["AdClawAgent", "create_model_and_formatter"]


def __getattr__(name: str):
    """Lazy load heavy imports."""
    if name == "AdClawAgent":
        from .react_agent import AdClawAgent

        return AdClawAgent
    if name == "create_model_and_formatter":
        from .model_factory import create_model_and_formatter

        return create_model_and_formatter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
