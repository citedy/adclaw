import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock
from adclaw.config.config import Config, AgentsConfig, PersonaConfig


@pytest.fixture
def client():
    from adclaw.app.routers.personas import router
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


class TestPersonaAPI:
    def test_list_empty(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = Config()
            resp = client.get("/api/agents/personas")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_create_persona(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock_load, \
             patch("adclaw.app.routers.personas.save_config"):
            mock_load.return_value = Config()
            resp = client.post("/api/agents/personas", json={
                "id": "researcher", "name": "Researcher", "soul_md": "Find facts."
            })
            assert resp.status_code == 201
            assert resp.json()["id"] == "researcher"

    def test_create_duplicate_id(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = Config(agents=AgentsConfig(
                personas=[PersonaConfig(id="researcher", name="R")]
            ))
            resp = client.post("/api/agents/personas", json={"id": "researcher", "name": "Another"})
            assert resp.status_code == 409

    def test_get_persona(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = Config(agents=AgentsConfig(
                personas=[PersonaConfig(id="r", name="R", soul_md="Be helpful.")]
            ))
            resp = client.get("/api/agents/personas/r")
            assert resp.status_code == 200
            assert resp.json()["soul_md"] == "Be helpful."

    def test_get_not_found(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = Config()
            resp = client.get("/api/agents/personas/nope")
            assert resp.status_code == 404

    def test_update_persona(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock_load, \
             patch("adclaw.app.routers.personas.save_config"):
            mock_load.return_value = Config(agents=AgentsConfig(
                personas=[PersonaConfig(id="r", name="R")]
            ))
            resp = client.put("/api/agents/personas/r", json={"soul_md": "Updated."})
            assert resp.status_code == 200
            assert resp.json()["soul_md"] == "Updated."

    def test_update_persona_skills_mcp_and_model(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock_load, \
             patch("adclaw.app.routers.personas.save_config") as mock_save:
            mock_load.return_value = Config(agents=AgentsConfig(
                personas=[PersonaConfig(id="r", name="R")]
            ))
            resp = client.put("/api/agents/personas/r", json={
                "model_provider": "adclaw-host-ai",
                "model_name": "@cf/google/gemma-4-26b-a4b-it",
                "skills": ["citedy.marketing-research"],
                "mcp_clients": ["citedy"],
            })
            body = resp.json()
            assert resp.status_code == 200
            assert body["model_provider"] == "adclaw-host-ai"
            assert body["model_name"] == "@cf/google/gemma-4-26b-a4b-it"
            assert body["skills"] == ["citedy.marketing-research"]
            assert body["mcp_clients"] == ["citedy"]
            mock_save.assert_called_once()
            saved_cfg = mock_save.call_args.args[0]
            saved_persona = next(
                p for p in saved_cfg.agents.personas if p.id == "r"
            )
            assert saved_persona.model_provider == "adclaw-host-ai"
            assert saved_persona.model_name == "@cf/google/gemma-4-26b-a4b-it"
            assert saved_persona.skills == ["citedy.marketing-research"]
            assert saved_persona.mcp_clients == ["citedy"]

    def test_delete_persona(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock_load, \
             patch("adclaw.app.routers.personas.save_config"):
            mock_load.return_value = Config(agents=AgentsConfig(
                personas=[PersonaConfig(id="r", name="R")]
            ))
            resp = client.delete("/api/agents/personas/r")
            assert resp.status_code == 200

    def test_only_one_coordinator(self, client):
        with patch("adclaw.app.routers.personas.load_config") as mock_load, \
             patch("adclaw.app.routers.personas.save_config"):
            mock_load.return_value = Config(agents=AgentsConfig(
                personas=[PersonaConfig(id="a", name="A", is_coordinator=True)]
            ))
            resp = client.post("/api/agents/personas", json={"id": "b", "name": "B", "is_coordinator": True})
            assert resp.status_code == 409
