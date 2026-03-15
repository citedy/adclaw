# -*- coding: utf-8 -*-
"""Self-patching skills — tool for agent to fix broken skill scripts."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum patch attempts per script per session (prevent infinite loops)
_MAX_PATCHES_PER_SESSION = 3

# Track patches applied in current session: {script_path: count}
_session_patch_counts: dict[str, int] = {}


def _get_skill_dirs() -> tuple[Path, Path]:
    """Get customized and active skills directories."""
    from ..skills_manager import get_active_skills_dir, get_customized_skills_dir

    return get_customized_skills_dir(), get_active_skills_dir()


def _find_script(skill_name: str, script_path: str) -> Path | None:
    """Find a script file in customized or active skills directories."""
    customized_dir, active_dir = _get_skill_dirs()

    # Try customized first, then active
    for base in (customized_dir, active_dir):
        candidate = base / skill_name / script_path
        if candidate.exists() and candidate.is_file():
            # Security: ensure path doesn't escape skill directory
            try:
                candidate.resolve().relative_to(base.resolve())
            except ValueError:
                logger.warning(
                    "Path traversal detected: %s", script_path
                )
                return None
            return candidate
    return None


def _save_patch_record(
    skill_dir: Path,
    script_path: str,
    error: str,
    fix_description: str,
) -> None:
    """Save a record of the patch to .patches/ directory."""
    patches_dir = skill_dir / ".patches"
    patches_dir.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    safe_name = script_path.replace("/", "_").replace("\\", "_")
    record_path = patches_dir / f"{safe_name}.{ts}.json"

    record = {
        "script": script_path,
        "timestamp": ts,
        "error": error[:2000],
        "fix_description": fix_description[:2000],
    }
    record_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def patch_skill_script(
    skill_name: str,
    script_path: str,
    new_content: str,
    error_traceback: str = "",
    fix_description: str = "",
) -> dict[str, Any]:
    """Patch a skill script with new content, creating a backup.

    Args:
        skill_name: Name of the skill (directory name).
        script_path: Relative path to script within skill dir
                     (e.g. "scripts/process.py").
        new_content: The fixed script content.
        error_traceback: The error that triggered the fix.
        fix_description: Human-readable description of the fix.

    Returns:
        Dict with status, backup_path, and message.
    """
    # Rate limit: max N patches per script per session
    patch_key = f"{skill_name}/{script_path}"
    count = _session_patch_counts.get(patch_key, 0)
    if count >= _MAX_PATCHES_PER_SESSION:
        return {
            "success": False,
            "message": (
                f"Maximum {_MAX_PATCHES_PER_SESSION} patch attempts "
                f"reached for {patch_key} in this session. "
                f"Manual fix required."
            ),
        }

    # Find the script
    script_file = _find_script(skill_name, script_path)
    if script_file is None:
        return {
            "success": False,
            "message": f"Script not found: {skill_name}/{script_path}",
        }

    skill_dir = script_file.parent
    # Walk up to find skill root (directory containing SKILL.md)
    while skill_dir.name != skill_name and skill_dir != skill_dir.parent:
        skill_dir = skill_dir.parent

    try:
        # Create backup
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup_path = script_file.with_suffix(f".bak.{ts}")
        shutil.copy2(script_file, backup_path)

        # Write new content
        script_file.write_text(new_content, encoding="utf-8")

        # Also update in active_skills if it exists there
        _, active_dir = _get_skill_dirs()
        active_script = active_dir / skill_name / script_path
        if active_script.exists() and active_script != script_file:
            shutil.copy2(script_file, active_script)

        # Save patch record
        _save_patch_record(skill_dir, script_path, error_traceback, fix_description)

        # Update session counter
        _session_patch_counts[patch_key] = count + 1

        logger.info(
            "Patched skill script %s/%s (attempt %d/%d)",
            skill_name,
            script_path,
            count + 1,
            _MAX_PATCHES_PER_SESSION,
        )

        return {
            "success": True,
            "backup_path": str(backup_path),
            "message": (
                f"Patched {skill_name}/{script_path}. "
                f"Backup: {backup_path.name}. "
                f"Attempt {count + 1}/{_MAX_PATCHES_PER_SESSION}."
            ),
            "attempts_remaining": _MAX_PATCHES_PER_SESSION - count - 1,
        }

    except Exception as exc:
        logger.error(
            "Failed to patch %s/%s: %s", skill_name, script_path, exc
        )
        return {
            "success": False,
            "message": f"Patch failed: {exc}",
        }


def get_patch_history(skill_name: str) -> list[dict]:
    """Get patch history for a skill.

    Returns:
        List of patch records sorted by timestamp (newest first).
    """
    customized_dir, active_dir = _get_skill_dirs()
    records: list[dict] = []

    for base in (customized_dir, active_dir):
        patches_dir = base / skill_name / ".patches"
        if patches_dir.exists():
            for f in patches_dir.glob("*.json"):
                try:
                    record = json.loads(f.read_text(encoding="utf-8"))
                    records.append(record)
                except Exception:
                    pass

    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records


def reset_session_counts() -> None:
    """Reset patch attempt counters (called at session start)."""
    _session_patch_counts.clear()


# --- Tool registration helper ---

TOOL_SPEC = {
    "name": "patch_skill_script",
    "description": (
        "Fix a broken skill script by replacing its content. "
        "Creates a backup of the original. Use when a skill script "
        "fails with an error — read the script, fix the bug, and "
        "apply the patch. Maximum 3 attempts per script per session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill (directory name)",
            },
            "script_path": {
                "type": "string",
                "description": (
                    "Relative path to the script within the skill "
                    "directory (e.g. 'scripts/process.py')"
                ),
            },
            "new_content": {
                "type": "string",
                "description": "The fixed script content",
            },
            "error_traceback": {
                "type": "string",
                "description": "The error traceback that triggered the fix",
            },
            "fix_description": {
                "type": "string",
                "description": "Brief description of what was fixed",
            },
        },
        "required": ["skill_name", "script_path", "new_content"],
    },
}
