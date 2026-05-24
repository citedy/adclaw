# -*- coding: utf-8 -*-
"""Factory for creating chat models and formatters.

This module provides a unified factory for creating chat model instances
and their corresponding formatters based on configuration.

Example:
    >>> from adclaw.agents.model_factory import create_model_and_formatter
    >>> model, formatter = create_model_and_formatter()
"""

import logging
import os
from typing import TYPE_CHECKING, Optional, Sequence, Tuple, Type

from agentscope.formatter import FormatterBase, OpenAIChatFormatter
from agentscope.model import ChatModelBase, OpenAIChatModel

from .utils.tool_message_utils import _sanitize_tool_messages
from ..local_models import create_local_chat_model
from ..providers import (
    get_active_llm_config,
    get_chat_model_class,
    get_provider_chat_model,
    load_providers_json,
)

if TYPE_CHECKING:
    from ..providers import ResolvedModelConfig

logger = logging.getLogger(__name__)

_HOST_AI_PROVIDER_ID = "adclaw-host-ai"
_HOST_AI_DEFAULT_MAX_TOKENS = 4096
_HOST_AI_MAX_OUTPUT_TOKENS_ENV = "ADCLAW_HOST_AI_MAX_OUTPUT_TOKENS"
_HOST_AI_LEGACY_MAX_TOKENS_ENV = "ADCLAW_HOST_AI_MAX_TOKENS"
_LLM_TOOL_RESULT_MAX_CHARS_ENV = "ADCLAW_LLM_TOOL_RESULT_MAX_CHARS"
_LLM_TOOL_RESULT_DEFAULT_MAX_CHARS = 6000
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


_LOCAL_FILE_URL_FIELDS = (
    "image_url",
    "file_url",
    "video_url",
    "audio_url",
    "url",
)


def _is_missing_local_file_url(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("file://"):
        return False
    raw = url.removeprefix("file://")
    return bool(raw) and not os.path.isfile(raw)


def _block_missing_local_file_url(block) -> str:
    """Return the missing file:// URL referenced by a content block."""
    for field in _LOCAL_FILE_URL_FIELDS:
        url = getattr(block, field, None)
        if _is_missing_local_file_url(url):
            return url

    if isinstance(block, dict):
        for field in _LOCAL_FILE_URL_FIELDS:
            url = block.get(field)
            if _is_missing_local_file_url(url):
                return url

        source = block.get("source")
        if isinstance(source, dict):
            url = source.get("url")
            if _is_missing_local_file_url(url):
                return url

    return ""


def _strip_missing_local_files(msgs):
    """Remove content blocks that reference missing local files.

    Agentscope's formatter crashes with ValueError when a local image
    file no longer exists, and some OpenAI-compatible providers reject
    stale local file blocks with BadRequest errors. This strips those
    blocks so formatting can proceed after container/runtime changes.
    """
    for msg in msgs:
        content = getattr(msg, "content", None)
        if not isinstance(content, list):
            continue
        cleaned = []
        for block in content:
            missing_url = _block_missing_local_file_url(block)
            if missing_url:
                logger.warning(
                    "Dropping missing local file from message: %s",
                    missing_url,
                )
                continue
            cleaned.append(block)
        if len(cleaned) != len(content):
            msg.content = (
                cleaned
                if cleaned
                else (msg.get_text_content() or "[local file removed]")
            )
    return msgs


def _env_positive_int(name: str, default: int) -> int:
    """Return a positive integer env value, or a safe default."""
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, value, default)
        return default
    if parsed <= 0:
        logger.warning("Invalid %s=%r; using %d", name, value, default)
        return default
    return parsed


def _host_ai_generate_kwargs(provider_id: str) -> dict:
    """Apply bounded generation for managed Host AI only.

    Hosted onboarding should be fast and predictable. Without an output cap,
    some OpenAI-compatible Workers AI streams can spend tens of seconds on
    hidden reasoning before producing a short visible answer.
    """
    if provider_id != _HOST_AI_PROVIDER_ID:
        return {}
    env_name = (
        _HOST_AI_MAX_OUTPUT_TOKENS_ENV
        if os.getenv(_HOST_AI_MAX_OUTPUT_TOKENS_ENV)
        else _HOST_AI_LEGACY_MAX_TOKENS_ENV
    )
    return {
        "max_tokens": _env_positive_int(
            env_name,
            _HOST_AI_DEFAULT_MAX_TOKENS,
        ),
    }


def _host_ai_tool_result_truncation_enabled() -> bool:
    """Return true only for managed Host AI contexts."""
    if os.getenv("ADCLAW_HOST_AI_TOOL_RESULT_TRUNCATION", "").lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    if os.getenv("ADCLAW_HOST_AI_ENABLED", "").lower() in _TRUTHY_ENV_VALUES:
        return True
    return os.getenv("ADCLAW_HOST_AI_BASE_URL", "").strip() != ""


