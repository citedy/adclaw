# -*- coding: utf-8 -*-
"""Embedding pipeline — local sentence-transformers or API backend."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import struct
from typing import List, Optional

import httpx

from .store import MemoryStore

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """Generates embeddings via local model or OpenAI-compatible API."""

    def __init__(
        self,
        backend: str = "local",
        model_name: str = "all-MiniLM-L6-v2",
        api_url: str = "",
        dimensions: int = 384,
    ) -> None:
        self.backend = backend
        self.model_name = model_name
        self.api_url = api_url
        self.dimensions = dimensions
        self._local_model = None

    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer

            self._local_model = SentenceTransformer(self.model_name)
            self.dimensions = self._local_model.get_sentence_embedding_dimension()
        return self._local_model

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.backend == "api":
            return await self._embed_api(texts)
        return await self._embed_local(texts)

    async def _embed_local(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_running_loop()
        model = self._get_local_model()

        def _encode():
            return model.encode(texts, show_progress_bar=False).tolist()

        return await loop.run_in_executor(None, _encode)

    async def _embed_api(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self.api_url,
                json={"input": texts, "model": self.model_name},
            )
            resp.raise_for_status()
            data = resp.json()
        embeddings = sorted(data["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in embeddings]

    async def re_embed_all(self, store: MemoryStore) -> int:
        """Re-embed all memories in the store. Returns count of updated."""
        memories = await store.list_memories(limit=100_000)
        count = 0
        batch_size = 64
        for i in range(0, len(memories), batch_size):
            batch = memories[i : i + batch_size]
            texts = [m.content for m in batch]
            vectors = await self.embed_batch(texts)
            for mem, vec in zip(batch, vectors):
                await store.upsert_embedding(mem.id, vec, self.model_name)
                count += 1
        return count


class FakeEmbeddingPipeline(EmbeddingPipeline):
    """Deterministic embeddings from SHA-256 for testing."""

    def __init__(self, dimensions: int = 32) -> None:
        super().__init__(backend="fake", dimensions=dimensions)

    async def embed(self, text: str) -> List[float]:
        return self._hash_embed(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode()).digest()
        # Repeat hash bytes to fill dimensions
        needed = self.dimensions * 4  # 4 bytes per float32
        repeated = h * ((needed // len(h)) + 1)
        raw = repeated[:needed]
        vals = list(struct.unpack(f"<{self.dimensions}f", raw))
        # Normalize
        import math

        norm = math.sqrt(sum(v * v for v in vals))
        if norm > 0:
            vals = [v / norm for v in vals]
        return vals
