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
        "grok-4.5",
        "grok-4.3",
        "grok-4.20-reasoning",
        "grok-4.20-non-reasoning",
    ]


def test_openai_provider_includes_gpt_5_6_family():
    provider = get_provider("openai")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert model_ids[:3] == [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ]


def test_openrouter_provider_includes_gpt_5_6_family():
    provider = get_provider("openrouter")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert "openai/gpt-5.6-sol" in model_ids
    assert "openai/gpt-5.6-terra" in model_ids
    assert "openai/gpt-5.6-luna" in model_ids
    assert "anthropic/claude-fable-5" in model_ids
    assert "google/gemini-3.6-flash" in model_ids
    assert "moonshotai/kimi-k3" in model_ids
    assert "z-ai/glm-5.2" in model_ids
    assert "x-ai/grok-4.5" in model_ids


def test_anthropic_provider_includes_claude_5_family():
    provider = get_provider("anthropic")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert model_ids[:3] == [
        "claude-fable-5",
        "claude-opus-5",
        "claude-sonnet-5",
    ]


def test_gemini_provider_includes_3_6_flash_and_3_5_flash_lite():
    provider = get_provider("gemini")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert model_ids[:3] == [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]


def test_moonshot_provider_includes_kimi_k3_and_k2_7_code():
    provider = get_provider("moonshot")

    assert provider is not None
    assert [model.id for model in provider.models] == [
        "kimi-k3",
        "kimi-k2.7-code",
        "kimi-k2.7-code-highspeed",
        "kimi-k2.6",
    ]


def test_zai_provider_includes_glm_5_2():
    provider = get_provider("zai")

    assert provider is not None
    assert provider.models[0].id == "glm-5.2"


def test_baseten_provider_drops_deprecated_and_adds_current():
    provider = get_provider("baseten")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert "moonshotai/Kimi-K3" in model_ids
    assert "zai-org/GLM-5.2" in model_ids
    assert "deepseek-v4-pro" in model_ids
    assert "deepseek-ai/DeepSeek-V3.1" not in model_ids
    assert "MiniMaxAI/MiniMax-M2.5" not in model_ids


def test_azure_openai_includes_gpt_5_6_family():
    provider = get_provider("azure-openai")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert model_ids[:3] == [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ]


def test_aliyun_coding_plan_keeps_allowlist_and_adds_qwen37():
    """Coding Plan is an exact-string allowlist; k2.5/M2.5 still official."""
    provider = get_provider("aliyun-codingplan")

    assert provider is not None
    model_ids = [model.id for model in provider.models]
    assert "qwen3.7-plus" in model_ids
    assert "qwen3.6-plus" in model_ids
    assert "kimi-k2.5" in model_ids
    assert "MiniMax-M2.5" in model_ids
    assert "glm-5" in model_ids
