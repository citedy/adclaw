import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_safe_agent_id(agent_id: str) -> bool:
    """Validate agent_id contains only safe characters."""
    return bool(re.match(r'^[a-z0-9_-]+$', agent_id))


def _is_safe_path(base: str, requested: str) -> bool:
    """Check that resolved path stays within base directory."""
    base_resolved = os.path.realpath(base)
    full_resolved = os.path.realpath(os.path.join(base, requested))
    return full_resolved.startswith(base_resolved + os.sep) or full_resolved == base_resolved


def make_write_shared_file(shared_root: str, agent_id: str):
    agent_dir = os.path.join(shared_root, agent_id)

    def write_shared_file(filename: str, content: str) -> str:
        """Write a file to your shared directory where other agents can read it.
        Args:
            filename: File name (e.g., "daily-report.md"). No path separators.
            content: File content to write.
        Returns:
            Success or error message.
        """
        if not _is_safe_path(agent_dir, filename):
            return "Error: Invalid filename — path traversal not allowed."
        os.makedirs(agent_dir, exist_ok=True)
        filepath = os.path.join(agent_dir, os.path.basename(filename))
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: Written to shared/{agent_id}/{os.path.basename(filename)}"
        except Exception as e:
            return f"Error writing file: {e}"
    return write_shared_file


def make_read_shared_file(shared_root: str):
    def read_shared_file(agent_id: str, filename: str) -> str:
        """Read a file from any agent's shared directory.
        Args:
            agent_id: The agent whose shared file to read.
            filename: The file name to read.
        Returns:
            File content or error message.
        """
        if not _is_safe_agent_id(agent_id):
            return "Error: Invalid agent_id — path traversal not allowed."
        agent_dir = os.path.join(shared_root, agent_id)
        if not _is_safe_path(agent_dir, filename):
            return "Error: Invalid path — path traversal not allowed."
        filepath = os.path.join(agent_dir, filename)
        if not os.path.exists(filepath):
            return f"Error: File not found: shared/{agent_id}/{filename}"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    return read_shared_file


def make_list_shared_files(shared_root: str):
    def list_shared_files(agent_id: str = "") -> str:
        """List files in shared directories.
        Args:
            agent_id: Specific agent ID, or empty to list all.
        Returns:
            Formatted list of shared files.
        """
        if agent_id:
            if not _is_safe_agent_id(agent_id):
                return "Error: Invalid agent_id — path traversal not allowed."
            agent_dir = os.path.join(shared_root, agent_id)
            if not os.path.isdir(agent_dir):
                return f"No shared directory for agent '{agent_id}'."
            files = [f for f in os.listdir(agent_dir) if os.path.isfile(os.path.join(agent_dir, f))]
            return f"shared/{agent_id}/: {', '.join(files) if files else '(empty)'}"
        else:
            lines = []
            if not os.path.isdir(shared_root):
                return "No shared directories exist yet."
            for d in sorted(os.listdir(shared_root)):
                dp = os.path.join(shared_root, d)
                if os.path.isdir(dp):
                    files = [f for f in os.listdir(dp) if os.path.isfile(os.path.join(dp, f))]
                    lines.append(f"shared/{d}/: {', '.join(files) if files else '(empty)'}")
            return "\n".join(lines) if lines else "No shared directories."
    return list_shared_files
