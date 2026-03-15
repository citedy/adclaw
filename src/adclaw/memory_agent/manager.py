# -*- coding: utf-8 -*-
"""AOMManager — orchestrates all AOM components lifecycle."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

from .consolidate import ConsolidationEngine, ConsolidationScheduler
from .embeddings import EmbeddingPipeline
from .file_inbox import FileInboxWatcher
from .ingest import IngestAgent
from .models import AOMConfig
from .multimodal import MultimodalProcessor
from .query import QueryAgent
from .store import MemoryStore

logger = logging.getLogger(__name__)


class AOMManager:
    """Lifecycle manager for Always-On Memory Agent components."""

    def __init__(
        self,
        working_dir: Path,
        config: AOMConfig,
        llm_caller: Callable[[str], Coroutine[Any, Any, str]],
    ) -> None:
        self.working_dir = working_dir
        self.config = config
        self.llm_caller = llm_caller

        self.store: Optional[MemoryStore] = None
        self.embedder: Optional[EmbeddingPipeline] = None
        self.multimodal: Optional[MultimodalProcessor] = None
        self.ingest_agent: Optional[IngestAgent] = None
        self.query_agent: Optional[QueryAgent] = None
        self.consolidation_engine: Optional[ConsolidationEngine] = None
        self._consolidation_scheduler: Optional[ConsolidationScheduler] = None
        self._file_inbox_watcher: Optional[FileInboxWatcher] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Initialize and start all AOM components."""
        if self._running:
            return

        db_path = self.working_dir / "aom.db"

        # 1. Store
        self.store = MemoryStore(db_path, dimensions=self.config.embedding_dimensions)
        await self.store.initialize()
        logger.info("AOM store initialized: %s", db_path)

        # 2. Embedder
        self.embedder = EmbeddingPipeline(
            backend=self.config.embedding_backend,
            model_name=self.config.embedding_model,
            api_url=self.config.embedding_api_url,
            dimensions=self.config.embedding_dimensions,
        )

        # 3. Multimodal processor (optional — only if API key provided)
        self.multimodal = None
        if self.config.multimodal_api_key:
            self.multimodal = MultimodalProcessor(
                provider=self.config.multimodal_provider,
                api_key=self.config.multimodal_api_key,
                model=self.config.multimodal_model,
                custom_api_url=self.config.multimodal_api_url,
            )
            logger.info(
                "AOM multimodal enabled: %s/%s",
                self.config.multimodal_provider,
                self.multimodal.model,
            )

        # 4. Ingest
        self.ingest_agent = IngestAgent(
            store=self.store,
            embedder=self.embedder,
            llm_caller=self.llm_caller,
            config=self.config,
            multimodal=self.multimodal,
        )

        # 4. Query
        self.query_agent = QueryAgent(
            store=self.store,
            embedder=self.embedder,
            llm_caller=self.llm_caller,
            config=self.config,
        )

        # 5. Consolidation
        self.consolidation_engine = ConsolidationEngine(
            store=self.store,
            embedder=self.embedder,
            llm_caller=self.llm_caller,
            config=self.config,
        )

        if self.config.consolidation_enabled:
            self._consolidation_scheduler = ConsolidationScheduler(
                engine=self.consolidation_engine,
                interval_minutes=self.config.consolidation_interval_minutes,
            )
            await self._consolidation_scheduler.start()

        # 6. File inbox
        if self.config.file_inbox_enabled:
            inbox_dir = self.working_dir / "inbox"
            self._file_inbox_watcher = FileInboxWatcher(
                inbox_dir=inbox_dir,
                ingest_agent=self.ingest_agent,
                store=self.store,
            )
            await self._file_inbox_watcher.start()

        self._running = True
        logger.info("AOM Manager started")

    async def stop(self) -> None:
        """Stop all AOM components gracefully."""
        if not self._running:
            return

        if self._file_inbox_watcher:
            await self._file_inbox_watcher.stop()

        if self._consolidation_scheduler:
            await self._consolidation_scheduler.stop()

        if self.multimodal:
            await self.multimodal.close()

        if self.store:
            await self.store.close()

        self._running = False
        logger.info("AOM Manager stopped")

    async def update_config(self, new_config: AOMConfig) -> None:
        """Hot-update AOM configuration."""
        old_config = self.config
        self.config = new_config

        # Update sub-component configs
        if self.ingest_agent:
            self.ingest_agent.config = new_config
        if self.query_agent:
            self.query_agent.config = new_config
        if self.consolidation_engine:
            self.consolidation_engine.config = new_config

        # Handle consolidation scheduler toggle
        if new_config.consolidation_enabled and not old_config.consolidation_enabled:
            if self.consolidation_engine and not self._consolidation_scheduler:
                self._consolidation_scheduler = ConsolidationScheduler(
                    engine=self.consolidation_engine,
                    interval_minutes=new_config.consolidation_interval_minutes,
                )
                await self._consolidation_scheduler.start()
        elif not new_config.consolidation_enabled and self._consolidation_scheduler:
            await self._consolidation_scheduler.stop()
            self._consolidation_scheduler = None

        # Handle file inbox toggle
        if new_config.file_inbox_enabled and not old_config.file_inbox_enabled:
            if self.ingest_agent and self.store and not self._file_inbox_watcher:
                inbox_dir = self.working_dir / "inbox"
                self._file_inbox_watcher = FileInboxWatcher(
                    inbox_dir=inbox_dir,
                    ingest_agent=self.ingest_agent,
                    store=self.store,
                )
                await self._file_inbox_watcher.start()
        elif not new_config.file_inbox_enabled and self._file_inbox_watcher:
            await self._file_inbox_watcher.stop()
            self._file_inbox_watcher = None

        logger.info("AOM config updated")
