"""Auto-heal broken skill YAML frontmatter using the user's LLM."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

HEAL_PROMPT = """Fix the YAML frontmatter in this SKILL.md file. The error was:

{error}

The file content is:

```
{content}
```

Rules:
- The file MUST start with `---`, then YAML with at least `name` and `description` fields, then `---`
- Fix any YAML syntax errors, invalid unicode escapes, or missing fields
- The `name` field should be a simple lowercase-kebab-case identifier
- The `description` field should be a single English sentence
- Do NOT modify the markdown body after the closing `---`
- Return ONLY the complete fixed file content, no explanations"""


@dataclass
class HealResult:
    healed: bool
    skill_name: str
    original: str
    fixed: str
    error: str
    message: str = ""


async def heal_skill(
    skill_dir: Path,
    error_message: str,
    llm_caller: Callable[[str], Awaitable[str]],
) -> HealResult:
    """Attempt to fix a broken SKILL.md using LLM."""
    skill_name = skill_dir.name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return HealResult(
            healed=False, skill_name=skill_name,
            original="", fixed="", error=error_message,
            message="SKILL.md not found",
        )

    original = skill_file.read_text(encoding="utf-8")
    prompt = HEAL_PROMPT.format(error=error_message, content=original)

    try:
        fixed = await llm_caller(prompt)
    except Exception as e:
        logger.warning("LLM heal failed for '%s': %s", skill_name, e)
        return HealResult(
            healed=False, skill_name=skill_name,
            original=original, fixed="", error=error_message,
            message=f"LLM call failed: {e}",
        )

    # Strip markdown code fences if LLM wrapped the response
    fixed = fixed.strip()
    if fixed.startswith("```"):
        lines = fixed.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        fixed = "\n".join(lines)

    if not fixed or fixed == original:
        return HealResult(
            healed=False, skill_name=skill_name,
            original=original, fixed=fixed, error=error_message,
            message="LLM returned unchanged or empty content",
        )

    if not fixed.startswith("---"):
        return HealResult(
            healed=False, skill_name=skill_name,
            original=original, fixed=fixed, error=error_message,
            message="LLM response missing frontmatter delimiters",
        )

    # Backup original and write fix
    backup = skill_dir / "SKILL.md.bak"
    backup.write_text(original, encoding="utf-8")
    skill_file.write_text(fixed, encoding="utf-8")

    logger.info("Auto-healed skill '%s': %s", skill_name, error_message[:80])

    return HealResult(
        healed=True, skill_name=skill_name,
        original=original, fixed=fixed, error=error_message,
        message=f"Fixed: {error_message[:80]}",
    )
