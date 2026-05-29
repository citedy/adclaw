from adclaw.providers.registry import get_provider, list_providers


def test_xiaomi_provider_registered():
    provider = get_provider("xiaomi-codingplan")

    assert provider is not None
    assert provider.name == "Xiaomi"
    assert provider.default_base_url == "https://token-plan-ams.xiaomimimo.com/v1"
    assert [model.id for model in provider.models] == [
        "mimo-v2.5",
        "mimo-v2.5-pro",
        "mimo-v2-omni",
    ]


def test_xiaomi_provider_sorted_first():
    providers = list_providers()

    assert providers[0].id == "xiaomi-codingplan"


def test_xai_provider_uses_current_text_chat_models():
    provider = get_provider("xai")

    assert provider is not None
    assert [model.id for model in provider.models] == [
        "grok-4.3",
        "grok-4.20-reasoning",
        "grok-4.20-non-reasoning",
    ]
