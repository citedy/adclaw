# -*- coding: utf-8 -*-
"""FileInboxWatcher — monitors inbox/ folder and auto-ingests new files.

In basic mode: only text files (.txt, .md, .json, .csv).
In advanced mode (multimodal API key set): also images, audio, video, PDF.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .ingest import IngestAgent
from .multimodal import ALL_SUPPORTED_EXTS, is_multimodal_file, is_supported_file
from .store import MemoryStore

logger = logging.getLogger(__name__)

_TEXT_ONLY_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".xml", ".html", ".log", ".yaml", ".yml"}


class FileInboxWatcher:
    """Polls a directory for new files and ingests them.

    When multimodal processor is available on the IngestAgent,
    supports images, audio, video, and PDF files too.
    """

    def __init__(
        self,
        inbox_dir: Path,
        ingest_agent: IngestAgent,
        store: MemoryStore,
        poll_interval: float = 5.0,
    ) -> None:
        self.inbox_dir = inbox_dir
        self.ingest_agent = ingest_agent
        self.store = store
        self.poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None

    @property
    def _supported_extensions(self) -> set[str]:
        """Return supported extensions based on multimodal availability."""
        if (
            self.ingest_agent.multimodal
            and self.ingest_agent.multimodal.is_available
        ):
            return ALL_SUPPORTED_EXTS
        return _TEXT_ONLY_EXTENSIONS

    async def start(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        mode = "advanced (multimodal)" if self._supported_extensions == ALL_SUPPORTED_EXTS else "basic (text only)"
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("FileInboxWatcher started [%s]: %s", mode, self.inbox_dir)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._scan_inbox()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Inbox scan error: %s", exc)
            await asyncio.sleep(self.poll_interval)

    async def _scan_inbox(self) -> None:
        if not self.inbox_dir.exists():
            return

        supported = self._supported_extensions

        for file_path in sorted(self.inbox_dir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in supported:
                continue

            fp_str = str(file_path)
            if await self.store.is_file_processed(fp_str):
                continue

            try:
                mem = await self.ingest_agent.ingest_file(file_path)
                await self.store.mark_file_processed(fp_str)
                logger.info(
                    "Ingested inbox file: %s (%s, imp=%.2f)",
                    file_path.name,
                    "multimodal" if is_multimodal_file(file_path) else "text",
                    mem.importance,
                )
            except RuntimeError as exc:
                # Multimodal not available — skip silently
                logger.debug("Skipping %s: %s", file_path.name, exc)
            except Exception as exc:
                logger.warning("Failed to ingest %s: %s", file_path.name, exc)
