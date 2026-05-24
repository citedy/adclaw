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


def test_strip_reasoning_blocks_drops_thinking_only_messages():
    from adclaw.agents.model_factory import _strip_reasoning_blocks

    thinking_only = SimpleNamespace(
        content=[{"type": "thinking", "thinking": "private chain"}],
    )
    mixed = SimpleNamespace(
        content=[
            {"type": "thinking", "thinking": "private chain"},
            {"type": "text", "text": "visible answer"},
        ],
    )

    messages = _strip_reasoning_blocks([thinking_only, mixed])

    assert messages == [mixed]
    assert mixed.content == [{"type": "text", "text": "visible answer"}]


def test_strip_bare_tool_call_text_messages_drops_json_only_assistant():
    from adclaw.agents.model_factory import _strip_bare_tool_call_text_messages

    raw_tool = SimpleNamespace(
        role="assistant",
        content='{"name":"agent.status","arguments":{}}',
    )
    normal_json = SimpleNamespace(
        role="assistant",
        content='{"campaign":"CEDAR-17"}',
    )
    user_msg = SimpleNamespace(
        role="user",
        content='{"name":"agent.status","arguments":{}}',
    )

    messages = _strip_bare_tool_call_text_messages(
        [raw_tool, normal_json, user_msg],
    )

    assert messages == [normal_json, user_msg]


def test_bare_tool_call_detector_accepts_json_string_arguments():
    from adclaw.agents.model_factory import is_bare_tool_call_json_text

    assert is_bare_tool_call_json_text(
        '{"name":"agent.status","arguments":"{\\"verbose\\":false}"}',
    )


def test_normalize_assistant_tool_call_content_replaces_null():
    from adclaw.agents.model_factory import (
        _normalize_assistant_tool_call_content,
    )

    messages = [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
        {"role": "assistant", "content": None},
    ]

    _normalize_assistant_tool_call_content(messages)

    assert messages[0]["content"] == ""
    assert messages[1]["content"] is None


