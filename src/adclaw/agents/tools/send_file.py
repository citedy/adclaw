# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long,too-many-return-statements
import json
import logging
import os
import mimetypes

from agentscope.tool import ToolResponse
from agentscope.message import (
    TextBlock,
    ImageBlock,
    AudioBlock,
    VideoBlock,
)

from ..schema import FileBlock

logger = logging.getLogger(__name__)


def _auto_as_type(mt: str) -> str:
    if mt.startswith("image/"):
        return "image"
    if mt.startswith("audio/"):
        return "audio"
    if mt.startswith("video/"):
        return "video"
    return "file"


def _is_auto_publish_enabled() -> bool:
    """Check config.json -> herenow.auto_publish (default: True)."""
    config_path = os.path.join(
        os.environ.get("ADCLAW_WORKING_DIR", "/app/working"), "config.json"
    )
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("herenow", {}).get("auto_publish", True)
    except Exception:
        return True  # default on


async def _try_herenow_publish(file_path: str) -> str | None:
    """Attempt to publish file to here.now. Returns URL or None on failure."""
    try:
        from .herenow_publish import publish_to_herenow

        result = await publish_to_herenow(file_path)
        for block in result.content:
            text = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
            if text.startswith("File published:"):
                return text.split("\n")[0].replace("File published: ", "")
    except Exception as e:
        logger.warning("Auto-publish to here.now failed: %s", e)
    return None


async def send_file_to_user(
    file_path: str,
) -> ToolResponse:
    """Send a file to the user.

    If here.now auto-publish is enabled (default), the file is also uploaded
    to here.now and a public download link is included in the response.

    Args:
        file_path (`str`):
            Path to the file to send.

    Returns:
        `ToolResponse`:
            The tool response containing the file or an error message.
    """

    if not os.path.exists(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The file {file_path} does not exist.",
                ),
            ],
        )

    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: The path {file_path} is not a file.",
                ),
            ],
        )

    # Auto-publish to here.now (non-blocking — failure doesn't prevent sending)
    herenow_url = None
    if _is_auto_publish_enabled():
        herenow_url = await _try_herenow_publish(file_path)

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    as_type = _auto_as_type(mime_type)

    success_msg = "File sent successfully."
    if herenow_url:
        success_msg += f"\n\nDownload link: {herenow_url}"

    try:
        # text
        if as_type == "text":
            with open(file_path, "r", encoding="utf-8") as file:
                content = [TextBlock(type="text", text=file.read())]
                if herenow_url:
                    content.append(TextBlock(type="text", text=f"Download link: {herenow_url}"))
                return ToolResponse(content=content)

        # Use local file URL instead of base64
        absolute_path = os.path.abspath(file_path)
        file_url = f"file://{absolute_path}"
        source = {"type": "url", "url": file_url}

        if as_type == "image":
            return ToolResponse(
                content=[
                    ImageBlock(type="image", source=source),
                    TextBlock(type="text", text=success_msg),
                ],
            )
        if as_type == "audio":
            return ToolResponse(
                content=[
                    AudioBlock(type="audio", source=source),
                    TextBlock(type="text", text=success_msg),
                ],
            )
        if as_type == "video":
            return ToolResponse(
                content=[
                    VideoBlock(type="video", source=source),
                    TextBlock(type="text", text=success_msg),
                ],
            )

        return ToolResponse(
            content=[
                FileBlock(
                    type="file",
                    source=source,
                    filename=os.path.basename(file_path),
                ),
                TextBlock(type="text", text=success_msg),
            ],
        )

    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error: Send file failed due to \n{e}",
                ),
            ],
        )
