# -*- coding: utf-8 -*-
"""Tests for EmbeddingPipeline and FakeEmbeddingPipeline."""

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adclaw.memory_agent.embeddings import EmbeddingPipeline, FakeEmbeddingPipeline


class TestFakeEmbeddingPipeline:
    async def test_embed_returns_correct_dimensions(self):
        pipe = FakeEmbeddingPipeline(dimensions=32)
        vec = await pipe.embed("test text")
        assert len(vec) == 32

    async def test_embed_is_deterministic(self):
        pipe = FakeEmbeddingPipeline(dimensions=16)
        v1 = await pipe.embed("hello")
        v2 = await pipe.embed("hello")
        assert v1 == v2

    async def test_different_texts_different_vectors(self):
        pipe = FakeEmbeddingPipeline(dimensions=16)
        v1 = await pipe.embed("hello")
        v2 = await pipe.embed("world")
        assert v1 != v2

    async def test_embed_batch(self):
        pipe = FakeEmbeddingPipeline(dimensions=8)
        results = await pipe.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(len(v) == 8 for v in results)

    async def test_embed_batch_empty(self):
        pipe = FakeEmbeddingPipeline(dimensions=8)
        assert await pipe.embed_batch([]) == []

    async def test_vectors_are_normalized(self):
        pipe = FakeEmbeddingPipeline(dimensions=32)
        vec = await pipe.embed("test normalization")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 0.01


class TestEmbeddingPipelineAPI:
    async def test_api_backend(self):
        pipe = EmbeddingPipeline(
            backend="api",
            model_name="test-model",
            api_url="http://fake:8080/v1/embeddings",
            dimensions=4,
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]},
                {"index": 1, "embedding": [0.5, 0.6, 0.7, 0.8]},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("adclaw.memory_agent.embeddings.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            results = await pipe.embed_batch(["text1", "text2"])
            assert len(results) == 2
            assert results[0] == [0.1, 0.2, 0.3, 0.4]
