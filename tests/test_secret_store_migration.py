# -*- coding: utf-8 -*-
import json

from adclaw.envs import store as env_store
from adclaw.providers import store as provider_store


def _write_json(path, payload):
    """Write a JSON fixture to a test path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_provider_migration_merges_legacy_secret_once(tmp_path, monkeypatch):
    """Merge legacy provider secrets once and do not resurrect cleared keys."""
    target = tmp_path / "working.secret" / "providers.json"
    legacy = tmp_path / "working" / ".secret" / "providers.json"

    _write_json(
        target,
        {
            "providers": {
                "aliyun-intl": {
                    "base_url": "https://coding-intl.dashscope.aliyuncs.com/v1",
                    "api_key": "",
                    "extra_models": [],
                    "chat_model": "",
                },
            },
            "custom_providers": {},
            "active_llm": {"provider_id": "", "model": ""},
            "fallback": {"enabled": False, "timeout_seconds": 30, "chain": []},
        },
    )
    _write_json(
        legacy,
        {
            "providers": {
                "aliyun-intl": {
                    "base_url": "https://coding-intl.dashscope.aliyuncs.com/v1",
                    "api_key": "legacy-key",
                    "extra_models": [],
                    "chat_model": "",
                },
            },
            "custom_providers": {},
            "active_llm": {
                "provider_id": "aliyun-intl",
                "model": "qwen3.5-plus",
            },
            "fallback": {
                "enabled": True,
                "timeout_seconds": 45,
                "chain": [{"provider_id": "xai", "model": "grok-4.3"}],
            },
        },
    )

    monkeypatch.setattr(provider_store, "_PROVIDERS_JSON", target)
    monkeypatch.setattr(
        provider_store,
        "_LEGACY_PROVIDERS_JSON_CANDIDATES",
        (legacy,),
    )

    data = provider_store.load_providers_json()

    assert data.providers["aliyun-intl"].api_key == "legacy-key"
    assert data.active_llm.provider_id == "aliyun-intl"
    assert data.active_llm.model == "qwen3.5-plus"
    assert data.fallback.enabled is True
    assert data.fallback.chain[0].provider_id == "xai"
    assert target.with_name(".providers-legacy-migrated").exists()

    data.providers["aliyun-intl"].api_key = ""
    provider_store.save_providers_json(data)

    reloaded = provider_store.load_providers_json()
    assert reloaded.providers["aliyun-intl"].api_key == ""


def test_provider_migration_checks_all_legacy_sources_before_marker(
    tmp_path,
    monkeypatch,
):
    """Skip invalid/empty provider sources before writing migration marker."""
    target = tmp_path / "working.secret" / "providers.json"
    bad_legacy = tmp_path / "working" / "providers.json"
    empty_legacy = tmp_path / "pkg" / "providers.json"
    good_legacy = tmp_path / "working" / ".secret" / "providers.json"

    _write_json(
        target,
        {
            "providers": {"aliyun-intl": {"api_key": ""}},
            "custom_providers": {},
            "active_llm": {"provider_id": "", "model": ""},
            "fallback": {"enabled": False, "timeout_seconds": 30, "chain": []},
        },
    )
    bad_legacy.parent.mkdir(parents=True, exist_ok=True)
    bad_legacy.write_text("{", encoding="utf-8")
    _write_json(
        empty_legacy,
        {
            "providers": {"aliyun-intl": {"api_key": ""}},
            "custom_providers": {},
            "active_llm": {"provider_id": "", "model": ""},
            "fallback": {"enabled": False, "timeout_seconds": 30, "chain": []},
        },
    )
    _write_json(
        good_legacy,
        {
            "providers": {"aliyun-intl": {"api_key": "legacy-key"}},
            "custom_providers": {},
            "active_llm": {"provider_id": "aliyun-intl", "model": "qwen3.5-plus"},
            "fallback": {"enabled": False, "timeout_seconds": 30, "chain": []},
        },
    )

    monkeypatch.setattr(provider_store, "_PROVIDERS_JSON", target)
    monkeypatch.setattr(
        provider_store,
        "_LEGACY_PROVIDERS_JSON_CANDIDATES",
        (bad_legacy, empty_legacy, good_legacy),
    )

    data = provider_store.load_providers_json()

    assert data.providers["aliyun-intl"].api_key == "legacy-key"
    assert data.active_llm.provider_id == "aliyun-intl"
    assert target.with_name(".providers-legacy-migrated").exists()


def test_env_migration_merges_missing_legacy_keys_once(tmp_path, monkeypatch):
    """Merge legacy env keys once and do not resurrect cleared values."""
    target = tmp_path / "working.secret" / "envs.json"
    legacy = tmp_path / "working" / ".secret" / "envs.json"

    _write_json(target, {"CITEDY_API_KEY": "new"})
    _write_json(legacy, {"CITEDY_API_KEY": "old", "XAI_API_KEY": "legacy-xai"})

    monkeypatch.setattr(env_store, "_ENVS_JSON", target)
    monkeypatch.setattr(env_store, "_LEGACY_ENVS_JSON_CANDIDATES", (legacy,))

    envs = env_store.load_envs()

    assert envs == {"CITEDY_API_KEY": "new", "XAI_API_KEY": "legacy-xai"}
    assert target.with_name(".envs-legacy-migrated").exists()

    envs.pop("XAI_API_KEY")
    env_store.save_envs(envs)

    assert env_store.load_envs() == {"CITEDY_API_KEY": "new"}


def test_env_migration_checks_all_legacy_sources_before_marker(
    tmp_path,
    monkeypatch,
):
    """Skip invalid/empty env sources before writing migration marker."""
    target = tmp_path / "working.secret" / "envs.json"
    bad_legacy = tmp_path / "working" / "envs.json"
    empty_legacy = tmp_path / "pkg" / "envs.json"
    good_legacy = tmp_path / "working" / ".secret" / "envs.json"

    _write_json(target, {"CITEDY_API_KEY": "new"})
    bad_legacy.parent.mkdir(parents=True, exist_ok=True)
    bad_legacy.write_text("{", encoding="utf-8")
    _write_json(empty_legacy, {})
    _write_json(good_legacy, {"XAI_API_KEY": "legacy-xai"})

    monkeypatch.setattr(env_store, "_ENVS_JSON", target)
    monkeypatch.setattr(
        env_store,
        "_LEGACY_ENVS_JSON_CANDIDATES",
        (bad_legacy, empty_legacy, good_legacy),
    )

    envs = env_store.load_envs()

    assert envs == {"CITEDY_API_KEY": "new", "XAI_API_KEY": "legacy-xai"}
    assert target.with_name(".envs-legacy-migrated").exists()
