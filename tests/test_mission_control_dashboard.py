"""Tests for Mission Control P2: Dashboard API data aggregation."""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch
from adclaw.config.config import Config, AgentsConfig, PersonaConfig, PersonaCronConfig


@pytest.fixture
def dashboard_client():
    from adclaw.app.routers.personas import router
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


class TestDashboardData:
    """Dashboard needs personas + model + skills + cron data."""

    def test_personas_include_model_info(self, dashboard_client, config_with_personas):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            # Add model info to researcher
            config_with_personas.agents.personas[1].model_provider = "aliyun-intl"
            config_with_personas.agents.personas[1].model_name = "qwen3.5-plus"
            mock.return_value = config_with_personas

            resp = dashboard_client.get("/api/agents/personas")
            assert resp.status_code == 200
            personas = resp.json()
            researcher = next(p for p in personas if p["id"] == "researcher")
            assert researcher["model_provider"] == "aliyun-intl"
            assert researcher["model_name"] == "qwen3.5-plus"

    def test_personas_include_skills_count(self, dashboard_client, config_with_personas):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            config_with_personas.agents.personas[1].skills = ["citedy-trend-scout", "exa-search"]
            mock.return_value = config_with_personas

            resp = dashboard_client.get("/api/agents/personas")
            personas = resp.json()
            researcher = next(p for p in personas if p["id"] == "researcher")
            assert len(researcher["skills"]) == 2

    def test_personas_include_cron_config(self, dashboard_client, config_with_personas):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            config_with_personas.agents.personas[1].cron = PersonaCronConfig(
                enabled=True,
                schedule="0 9 * * *",
                prompt="Find AI trends today",
                output="chat",
            )
            mock.return_value = config_with_personas

            resp = dashboard_client.get("/api/agents/personas")
            personas = resp.json()
            researcher = next(p for p in personas if p["id"] == "researcher")
            assert researcher["cron"]["enabled"] is True
            assert researcher["cron"]["schedule"] == "0 9 * * *"

    def test_coordinator_marked(self, dashboard_client, config_with_personas):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = config_with_personas
            resp = dashboard_client.get("/api/agents/personas")
            personas = resp.json()
            coord = next(p for p in personas if p["is_coordinator"])
            assert coord["id"] == "coordinator"


class TestDashboardFiltering:
    """Dashboard should support filtering by persona properties."""

    def test_list_returns_all_personas(self, dashboard_client, config_with_personas):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = config_with_personas
            resp = dashboard_client.get("/api/agents/personas")
            assert len(resp.json()) == 3

    def test_get_single_persona_by_id(self, dashboard_client, config_with_personas):
        with patch("adclaw.app.routers.personas.load_config") as mock:
            mock.return_value = config_with_personas
            resp = dashboard_client.get("/api/agents/personas/researcher")
            assert resp.status_code == 200
            assert resp.json()["name"] == "Mike"
