# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adclaw.app.routers.diagnostics import router


@pytest.fixture
def mock_app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.runner = MagicMock()
    app.state.runner.memory_manager = MagicMock()
    app.state.runner.memory_manager.close = AsyncMock()
    app.state.runner.init_handler = AsyncMock()
    app.state.channel_manager = MagicMock()
    app.state.channel_manager.channels = []
    app.state.mcp_manager = MagicMock()
    app.state.mcp_manager._clients = {}
    app.state.cron_manager = MagicMock()
    app.state.cron_manager._scheduler = MagicMock()
    app.state.cron_manager._scheduler.get_jobs.return_value = []
    app.state.aom_manager = None
    app.state.config_watcher = MagicMock()
    return app


@pytest.fixture
def client(mock_app):
    return TestClient(mock_app)


def _mock_providers_data(has_llm=True):
    data = MagicMock()
    data.active_llm.provider_id = "test-provider" if has_llm else ""
    data.active_llm.model = "test-model" if has_llm else ""
    return data


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        with patch(
            "adclaw.app.routers.diagnostics.load_providers_json",
            return_value=_mock_providers_data(has_llm=True),
        ):
            resp = client.get("/api/diagnostics/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "uptime_seconds" in body
        assert "subsystems" in body
        assert isinstance(body["uptime_seconds"], (int, float))
        assert body["uptime_seconds"] >= 0

    def test_health_subsystems_structure(self, client):
        with patch(
            "adclaw.app.routers.diagnostics.load_providers_json",
            return_value=_mock_providers_data(has_llm=True),
        ):
            resp = client.get("/api/diagnostics/health")
        subs = resp.json()["subsystems"]
        for key in ("llm", "channels", "mcp", "crons"):
            assert key in subs, f"Missing subsystem key: {key}"
            assert "status" in subs[key]

    def test_health_no_channels(self, client, mock_app):
        mock_app.state.channel_manager.channels = []
        with patch(
            "adclaw.app.routers.diagnostics.load_providers_json",
            return_value=_mock_providers_data(has_llm=True),
        ):
            resp = client.get("/api/diagnostics/health")
        body = resp.json()
        assert body["subsystems"]["channels"]["status"] == "warning"


class TestErrorsEndpoint:
    def test_errors_endpoint(self, client):
        with patch(
            "adclaw.app.routers.diagnostics._ERROR_LOG"
        ) as mock_log:
            mock_log.exists.return_value = False
            resp = client.get("/api/diagnostics/errors")
        assert resp.status_code == 200
        body = resp.json()
        assert "errors" in body
        assert isinstance(body["errors"], list)

    def test_errors_with_limit(self, client):
        log_lines = []
        for i in range(10):
            log_lines.append(
                f"ERROR foo | 2026-01-0{i % 9 + 1} 12:00:00 | error message {i}"
            )
        with patch(
            "adclaw.app.routers.diagnostics._ERROR_LOG"
        ) as mock_log:
            mock_log.exists.return_value = True
            mock_log.read_text.return_value = "\n".join(log_lines)
            resp = client.get("/api/diagnostics/errors?limit=3")
        body = resp.json()
        assert len(body["errors"]) == 3
        assert body["total"] == 10


class TestRestartEndpoint:
    def test_restart_endpoint(self, client):
        resp = client.post("/api/diagnostics/restart")
        assert resp.status_code == 200
        body = resp.json()
        assert "restarted" in body
        assert body["restarted"] is True

    def test_restart_failure(self, client, mock_app):
        mock_app.state.runner.init_handler = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        resp = client.post("/api/diagnostics/restart")
        body = resp.json()
        assert body["restarted"] is False
        assert "boom" in body["error"]
