# -*- coding: utf-8 -*-
from types import SimpleNamespace


def test_strip_missing_local_files_removes_file_blocks():
    from adclaw.agents.model_factory import _strip_missing_local_files

    msg = SimpleNamespace(
        content=[
            {"type": "text", "text": "keep"},
            {
                "type": "file",
                "file_url": "file:///home/adclaw/.adclaw/media/telegram/missing.pptx",
            },
        ],
        get_text_content=lambda: "fallback",
    )

    _strip_missing_local_files([msg])

    assert msg.content == [{"type": "text", "text": "keep"}]


def test_strip_missing_local_files_removes_nested_source_blocks():
    from adclaw.agents.model_factory import _strip_missing_local_files

    msg = SimpleNamespace(
        content=[
            {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": "file:///home/adclaw/.adclaw/media/telegram/missing.jpg",
                },
            },
        ],
        get_text_content=lambda: "",
    )

    _strip_missing_local_files([msg])

    assert msg.content == "[local file removed]"


def test_strip_missing_local_files_keeps_remote_urls():
    from adclaw.agents.model_factory import _strip_missing_local_files

    block = {
        "type": "image",
        "source": {"type": "url", "url": "https://example.com/image.jpg"},
    }
    msg = SimpleNamespace(
        content=[block],
        get_text_content=lambda: "",
    )

    _strip_missing_local_files([msg])

    assert msg.content == [block]


def test_host_ai_remote_model_gets_safe_max_tokens(monkeypatch):
    from adclaw.agents.model_factory import _create_remote_model_instance

    class FakeChatModel:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

    monkeypatch.delenv("ADCLAW_HOST_AI_MAX_TOKENS", raising=False)
    llm_cfg = SimpleNamespace(
        provider_id="adclaw-host-ai",
        model="@cf/google/gemma-4-26b-a4b-it",
        api_key="ach_test",
        base_url="https://real.adclaw.app/api/host-ai/v1",
    )

    model = _create_remote_model_instance(llm_cfg, FakeChatModel)

    assert model.kwargs["generate_kwargs"] == {"max_tokens": 768}


def test_host_ai_remote_model_uses_canonical_max_output_tokens(monkeypatch):
    from adclaw.agents.model_factory import _create_remote_model_instance

    class FakeChatModel:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

    monkeypatch.setenv("ADCLAW_HOST_AI_MAX_OUTPUT_TOKENS", "321")
    monkeypatch.setenv("ADCLAW_HOST_AI_MAX_TOKENS", "654")
    llm_cfg = SimpleNamespace(
        provider_id="adclaw-host-ai",
        model="@cf/google/gemma-4-26b-a4b-it",
        api_key="ach_test",
        base_url="https://real.adclaw.app/api/host-ai/v1",
    )

    model = _create_remote_model_instance(llm_cfg, FakeChatModel)

    assert model.kwargs["generate_kwargs"] == {"max_tokens": 321}


def test_non_host_ai_remote_model_does_not_get_host_generation_cap():
    from adclaw.agents.model_factory import _create_remote_model_instance

    class FakeChatModel:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

    llm_cfg = SimpleNamespace(
        provider_id="openai",
        model="gpt-4.1",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
    )

    model = _create_remote_model_instance(llm_cfg, FakeChatModel)

    assert "generate_kwargs" not in model.kwargs
