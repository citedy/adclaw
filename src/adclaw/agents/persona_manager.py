import os
import re
import logging
from pathlib import Path
from typing import Optional
from ..config.config import PersonaConfig

logger = logging.getLogger(__name__)


class PersonaManager:
    """Manages agent personas — working dirs, routing, shared files."""

    def __init__(self, working_dir: str, personas: list[PersonaConfig]):
        self.working_dir = Path(working_dir)
        self._personas = {p.id: p for p in personas}

    def ensure_dirs(self) -> None:
        """Create working directories for all personas."""
        for pid in self._personas:
            agent_dir = self.working_dir / "agents" / pid
            (agent_dir / "memory").mkdir(parents=True, exist_ok=True)
            shared_dir = self.working_dir / "shared" / pid
            shared_dir.mkdir(parents=True, exist_ok=True)

    def get_persona(self, persona_id: str) -> Optional[PersonaConfig]:
        return self._personas.get(persona_id)

    def get_coordinator(self) -> Optional[PersonaConfig]:
        for p in self._personas.values():
            if p.is_coordinator:
                return p
        return None

    def get_working_dir(self, persona_id: str) -> str:
        return str(self.working_dir / "agents" / persona_id)

    def get_shared_dir(self, persona_id: str) -> str:
        return str(self.working_dir / "shared" / persona_id)

    @staticmethod
    def _normalize_ref(value: str) -> str:
        """Normalize user-facing persona references for tolerant matching."""
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    def resolve_reference(self, value: str) -> Optional[str]:
        """Resolve a persona reference by id, display name, or slug."""
        normalized = self._normalize_ref(value)
        if not normalized:
            return None
        if normalized in self._personas:
            return normalized
        for pid, persona in self._personas.items():
            if self._normalize_ref(pid) == normalized:
                return pid
            if self._normalize_ref(persona.name) == normalized:
                return pid
        return None

    def _leading_tag_match(self, text: str) -> Optional[tuple[str, str]]:
        """Return ``(persona_id, remaining_text)`` for a leading @mention."""
        if not text.startswith("@"):
            return None
        after_at = text[1:]
        candidates: list[tuple[int, str]] = []
        for persona in self._personas.values():
            for alias in {persona.id, persona.name, persona.name.replace(" ", "-")}:
                alias = alias.strip()
                if not alias:
                    continue
                if re.match(
                    rf"^{re.escape(alias)}(?=\s|$|[.,;:!?])",
                    after_at,
                    re.IGNORECASE,
                ):
                    resolved = self.resolve_reference(alias)
                    if resolved:
                        candidates.append((len(alias), resolved))
        if not candidates:
            return None
        consumed, persona_id = max(candidates, key=lambda item: item[0])
        return persona_id, after_at[consumed:].lstrip(" \t,.;:!?")

    def resolve_tag(self, text: str) -> Optional[str]:
        """Extract leading @tag, matching by id, display name, or slug."""
        match = self._leading_tag_match(text)
        return match[0] if match else None

    def strip_tag(self, text: str) -> str:
        """Remove a leading @tag while preserving the remaining prompt."""
        match = self._leading_tag_match(text)
        return match[1] if match else text

    def get_team_summary(self) -> str:
        """Generate team summary for prompt injection."""
        lines = ["## Your Team\n"]
        for p in self._personas.values():
            role = p.soul_md.split('\n')[0] if p.soul_md else "No role defined"
            coord = " (coordinator)" if p.is_coordinator else ""
            lines.append(f"- **@{p.id}** ({p.name}){coord}: {role}")
        return "\n".join(lines)

    def list_shared_files(self, persona_id: str) -> list[str]:
        shared = Path(self.get_shared_dir(persona_id))
        if not shared.exists():
            return []
        return [f.name for f in shared.iterdir() if f.is_file()]

    @property
    def all_personas(self) -> list[PersonaConfig]:
        return list(self._personas.values())
