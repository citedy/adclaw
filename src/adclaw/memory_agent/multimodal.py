# -*- coding: utf-8 -*-
"""MultimodalProcessor — converts images/audio/video/PDF to text via vision LLM.

Supports Gemini, OpenAI, and Anthropic as multimodal backends.
Only active when user provides an API key (advanced memory mode).
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)

# File extensions grouped by modality
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
_PDF_EXTS = {".pdf"}
_TEXT_EXTS = {".txt", ".md", ".json", ".csv", ".xml", ".html", ".log", ".yaml", ".yml"}

ALL_SUPPORTED_EXTS = _IMAGE_EXTS | _AUDIO_EXTS | _VIDEO_EXTS | _PDF_EXTS | _TEXT_EXTS

_DESCRIBE_PROMPT = (
    "Analyze this file thoroughly. Extract and describe:\n"
    "1. All text content (OCR if image)\n"
    "2. Key entities (people, companies, products, URLs)\n"
    "3. Topics and themes\n"
    "4. Important data points, numbers, metrics\n"
    "5. Visual elements description (if image/video)\n"
    "6. Audio transcript (if audio/video)\n\n"
    "Be detailed and factual. This will be stored in long-term memory."
)

# Max file size per provider (bytes)
_MAX_FILE_SIZE = {
    "gemini": 20 * 1024 * 1024,    # 20MB for Gemini
    "openai": 20 * 1024 * 1024,    # 20MB for OpenAI
    "anthropic": 5 * 1024 * 1024,  # 5MB for Anthropic (images only)
}

# Provider API endpoints
_API_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}

# Default models per provider
_DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash-lite",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


def is_multimodal_file(file_path: Path) -> bool:
    """Check if file requires multimodal processing (not plain text)."""
    return file_path.suffix.lower() in (_IMAGE_EXTS | _AUDIO_EXTS | _VIDEO_EXTS | _PDF_EXTS)


def is_supported_file(file_path: Path) -> bool:
    """Check if file is supported at all (text or multimodal)."""
    return file_path.suffix.lower() in ALL_SUPPORTED_EXTS


class MultimodalProcessor:
    """Converts non-text files to text descriptions via multimodal LLM API.

    Architecture:
    - Basic mode (no API key): text files only, uses user's main LLM
    - Advanced mode (API key provided): all file types, uses vision LLM

    The processor does NOT replace the main LLM. It's a separate layer
    that pre-processes files into text before they enter the AOM pipeline.
    """

    def __init__(
        self,
        provider: Literal["gemini", "openai", "anthropic"] = "gemini",
        api_key: str = "",
        model: str = "",
        custom_api_url: str = "",
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.model = model or _DEFAULT_MODELS.get(provider, "")
        self.custom_api_url = custom_api_url
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_available(self) -> bool:
        """Whether multimodal processing is available (API key set)."""
        return bool(self.api_key)

    async def process_file(self, file_path: Path) -> str:
        """Convert any supported file to text description.

        Args:
            file_path: Path to the file.

        Returns:
            Text description/transcription of the file content.

        Raises:
            ValueError: If file type not supported or too large.
            RuntimeError: If no API key configured.
        """
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        # Text files — just read directly, no API needed
        if suffix in _TEXT_EXTS:
            return file_path.read_text(encoding="utf-8", errors="replace")

        # Multimodal files require API key
        if not self.is_available:
            raise RuntimeError(
                f"Multimodal processing requires an API key. "
                f"Set multimodal_api_key in AOM config to process {suffix} files."
            )

        if suffix not in ALL_SUPPORTED_EXTS:
            raise ValueError(f"Unsupported file type: {suffix}")

        # Check file size
        max_size = _MAX_FILE_SIZE.get(self.provider, 20 * 1024 * 1024)
        file_size = file_path.stat().st_size
        if file_size > max_size:
            raise ValueError(
                f"File too large ({file_size / 1024 / 1024:.1f}MB). "
                f"Max for {self.provider}: {max_size / 1024 / 1024:.0f}MB"
            )

        # Read and encode file
        file_bytes = file_path.read_bytes()
        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        # Route to provider
        if self.provider == "gemini":
            return await self._process_gemini(file_bytes, mime_type)
        elif self.provider == "openai":
            return await self._process_openai(file_bytes, mime_type, suffix)
        elif self.provider == "anthropic":
            return await self._process_anthropic(file_bytes, mime_type, suffix)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ----- Gemini -----

    async def _process_gemini(self, file_bytes: bytes, mime_type: str) -> str:
        """Process via Google Gemini API (supports all modalities)."""
        client = await self._get_client()
        b64_data = base64.standard_b64encode(file_bytes).decode()

        url = self.custom_api_url or _API_URLS["gemini"].format(model=self.model)
        url = f"{url}?key={self.api_key}"

        body = {
            "contents": [
                {
                    "parts": [
                        {"text": _DESCRIBE_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            },
        }

        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            logger.warning("Gemini response parse error: %s | data=%s", exc, data)
            raise RuntimeError(f"Failed to parse Gemini response: {exc}") from exc

    # ----- OpenAI -----

    async def _process_openai(
        self, file_bytes: bytes, mime_type: str, suffix: str
    ) -> str:
        """Process via OpenAI API (images + audio via separate endpoints)."""
        client = await self._get_client()

        # Audio: use whisper endpoint
        if suffix in _AUDIO_EXTS:
            return await self._process_openai_audio(client, file_bytes, suffix)

        # Images/PDF: use vision
        b64_data = base64.standard_b64encode(file_bytes).decode()
        url = self.custom_api_url or _API_URLS["openai"]

        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _DESCRIBE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64_data}",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
        }

        resp = await client.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _process_openai_audio(
        self, client: httpx.AsyncClient, file_bytes: bytes, suffix: str
    ) -> str:
        """Transcribe audio via OpenAI Whisper API."""
        import io

        url = "https://api.openai.com/v1/audio/transcriptions"
        files = {"file": (f"audio{suffix}", io.BytesIO(file_bytes), "audio/mpeg")}
        data = {"model": "whisper-1"}

        resp = await client.post(
            url,
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        resp.raise_for_status()
        return resp.json()["text"]

    # ----- Anthropic -----

    async def _process_anthropic(
        self, file_bytes: bytes, mime_type: str, suffix: str
    ) -> str:
        """Process via Anthropic API (images + PDF only)."""
        if suffix in _AUDIO_EXTS | _VIDEO_EXTS:
            raise ValueError(
                f"Anthropic does not support {suffix} files. "
                f"Use Gemini or OpenAI for audio/video."
            )

        client = await self._get_client()
        b64_data = base64.standard_b64encode(file_bytes).decode()
        url = self.custom_api_url or _API_URLS["anthropic"]

        # Determine content type for Anthropic
        if suffix in _PDF_EXTS:
            source_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64_data,
                },
            }
        else:
            source_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": b64_data,
                },
            }

        body = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        source_block,
                        {"type": "text", "text": _DESCRIBE_PROMPT},
                    ],
                }
            ],
        }

        resp = await client.post(
            url,
            json=body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
