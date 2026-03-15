# -*- coding: utf-8 -*-
"""Publish files to here.now — free instant web hosting for agents.

Anonymous uploads expire in 24 hours. Authenticated uploads (HERENOW_API_KEY)
are permanent.
"""

import hashlib
import mimetypes
import os
import logging
from typing import Optional

import httpx
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

HERENOW_API = "https://here.now/api/v1"


def _get_api_key() -> Optional[str]:
    """Return HERENOW_API_KEY from env, or None for anonymous mode."""
    return os.environ.get("HERENOW_API_KEY") or None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def publish_to_herenow(
    file_path: str,
) -> ToolResponse:
    """Upload a file to here.now and return a public URL.

    The file is published to here.now instant hosting. Without an API key,
    the link expires in 24 hours. With HERENOW_API_KEY set, links are permanent.

    Args:
        file_path (`str`):
            Path to the local file to publish.

    Returns:
        `ToolResponse`:
            A response containing the public URL or an error message.
    """
    if not os.path.exists(file_path):
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error: file not found: {file_path}")]
        )
    if not os.path.isfile(file_path):
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error: not a file: {file_path}")]
        )

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    file_hash = _sha256(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    api_key = _get_api_key()
    headers = {"Content-Type": "application/json", "X-HereNow-Client": "adclaw"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Create site
            create_resp = await client.post(
                f"{HERENOW_API}/publish",
                headers=headers,
                json={
                    "files": [
                        {
                            "path": filename,
                            "size": file_size,
                            "contentType": content_type,
                            "hash": file_hash,
                        }
                    ],
                },
            )
            if create_resp.status_code != 200:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=f"Error: here.now create failed ({create_resp.status_code}): {create_resp.text}",
                        )
                    ]
                )

            data = create_resp.json()
            slug = data["slug"]
            site_url = data["siteUrl"]
            upload_info = data["upload"]
            version_id = upload_info["versionId"]
            finalize_url = upload_info["finalizeUrl"]

            # Step 2: Upload file to presigned URL
            upload = upload_info["uploads"][0]
            upload_headers = upload.get("headers", {})
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            put_resp = await client.put(
                upload["url"],
                headers=upload_headers,
                content=file_bytes,
            )
            if put_resp.status_code not in (200, 201):
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=f"Error: file upload failed ({put_resp.status_code}): {put_resp.text}",
                        )
                    ]
                )

            # Step 3: Finalize
            fin_headers = {"Content-Type": "application/json"}
            if api_key:
                fin_headers["Authorization"] = f"Bearer {api_key}"
            fin_resp = await client.post(
                finalize_url,
                headers=fin_headers,
                json={"versionId": version_id},
            )
            if fin_resp.status_code != 200:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=f"Error: finalize failed ({fin_resp.status_code}): {fin_resp.text}",
                        )
                    ]
                )

            # Build result
            file_url = f"{site_url}{filename}" if not site_url.endswith(filename) else site_url
            expires = data.get("expiresAt")
            mode = "permanent" if api_key else f"expires {expires}"

            logger.info("Published %s to %s (%s)", filename, file_url, mode)

            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"File published: {file_url}\nMode: {mode}",
                    )
                ]
            )

    except Exception as e:
        logger.exception("here.now publish failed")
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error: here.now publish failed: {e}")]
        )
