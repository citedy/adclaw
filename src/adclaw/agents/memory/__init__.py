# -*- coding: utf-8 -*-
"""Memory management module for AdClaw agents."""

from typing import TYPE_CHECKING

from .agent_md_manager import AgentMdManager

__all__ = [
    "AgentMdManager",
    "MemoryManager",
]

if TYPE_CHECKING:
    from .memory_manager import MemoryManager


def __getattr__(name: str):
    """Import ReMe-backed MemoryManager only when it is actually requested."""
    if name == "MemoryManager":
        from .memory_manager import MemoryManager

        return MemoryManager
    raise AttributeError(name)
