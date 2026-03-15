# -*- coding: utf-8 -*-
import logging
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ...agents.skills_manager import (
    SkillService,
    SkillInfo,
    list_available_skills,
    get_customized_skills_dir,
    get_active_skills_dir,
)
from ...agents.skills_hub import (
    search_hub_skills,
    install_skill_from_hub,
)
from ...agents.skill_scanner import SkillSecurityScanner
from ...agents.skill_security import read_scan_cache, scan_and_cache
from ...agents.skill_quality import evaluate_skill_quality
from ...agents.tools.skill_patcher import get_patch_history


logger = logging.getLogger(__name__)


class SkillSpec(SkillInfo):
    enabled: bool = False
    security: dict | None = None


class CreateSkillRequest(BaseModel):
    name: str = Field(..., description="Skill name")
    content: str = Field(..., description="Skill content (SKILL.md)")
    references: dict[str, Any] | None = Field(
        None,
        description="Optional tree structure for references/. "
        "Can be flat {filename: content} or nested "
        "{dirname: {filename: content}}",
    )
    scripts: dict[str, Any] | None = Field(
        None,
        description="Optional tree structure for scripts/. "
        "Can be flat {filename: content} or nested "
        "{dirname: {filename: content}}",
    )


class HubSkillSpec(BaseModel):
    slug: str
    name: str
    description: str = ""
    version: str = ""
    source_url: str = ""


class HubInstallRequest(BaseModel):
    bundle_url: str = Field(..., description="Skill URL")
    version: str = Field(default="", description="Optional version tag")
    enable: bool = Field(default=True, description="Enable after import")
    overwrite: bool = Field(
        default=False,
        description="Overwrite existing customized skill",
    )


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills() -> list[SkillSpec]:
    all_skills = SkillService.list_all_skills()

    available_skills = list_available_skills()
    skills_spec = []
    for skill in all_skills:
        # Read cached security scan if available
        security = None
        skill_path = Path(skill.path) if skill.path else None
        if skill_path and skill_path.exists():
            cached = read_scan_cache(skill_path)
            if cached:
                security = {
                    "score": cached.get("score"),
                    "pattern_scan": cached.get("pattern_scan"),
                    "llm_audit": cached.get("llm_audit"),
                    "auto_healed": cached.get("auto_healed", False),
                }
        skills_spec.append(
            SkillSpec(
                name=skill.name,
                content=skill.content,
                source=skill.source,
                path=skill.path,
                references=skill.references,
                scripts=skill.scripts,
                enabled=skill.name in available_skills,
                security=security,
            ),
        )
    return skills_spec


@router.get("/available")
async def get_available_skills() -> list[SkillSpec]:
    available_skills = SkillService.list_available_skills()
    skills_spec = []
    for skill in available_skills:
        skills_spec.append(
            SkillSpec(
                name=skill.name,
                content=skill.content,
                source=skill.source,
                path=skill.path,
                references=skill.references,
                scripts=skill.scripts,
                enabled=True,
            ),
        )
    return skills_spec


@router.get("/hub/search")
async def search_hub(
    q: str = "",
    limit: int = 20,
) -> list[HubSkillSpec]:
    results = search_hub_skills(q, limit=limit)
    return [
        HubSkillSpec(
            slug=item.slug,
            name=item.name,
            description=item.description,
            version=item.version,
            source_url=item.source_url,
        )
        for item in results
    ]


def _github_token_hint(bundle_url: str) -> str:
    """Hint to set GITHUB_TOKEN when URL is from GitHub/skills.sh."""
    if not bundle_url:
        return ""
    lower = bundle_url.lower()
    if "skills.sh" in lower or "github.com" in lower:
        return " Tip: set GITHUB_TOKEN (or GH_TOKEN) to avoid rate limits."
    return ""