def _truncate_llm_tool_result_text(text: str) -> str:
    """Cap Host AI tool-result text before it feeds the next LLM call."""
    if not _host_ai_tool_result_truncation_enabled():
        return text
    max_chars = _env_positive_int(
        _LLM_TOOL_RESULT_MAX_CHARS_ENV,
        _LLM_TOOL_RESULT_DEFAULT_MAX_CHARS,
    )
    if len(text) <= max_chars:
        return text

    marker = (
        f"\n\n[adclaw: tool result truncated from {len(text)} to "
        f"{max_chars} chars before LLM context; retained head/tail]\n\n"
    )
    if max_chars <= len(marker) + 20:
        return text[:max_chars]

    budget = max_chars - len(marker)
    head_len = max(1, int(budget * 0.7))
    tail_len = max(1, budget - head_len)
    return f"{text[:head_len]}{marker}{text[-tail_len:]}"


def _strip_missing_images(msgs):
    """Backward-compatible alias for older tests/imports."""
    return _strip_missing_local_files(msgs)


# Mapping from chat model class to formatter class
_CHAT_MODEL_FORMATTER_MAP: dict[Type[ChatModelBase], Type[FormatterBase]] = {
    OpenAIChatModel: OpenAIChatFormatter,
}


def _get_formatter_for_chat_model(
    chat_model_class: Type[ChatModelBase],
) -> Type[FormatterBase]:
    """Get the appropriate formatter class for a chat model.

    Args:
        chat_model_class: The chat model class

    Returns:
        Corresponding formatter class, defaults to OpenAIChatFormatter
    """
    return _CHAT_MODEL_FORMATTER_MAP.get(
        chat_model_class,
        OpenAIChatFormatter,
    )


def _create_file_block_support_formatter(
    base_formatter_class: Type[FormatterBase],
) -> Type[FormatterBase]:
    """Create a formatter class with file block support.

    This factory function extends any Formatter class to support file blocks
    in tool results, which are not natively supported by AgentScope.

    Args:
        base_formatter_class: Base formatter class to extend

    Returns:
        Enhanced formatter class with file block support
    """

    class FileBlockSupportFormatter(base_formatter_class):
        """Formatter with file block support for tool results."""

        async def _format(self, msgs):
            """Override to sanitize tool messages before formatting.

            This prevents OpenAI API errors from improperly paired
            tool messages and removes references to missing local files.
            """
            msgs = _sanitize_tool_messages(msgs)
            msgs = _strip_missing_local_files(msgs)
            messages = await super()._format(msgs)
            return _strip_top_level_message_name(messages)

        @staticmethod
        def convert_tool_result_to_string(
            output: str | list[dict],
        ) -> tuple[str, Sequence[Tuple[str, dict]]]:
            """Extend parent class to support file blocks.

            Uses try-first strategy for compatibility with parent class.

            Args:
                output: Tool result output (string or list of blocks)

            Returns:
                Tuple of (text_representation, multimodal_data)
            """
            if isinstance(output, str):
                return _truncate_llm_tool_result_text(output), []

            # Try parent class method first
            try:
                text, data = base_formatter_class.convert_tool_result_to_string(
                    output,
                )
                return _truncate_llm_tool_result_text(text), data
            except ValueError as e:
                if "Unsupported block type: file" not in str(e):
                    raise

                # Handle output containing file blocks
                textual_output = []
                multimodal_data = []

                for block in output:
                    if not isinstance(block, dict) or "type" not in block:
                        raise ValueError(
                            f"Invalid block: {block}, "
                            "expected a dict with 'type' key",
                        ) from e

                    if block["type"] == "file":
                        file_path = block.get("path", "") or block.get(
                            "url",
                            "",
                        )
                        file_name = block.get("name", file_path)

                        textual_output.append(
                            f"The returned file '{file_name}' "
                            f"can be found at: {file_path}",
                        )
                        multimodal_data.append((file_path, block))
                    else:
                        # Delegate other block types to parent class
                        (
                            text,
                            data,
                        ) = base_formatter_class.convert_tool_result_to_string(
                            [block],
                        )
                        textual_output.append(text)
                        multimodal_data.extend(data)

                if len(textual_output) == 0:
                    return "", multimodal_data
                elif len(textual_output) == 1:
                    return (
                        _truncate_llm_tool_result_text(textual_output[0]),
                        multimodal_data,
                    )
                else:
                    return (
                        _truncate_llm_tool_result_text(
                            "\n".join("- " + _ for _ in textual_output),
                        ),
                        multimodal_data,
                    )

    FileBlockSupportFormatter.__name__ = (
        f"FileBlockSupport{base_formatter_class.__name__}"
    )
    return FileBlockSupportFormatter


def _strip_top_level_message_name(
    messages: list[dict],
) -> list[dict]:
    """Strip top-level `name` from OpenAI chat messages.

    Some strict OpenAI-compatible backends reject `messages[*].name`
    (especially for assistant/tool roles) and may return 500/400 on
    follow-up turns. Keep function/tool names unchanged.
    """
    for message in messages:
        message.pop("name", None)
    return messages


