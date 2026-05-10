# -*- coding: utf-8 -*-
# pylint: disable=too-many-return-statements
"""
Bridge between channels and AgentApp process: factory to build
ProcessHandler from runner. Shared helpers for channels (e.g. file URL).
"""
from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.request import url2pathname

from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    TextContent,
)

_MEDIA_REFERENCE_FIELDS = {
    "image": "image_url",
    "video": "video_url",
    "audio": "data",
    "file": "file_url",
}

_MEDIA_LABELS = {
    "image": "image",
    "video": "video",
    "audio": "audio",
    "file": "file",
}


def file_url_to_local_path(url: str) -> Optional[str]:
    """Convert file:// URL or plain local path to local path string.

    Supports:
    - file:// URL (all platforms): file:///path, file://D:/path,
      file://D:\\path (Windows two-slash).
    - Plain local path: D:\\path, /tmp/foo (no scheme). Pass-through after
      stripping whitespace; no existence check (caller may use Path().exists).

    Returns None only when url is clearly not a local file (e.g. http(s) URL)
    or file URL could not be resolved to a non-empty path.
    """
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    parsed = urlparse(s)
    if parsed.scheme == "file":
        path = url2pathname(parsed.path)
        if not path and parsed.netloc:
            path = url2pathname(parsed.netloc.replace("\\", "/"))
        elif (
            path
            and parsed.netloc
            and len(parsed.netloc) == 1
            and os.name == "nt"
        ):
            path = f"{parsed.netloc}:{path}"
        return path if path else None
    if parsed.scheme in ("http", "https"):
        return None
    if not parsed.scheme:
        return s
    if (
        os.name == "nt"
        and len(parsed.scheme) == 1
        and parsed.path.startswith("\\")
    ):
        return s
    return None


def is_local_media_reference(value: Any) -> bool:
    """True when value points to local or embedded media, not the network."""
    if not isinstance(value, str):
        return False
    ref = value.strip()
    if not ref:
        return False
    if ref.startswith("data:"):
        return True
    return file_url_to_local_path(ref) is not None


def _content_type_key(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _part_field_value(part: Any, field_name: str) -> Optional[str]:
    if isinstance(part, dict):
        value = part.get(field_name)
    else:
        value = getattr(part, field_name, None)
    return value if isinstance(value, str) else None


def _blocked_media_notice(part_type: str) -> TextContent:
    label = _MEDIA_LABELS.get(part_type, "media")
    return TextContent(
        type=ContentType.TEXT,
        text=(
            f"[Security notice: remote {label} URL was blocked. "
            "Please upload the file directly in this channel instead.]"
        ),
    )


def sanitize_inbound_media_content_parts(
    content_parts: list[Any],
) -> tuple[list[Any], bool]:
    """
    Replace inbound remote media references with an explicit warning.

    Channels should pass only local paths, file:// URLs, or data: URLs to
    AgentScope. Any network-backed media reference is blocked here.
    """
    sanitized: list[Any] = []
    changed = False
    for part in content_parts:
        part_type = _content_type_key(
            part.get("type") if isinstance(part, dict) else getattr(
                part,
                "type",
                None,
            ),
        )
        field_name = _MEDIA_REFERENCE_FIELDS.get(part_type)
        if not field_name:
            sanitized.append(part)
            continue
        ref = _part_field_value(part, field_name)
        if ref and not is_local_media_reference(ref):
            sanitized.append(_blocked_media_notice(part_type))
            changed = True
            continue
        sanitized.append(part)
    return sanitized, changed


def sanitize_agent_request_media(request: Any) -> Any:
    """Sanitize any inbound media refs already wrapped in AgentRequest."""
    messages = list(getattr(request, "input", None) or [])
    if not messages:
        return request

    changed = False
    sanitized_messages = []
    for message in messages:
        content_parts = list(getattr(message, "content", None) or [])
        sanitized_parts, content_changed = (
            sanitize_inbound_media_content_parts(content_parts)
        )
        if content_changed and hasattr(message, "model_copy"):
            sanitized_messages.append(
                message.model_copy(update={"content": sanitized_parts}),
            )
            changed = True
            continue
        if content_changed:
            message.content = sanitized_parts
            changed = True
        sanitized_messages.append(message)

    if not changed:
        return request
    if hasattr(request, "model_copy"):
        return request.model_copy(update={"input": sanitized_messages})
    request.input = sanitized_messages
    return request


def make_process_from_runner(runner: Any):
    """
    Use runner.stream_query as the channel's process.

    Each channel does: native -> build_agent_request_from_native()
        -> process(request) -> send on each completed message.
    process is runner.stream_query, same as AgentApp's /process endpoint.

    Usage::
        process = make_process_from_runner(runner)
        manager = ChannelManager.from_env(process)
    """
    return runner.stream_query