@router.post("/hub/install")
async def install_from_hub(request: HubInstallRequest):
    try:
        result = install_skill_from_hub(
            bundle_url=request.bundle_url,
            version=request.version,
            enable=request.enable,
            overwrite=request.overwrite,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        # Upstream hub is flaky/rate-limited sometimes; surface as bad gateway.
        detail = str(e) + _github_token_hint(request.bundle_url)
        logger.exception(
            "Skill hub install failed (upstream/rate limit): %s",
            e,
        )
        raise HTTPException(status_code=502, detail=detail) from e
    except Exception as e:
        detail = f"Skill hub import failed: {e}" + _github_token_hint(
            request.bundle_url,
        )
        logger.exception("Skill hub import failed: %s", e)
        raise HTTPException(status_code=502, detail=detail) from e
    return {
        "installed": True,
        "name": result.name,
        "enabled": result.enabled,
        "source_url": result.source_url,
    }


CITEDY_SKILLS_REPO = "https://github.com/Citedy/citedy-seo-agent"
CITEDY_SKILL_NAMES = [
    "citedy-seo-agent",
    "citedy-content-writer",
    "citedy-content-ingestion",
    "citedy-trend-scout",
    "citedy-lead-magnets",
    "citedy-video-shorts",
]


@router.post("/hub/update-citedy")
async def update_citedy_skills():
    """Update all Citedy skills from GitHub to the latest version."""
    results = []
    errors = []
    for skill_name in CITEDY_SKILL_NAMES:
        url = f"{CITEDY_SKILLS_REPO}/tree/main/skills/{skill_name}"
        try:
            result = install_skill_from_hub(
                bundle_url=url,
                enable=True,
                overwrite=True,
            )
            results.append({"name": result.name, "updated": True})
        except Exception as e:
            logger.warning("Failed to update skill %s: %s", skill_name, e)
            errors.append({"name": skill_name, "error": str(e)})
    return {
        "updated": results,
        "errors": errors,
        "total": len(results),
        "failed": len(errors),
    }


@router.post("/batch-disable")
async def batch_disable_skills(skill_name: list[str]) -> None:
    for skill in skill_name:
        SkillService.disable_skill(skill)


@router.post("/batch-enable")
async def batch_enable_skills(skill_name: list[str]) -> None:
    for skill in skill_name:
        SkillService.enable_skill(skill)


@router.post("")
async def create_skill(request: CreateSkillRequest):
    result = SkillService.create_skill(
        name=request.name,
        content=request.content,
        references=request.references,
        scripts=request.scripts,
    )
    # Auto-scan and quality eval
    quality = None
    for base in (get_customized_skills_dir(), get_active_skills_dir()):
        skill_dir = base / request.name
        if skill_dir.exists():
            try:
                scan_and_cache(skill_dir, request.name)
            except Exception as e:
                logger.warning("Auto-scan failed for '%s': %s", request.name, e)
            try:
                qr = evaluate_skill_quality(skill_dir, request.name)
                quality = qr.to_dict()
            except Exception as e:
                logger.warning("Quality eval failed for '%s': %s", request.name, e)
            break
    return {"created": result, "quality": quality}


@router.post("/{skill_name}/disable")
async def disable_skill(skill_name: str):
    result = SkillService.disable_skill(skill_name)
    return {"disabled": result}


@router.post("/{skill_name}/enable")
async def enable_skill(skill_name: str):
    result = SkillService.enable_skill(skill_name)
    return {"enabled": result}


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str):
    """Delete a skill from customized_skills directory permanently.

    This only deletes skills from customized_skills directory.
    Built-in skills cannot be deleted.
    """
    result = SkillService.delete_skill(skill_name)
    return {"deleted": result}


@router.get("/{skill_name}/files/{source}/{file_path:path}")
async def load_skill_file(
    skill_name: str,
    source: str,
    file_path: str,
):
    """Load a specific file from a skill's references or scripts directory.

    Args:
        skill_name: Name of the skill
        source: Source directory ("builtin" or "customized")
        file_path: Path relative to skill directory, must start with
                   "references/" or "scripts/"

    Returns:
        File content as string, or None if not found

    Example:
        GET /skills/my_skill/files/customized/references/doc.md
        GET /skills/builtin_skill/files/builtin/scripts/utils/helper.py
    """
    content = SkillService.load_skill_file(
        skill_name=skill_name,
        file_path=file_path,
        source=source,
    )
    return {"content": content}


@router.get("/{skill_name}/quality")
async def get_skill_quality(skill_name: str):
    """Run quality evaluation on a skill's SKILL.md."""
    for base in (get_customized_skills_dir(), get_active_skills_dir()):
        skill_dir = base / skill_name
        if skill_dir.exists():
            result = evaluate_skill_quality(skill_dir, skill_name)
            return result.to_dict()
    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")


@router.get("/{skill_name}/security")
async def get_skill_security(skill_name: str):
    """Get security scan results for a skill (runs scan if not cached)."""
    for base in (get_customized_skills_dir(), get_active_skills_dir()):
        skill_dir = base / skill_name
        if skill_dir.exists():
            return scan_and_cache(skill_dir, skill_name)
    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")


@router.post("/{skill_name}/scan")
async def scan_skill(skill_name: str):
    """Run security scan on a skill."""
    # Find skill directory
    for base in (get_customized_skills_dir(), get_active_skills_dir()):
        skill_dir = base / skill_name
        if skill_dir.exists():
            scanner = SkillSecurityScanner()
            result = scanner.scan_skill(skill_dir, skill_name)
            return result.to_dict()
    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")


@router.post("/{skill_name}/llm-audit")
async def llm_audit_skill(skill_name: str):
    """Run LLM-based security audit on a skill (requires active LLM)."""
    from ...app.runner import runner as app_runner

    for base in (get_customized_skills_dir(), get_active_skills_dir()):
        skill_dir = base / skill_name
        if skill_dir.exists():
            scanner = SkillSecurityScanner()
            # Try to get LLM caller from runner
            llm_caller = None
            if app_runner and hasattr(app_runner, "get_llm_caller"):
                llm_caller = app_runner.get_llm_caller()
            result = await scanner.llm_audit_skill(
                skill_dir, llm_caller=llm_caller, skill_name=skill_name
            )
            return result.to_dict()
    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")


@router.get("/{skill_name}/patches")
async def skill_patches(skill_name: str):
    """Get patch history for a skill."""
    return {"skill_name": skill_name, "patches": get_patch_history(skill_name)}