def test_host_ai_remote_model_gets_safe_max_tokens(monkeypatch):
    from adclaw.agents.model_factory import _create_remote_model_instance

    class FakeChatModel:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

    monkeypatch.delenv("ADCLAW_HOST_AI_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("ADCLAW_HOST_AI_MAX_TOKENS", raising=False)
    llm_cfg = SimpleNamespace(
        provider_id="adclaw-host-ai",
        model="@cf/google/gemma-4-26b-a4b-it",
        api_key="ach_test",
        base_url="https://real.adclaw.app/api/host-ai/v1",
    )

    model = _create_remote_model_instance(llm_cfg, FakeChatModel)

    assert model.kwargs["generate_kwargs"] == {"max_tokens": 4096}
    assert "reasoning_effort" not in model.kwargs


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
    assert "reasoning_effort" not in model.kwargs


def test_host_ai_gpt_oss_uses_low_reasoning_effort(monkeypatch):
    from agentscope.model import OpenAIChatModel

    from adclaw.agents.model_factory import _create_remote_model_instance

    class FakeOpenAIChatModel(OpenAIChatModel):
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

    monkeypatch.delenv("ADCLAW_HOST_AI_REASONING_EFFORT", raising=False)
    llm_cfg = SimpleNamespace(
        provider_id="adclaw-host-ai",
        model="@cf/openai/gpt-oss-20b",
        api_key="ach_test",
        base_url="https://real.adclaw.app/api/host-ai/v1",
    )

    model = _create_remote_model_instance(llm_cfg, FakeOpenAIChatModel)

    assert model.kwargs["reasoning_effort"] == "low"


def test_host_ai_gpt_oss_reasoning_effort_can_be_disabled(monkeypatch):
    from agentscope.model import OpenAIChatModel

    from adclaw.agents.model_factory import _create_remote_model_instance

    class FakeOpenAIChatModel(OpenAIChatModel):
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

    monkeypatch.setenv("ADCLAW_HOST_AI_REASONING_EFFORT", "off")
    llm_cfg = SimpleNamespace(
        provider_id="adclaw-host-ai",
        model="@cf/openai/gpt-oss-20b",
        api_key="ach_test",
        base_url="https://real.adclaw.app/api/host-ai/v1",
    )

    model = _create_remote_model_instance(llm_cfg, FakeOpenAIChatModel)

    assert "reasoning_effort" not in model.kwargs


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
    assert "reasoning_effort" not in model.kwargs


def test_tool_result_string_is_truncated_for_host_ai_context(monkeypatch):
    from adclaw.agents.model_factory import _create_file_block_support_formatter

    class FakeFormatter:
        @staticmethod
        def convert_tool_result_to_string(output):
            return str(output), []

    monkeypatch.setenv("ADCLAW_HOST_AI_ENABLED", "true")
    monkeypatch.setenv("ADCLAW_LLM_TOOL_RESULT_MAX_CHARS", "160")
    formatter = _create_file_block_support_formatter(FakeFormatter)
    raw = "A" * 200 + "TAIL"

    text, data = formatter.convert_tool_result_to_string(raw)

    assert data == []
    assert len(text) <= 160
    assert text.startswith("A")
    assert text.endswith("TAIL")
    assert "tool result truncated from 204 to 160 chars" in text


def test_parent_tool_result_conversion_is_truncated(monkeypatch):
    from adclaw.agents.model_factory import _create_file_block_support_formatter

    class FakeFormatter:
        @staticmethod
        def convert_tool_result_to_string(output):
            return "B" * 220 + "END", [("file.txt", {"type": "file"})]

    monkeypatch.setenv("ADCLAW_HOST_AI_ENABLED", "true")
    monkeypatch.setenv("ADCLAW_LLM_TOOL_RESULT_MAX_CHARS", "180")
    formatter = _create_file_block_support_formatter(FakeFormatter)

    text, data = formatter.convert_tool_result_to_string([{"type": "text"}])

    assert data == [("file.txt", {"type": "file"})]
    assert len(text) <= 180
    assert text.endswith("END")
    assert "tool result truncated from 223 to 180 chars" in text


def test_tool_result_string_is_not_truncated_for_byo_provider(monkeypatch):
    from adclaw.agents.model_factory import _create_file_block_support_formatter

    class FakeFormatter:
        @staticmethod
        def convert_tool_result_to_string(output):
            return str(output), []

    monkeypatch.delenv("ADCLAW_HOST_AI_ENABLED", raising=False)
    monkeypatch.delenv("ADCLAW_HOST_AI_BASE_URL", raising=False)
    monkeypatch.setenv("ADCLAW_LLM_TOOL_RESULT_MAX_CHARS", "160")
    formatter = _create_file_block_support_formatter(FakeFormatter)
    raw = "A" * 200 + "TAIL"

    text, data = formatter.convert_tool_result_to_string(raw)

    assert data == []
    assert text == raw


def test_file_block_fallback_tool_result_is_truncated(monkeypatch):
    from adclaw.agents.model_factory import _create_file_block_support_formatter

    class FakeFormatter:
        @staticmethod
        def convert_tool_result_to_string(output):
            raise ValueError("Unsupported block type: file")

    monkeypatch.setenv("ADCLAW_HOST_AI_ENABLED", "true")
    monkeypatch.setenv("ADCLAW_LLM_TOOL_RESULT_MAX_CHARS", "220")
    formatter = _create_file_block_support_formatter(FakeFormatter)
    long_name = "deck-" + ("X" * 260) + ".pptx"
    block = {"type": "file", "name": long_name, "path": "/tmp/deck.pptx"}

    text, data = formatter.convert_tool_result_to_string([block])

    assert data == [("/tmp/deck.pptx", block)]
    assert len(text) <= 220
    assert "tool result truncated" in text
    assert "/tmp/deck.pptx" in text
