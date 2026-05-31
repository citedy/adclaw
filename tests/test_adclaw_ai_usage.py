# -*- coding: utf-8 -*-
"""Tests for AdClaw AI usage visibility in hosted sandboxes."""

import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException

from adclaw.app.routers import providers as provider_routes
from adclaw.providers.models import CustomProviderData, ModelInfo, ProvidersData
from adclaw.providers.store import (
    ProviderUsageRequestError,
    fetch_provider_usage,
    read_providers_json,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return BytesIO(self._body).read()


def _host_ai_data(api_key: str = "ach_real_secret") -> ProvidersData:
    return ProvidersData(
        custom_providers={
            "adclaw-host-ai": CustomProviderData(
                id="adclaw-host-ai",
                name="AdClaw AI",
                default_base_url="https://real.adclaw.app/api/host-ai/v1",
                base_url="https://real.adclaw.app/api/host-ai/v1",
                api_key=api_key,
                models=[
                    ModelInfo(
                        id="@cf/meta/llama-3.1-8b-instruct-fp8-fast",
                        name="Fast default",
                    ),
                ],
            ),
        },
    )


def test_fetch_provider_usage_uses_secret_and_usage_endpoint():
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "provider_id": "adclaw-host-ai",
                "provider_name": "AdClaw AI",
                "messages_limit": 1500,
                "messages_used": 17,
                "messages_remaining": 1483,
            },
        )

    payload = fetch_provider_usage(
        "adclaw-host-ai",
        data=_host_ai_data(),
        urlopen_fn=fake_urlopen,
    )

    assert captured == {
        "url": "https://real.adclaw.app/api/host-ai/v1/usage",
        "authorization": "Bearer ach_real_secret",
        "timeout": 5.0,
    }
    assert payload["messages_remaining"] == 1483
    assert payload["messages_limit"] == 1500


def test_fetch_provider_usage_requires_configured_secret():
    with pytest.raises(ValueError, match="API key"):
        fetch_provider_usage(
            "adclaw-host-ai",
            data=_host_ai_data(api_key=""),
            urlopen_fn=lambda *_args, **_kwargs: None,
        )


def test_fetch_provider_usage_translates_network_failures():
    def failing_urlopen(*_args, **_kwargs):
        raise OSError("connection refused")

    with pytest.raises(ProviderUsageRequestError, match="usage request failed"):
        fetch_provider_usage(
            "adclaw-host-ai",
            data=_host_ai_data(),
            urlopen_fn=failing_urlopen,
        )


def test_fetch_provider_usage_rejects_redirect_responses():
    class RedirectResponse:
        status = 302

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            raise AssertionError("redirect response body should not be read")

    with pytest.raises(ProviderUsageRequestError, match="302"):
        fetch_provider_usage(
            "adclaw-host-ai",
            data=_host_ai_data(),
            urlopen_fn=lambda *_args, **_kwargs: RedirectResponse(),
        )


def test_fetch_provider_usage_rejects_host_ai_token_on_unmanaged_origin():
    data = _host_ai_data()
    data.custom_providers["adclaw-host-ai"].base_url = (
        "https://evil.example/api/host-ai/v1"
    )

    def unexpected_urlopen(*_args, **_kwargs):
        raise AssertionError("Host AI token must not be sent to unmanaged origin")

    with pytest.raises(ValueError, match="managed AdClaw AI endpoint"):
        fetch_provider_usage(
            "adclaw-host-ai",
            data=data,
            urlopen_fn=unexpected_urlopen,
        )


def test_read_providers_json_does_not_rewrite_provider_file(tmp_path):
    providers_path = tmp_path / "providers.json"
    payload = {
        "providers": {},
        "custom_providers": {
            "adclaw-host-ai": _host_ai_data()
            .custom_providers["adclaw-host-ai"]
            .model_dump(mode="json"),
        },
        "active_llm": {
            "provider_id": "adclaw-host-ai",
            "model": "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
        },
        "fallback": {"enabled": False, "timeout_seconds": 30, "chain": []},
    }
    original = json.dumps(payload, indent=2)
    providers_path.write_text(original, encoding="utf-8")

    data = read_providers_json(providers_path)

    assert data.custom_providers["adclaw-host-ai"].api_key == "ach_real_secret"
    assert providers_path.read_text(encoding="utf-8") == original


def test_provider_usage_route_passes_readonly_provider_data(monkeypatch):
    marker = _host_ai_data()
    captured = {}

    def fake_fetch(provider_id, *, data=None):
        captured["provider_id"] = provider_id
        captured["data"] = data
        return {
            "provider_id": "adclaw-host-ai",
            "messages_limit": 1500,
            "messages_used": 10,
            "messages_remaining": 1490,
        }

    monkeypatch.setattr(provider_routes, "read_providers_json", lambda: marker)
    monkeypatch.setattr(provider_routes, "fetch_provider_usage", fake_fetch)

    response = provider_routes.get_provider_usage("adclaw-host-ai")

    assert response.provider_id == "adclaw-host-ai"
    assert captured == {"provider_id": "adclaw-host-ai", "data": marker}


def test_provider_usage_route_maps_upstream_failures_to_bad_gateway(monkeypatch):
    monkeypatch.setattr(provider_routes, "read_providers_json", _host_ai_data)

    def failing_fetch(*_args, **_kwargs):
        raise ProviderUsageRequestError("Provider 'adclaw-host-ai' usage request failed.")

    monkeypatch.setattr(provider_routes, "fetch_provider_usage", failing_fetch)

    with pytest.raises(HTTPException) as exc_info:
        provider_routes.get_provider_usage("adclaw-host-ai")

    assert exc_info.value.status_code == 502


def test_provider_usage_route_is_threadpool_safe_and_validation_guarded():
    source = (ROOT / "src/adclaw/app/routers/providers.py").read_text(
        encoding="utf-8",
    )

    assert "def get_provider_usage(" in source
    assert "async def get_provider_usage(" not in source
    assert "except (ValueError, ValidationError)" in source
