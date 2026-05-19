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