def create_model_and_formatter(
    llm_cfg: Optional["ResolvedModelConfig"] = None,
    timeout_seconds: Optional[int] = None,
) -> Tuple[ChatModelBase, FormatterBase]:
    """Factory method to create model and formatter instances.

    Args:
        llm_cfg: Resolved model configuration. If None, will call
            get_active_llm_config() to fetch the active configuration.
        timeout_seconds: Optional timeout for the OpenAI client.
            If None, no explicit timeout is set (SDK default).

    Returns:
        Tuple of (model_instance, formatter_instance)
    """
    # Fetch config if not provided
    if llm_cfg is None:
        llm_cfg = get_active_llm_config()

    # Create the model instance and determine chat model class
    model, chat_model_class = _create_model_instance(
        llm_cfg, timeout_seconds=timeout_seconds,
    )

    # Create the formatter based on chat_model_class
    formatter = _create_formatter_instance(chat_model_class)

    return model, formatter


def _create_model_instance(
    llm_cfg: Optional["ResolvedModelConfig"],
    timeout_seconds: Optional[int] = None,
) -> Tuple[ChatModelBase, Type[ChatModelBase]]:
    """Create a chat model instance and determine its class.

    Args:
        llm_cfg: Resolved model configuration
        timeout_seconds: Optional timeout for the OpenAI client

    Returns:
        Tuple of (model_instance, chat_model_class)
    """
    # Handle local models
    if llm_cfg and llm_cfg.is_local:
        model = create_local_chat_model(
            model_id=llm_cfg.model,
            stream=True,
            generate_kwargs={"max_tokens": None},
        )
        # Local models use OpenAIChatModel-compatible formatter
        return model, OpenAIChatModel

    # Handle remote models - determine chat_model_class from provider config
    provider_id = llm_cfg.provider_id if llm_cfg else ""
    chat_model_class = _get_chat_model_class_from_provider(provider_id)

    # Create remote model instance with configuration
    model = _create_remote_model_instance(
        llm_cfg, chat_model_class, timeout_seconds=timeout_seconds,
    )

    return model, chat_model_class


def _get_chat_model_class_from_provider(
    override_provider_id: str = "",
) -> Type[ChatModelBase]:
    """Get the chat model class from provider configuration.

    Args:
        override_provider_id: If set, use this provider instead of the active one.
            Used by fallback chain to resolve the correct chat model class.

    Returns:
        Chat model class, defaults to OpenAI-compatible chat model if not found
    """
    chat_model_class = get_chat_model_class("OpenAIChatModel")
    try:
        providers_data = load_providers_json()
        provider_id = override_provider_id or providers_data.active_llm.provider_id
        if provider_id:
            chat_model_name = get_provider_chat_model(
                provider_id,
                providers_data,
            )
            chat_model_class = get_chat_model_class(chat_model_name)
    except Exception as e:
        logger.debug(
            "Failed to determine chat model from provider: %s, "
            "using OpenAI-compatible default chat model",
            e,
        )
    return chat_model_class


def _create_remote_model_instance(
    llm_cfg: Optional["ResolvedModelConfig"],
    chat_model_class: Type[ChatModelBase],
    timeout_seconds: Optional[int] = None,
) -> ChatModelBase:
    """Create a remote model instance with configuration.

    Args:
        llm_cfg: Resolved model configuration
        chat_model_class: Chat model class to instantiate
        timeout_seconds: Optional timeout for the OpenAI client

    Returns:
        Configured chat model instance
    """
    # Get configuration from llm_cfg or fall back to environment
    if llm_cfg and (llm_cfg.api_key or llm_cfg.base_url):
        model_name = llm_cfg.model or "qwen3-max"
        api_key = llm_cfg.api_key
        base_url = llm_cfg.base_url
    else:
        logger.warning(
            "No active LLM configured — "
            "falling back to DASHSCOPE_API_KEY env var",
        )
        model_name = "qwen3-max"
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Build client_kwargs with optional timeout
    client_kwargs: dict = {"base_url": base_url}
    if timeout_seconds is not None:
        import httpx

        client_kwargs["timeout"] = httpx.Timeout(
            float(timeout_seconds), connect=10.0,
        )

    model_kwargs = {
        "api_key": api_key,
        "stream": True,
        "client_kwargs": client_kwargs,
    }
    generate_kwargs = _host_ai_generate_kwargs(
        llm_cfg.provider_id if llm_cfg else "",
    )
    if generate_kwargs:
        model_kwargs["generate_kwargs"] = generate_kwargs

    # Instantiate model
    model = chat_model_class(model_name, **model_kwargs)

    return model


def _create_formatter_instance(
    chat_model_class: Type[ChatModelBase],
) -> FormatterBase:
    """Create a formatter instance for the given chat model class.

    The formatter is enhanced with file block support for handling
    file outputs in tool results.

    Args:
        chat_model_class: The chat model class

    Returns:
        Formatter instance with file block support
    """
    base_formatter_class = _get_formatter_for_chat_model(chat_model_class)
    formatter_class = _create_file_block_support_formatter(
        base_formatter_class,
    )
    return formatter_class()


__all__ = [
    "create_model_and_formatter",
]
