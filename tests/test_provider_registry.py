from adclaw.providers.registry import get_provider, list_providers


def test_xiaomi_provider_registered():
    provider = get_provider("xiaomi-codingplan")

    assert provider is not None
    assert provider.name == "Xiaomi MiMo Token Plan"
    assert provider.default_base_url == "https://token-plan-ams.xiaomimimo.com/v1"
    assert [model.id for model in provider.models] == [
        "mimo-v2.5",
        "mimo-v2.5-pro",
        "mimo-v2-omni",
    ]


def test_xiaomi_provider_sorted_first():
    providers = list_providers()

    assert providers[0].id == "xiaomi-codingplan"
