# -*- coding: utf-8 -*-
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ...config.config import PersonaConfig, PersonaCronConfig
from ...config import load_config, save_config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["personas"])


class PersonaCreateRequest(BaseModel):
    id: str
    name: str
    soul_md: str = ""
    model_provider: str = ""
    model_name: str = ""
    skills: list[str] = []
    mcp_clients: list[str] = []
    is_coordinator: bool = False
    cron: Optional[PersonaCronConfig] = None


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    soul_md: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    skills: Optional[list[str]] = None
    mcp_clients: Optional[list[str]] = None
    is_coordinator: Optional[bool] = None
    cron: Optional[PersonaCronConfig] = None


@router.get("/agents/personas")
def list_personas():
    config = load_config()
    return [p.model_dump() for p in config.agents.personas]


@router.post("/agents/personas", status_code=201)
def create_persona(req: PersonaCreateRequest):
    config = load_config()
    existing_ids = {p.id for p in config.agents.personas}
    if req.id in existing_ids:
        raise HTTPException(409, f"Persona '{req.id}' already exists")
    if req.is_coordinator and any(p.is_coordinator for p in config.agents.personas):
        raise HTTPException(409, "A coordinator already exists")
    persona = PersonaConfig(**req.model_dump())
    config.agents.personas.append(persona)
    save_config(config)
    return persona.model_dump()


@router.get("/agents/personas/templates")
def list_templates():
    from ...agents.persona_templates import TEMPLATES
    return TEMPLATES


@router.post("/agents/personas/templates/{template_id}", status_code=201)
def create_from_template(template_id: str):
    from ...agents.persona_templates import get_template
    config = load_config()
    tmpl = get_template(template_id)
    if not tmpl:
        raise HTTPException(404, f"Template '{template_id}' not found")
    existing_ids = {p.id for p in config.agents.personas}
    base_id = tmpl["id"]
    pid = base_id
    counter = 2
    while pid in existing_ids:
        pid = f"{base_id}-{counter}"
        counter += 1
    tmpl["id"] = pid
    persona = PersonaConfig(**tmpl)
    config.agents.personas.append(persona)
    save_config(config)
    return persona.model_dump()


@router.get("/agents/personas/{persona_id}")
def get_persona(persona_id: str):
    config = load_config()
    for p in config.agents.personas:
        if p.id == persona_id:
            return p.model_dump()
    raise HTTPException(404, f"Persona '{persona_id}' not found")


@router.put("/agents/personas/{persona_id}")
def update_persona(persona_id: str, req: PersonaUpdateRequest):
    config = load_config()
    for i, p in enumerate(config.agents.personas):
        if p.id == persona_id:
            data = p.model_dump()
            updates = req.model_dump(exclude_unset=True)
            if "is_coordinator" in updates and updates["is_coordinator"]:
                others = [pp for pp in config.agents.personas if pp.is_coordinator and pp.id != persona_id]
                if others:
                    raise HTTPException(409, "Another coordinator already exists")
            data.update(updates)
            config.agents.personas[i] = PersonaConfig(**data)
            save_config(config)
            return config.agents.personas[i].model_dump()
    raise HTTPException(404, f"Persona '{persona_id}' not found")


@router.delete("/agents/personas/{persona_id}")
def delete_persona(persona_id: str):
    config = load_config()
    for i, p in enumerate(config.agents.personas):
        if p.id == persona_id:
            config.agents.personas.pop(i)
            save_config(config)
            return {"deleted": True, "id": persona_id}
    raise HTTPException(404, f"Persona '{persona_id}' not found")
