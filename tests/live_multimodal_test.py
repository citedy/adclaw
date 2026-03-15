#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live test: multimodal AOM with Gemini Flash Lite.

Tests: image processing, text file, PDF-like, and the two-tier architecture
(basic mode without key vs advanced mode with key).
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adclaw.memory_agent.store import MemoryStore
from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.multimodal import MultimodalProcessor, is_multimodal_file
from adclaw.memory_agent.query import QueryAgent
from adclaw.memory_agent.models import AOMConfig

# Real LLM for text extraction — set env vars before running
API_KEY_LLM = os.environ.get("QWEN_API_KEY", "")
LLM_URL = os.environ.get("QWEN_API_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
LLM_MODEL = os.environ.get("QWEN_MODEL", "qwen-plus")


async def real_llm_caller(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            LLM_URL,
            headers={"Authorization": f"Bearer {API_KEY_LLM}", "Content-Type": "application/json"},
            json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 500},
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        if "<think>" in content and "</think>" in content:
            content = content[content.index("</think>") + len("</think>"):].strip()
        return content


def print_header(text):
    print(f"\n{'='*60}\n  {text}\n{'='*60}")


def print_ok(text):
    print(f"  [OK] {text}")


def print_fail(text):
    print(f"  [FAIL] {text}")


async def main():
    # Check if Gemini key is provided as argument
    gemini_key = sys.argv[1] if len(sys.argv) > 1 else ""

    print_header("AOM Multimodal Live Test")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # --- Create test files ---
        print_header("1. Creating test files")

        # Text file
        text_file = tmpdir / "seo_report.txt"
        text_file.write_text(
            "Q1 2026 SEO Report\n"
            "Organic traffic: 45,000 sessions (+12% QoQ)\n"
            "Top keywords: running shoes (pos #3), trail shoes (pos #1)\n"
            "New backlinks: 234 from 89 domains\n"
            "Core Web Vitals: LCP 2.1s, FID 45ms, CLS 0.05\n"
        )
        print_ok(f"Created {text_file.name}")

        # CSV file
        csv_file = tmpdir / "campaigns.csv"
        csv_file.write_text(
            "campaign,impressions,clicks,ctr,cost,conversions\n"
            "Spring Running,125000,4750,3.8%,$9262,127\n"
            "Trail Shoes,89000,4539,5.1%,$6800,95\n"
            "Newsletter Promo,45000,1890,4.2%,$2100,34\n"
        )
        print_ok(f"Created {csv_file.name}")

        # Create a simple test PNG (1x1 pixel red dot)
        import struct
        import zlib

        def make_test_png():
            # Minimal valid PNG: 100x30 with "AdClaw Test" text-like pattern
            width, height = 100, 30
            raw = b""
            for y in range(height):
                raw += b"\x00"  # filter none
                for x in range(width):
                    if 10 <= x <= 90 and 5 <= y <= 25:
                        raw += b"\x20\x60\xff"  # blue-ish
                    else:
                        raw += b"\xff\xff\xff"  # white
            compressed = zlib.compress(raw)

            png = b"\x89PNG\r\n\x1a\n"
            # IHDR
            ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
            png += _png_chunk(b"IHDR", ihdr_data)
            # IDAT
            png += _png_chunk(b"IDAT", compressed)
            # IEND
            png += _png_chunk(b"IEND", b"")
            return png

        def _png_chunk(chunk_type, data):
            chunk = chunk_type + data
            return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

        img_file = tmpdir / "dashboard_screenshot.png"
        img_file.write_bytes(make_test_png())
        print_ok(f"Created {img_file.name} (test PNG)")

        # --- 2. Test BASIC mode (no multimodal key) ---
        print_header("2. Basic Mode — text only, no multimodal key")

        store = MemoryStore(tmpdir / "test_basic.db", dimensions=32)
        await store.initialize()
        embedder = FakeEmbeddingPipeline(dimensions=32)
        config = AOMConfig(enabled=True, embedding_dimensions=32, importance_threshold=0.2)

        ingest_basic = IngestAgent(store, embedder, real_llm_caller, config, multimodal=None)

        # Text file should work
        t0 = time.time()
        mem = await ingest_basic.ingest_file(text_file)
        print_ok(f"Text file ingested in {time.time()-t0:.1f}s | entities={mem.entities[:3]} | topics={mem.topics[:3]}")

        # CSV should work
        t0 = time.time()
        mem = await ingest_basic.ingest_file(csv_file)
        print_ok(f"CSV file ingested in {time.time()-t0:.1f}s | entities={mem.entities[:3]} | topics={mem.topics[:3]}")

        # Image should FAIL in basic mode
        try:
            await ingest_basic.ingest_file(img_file)
            print_fail("Image should have been rejected in basic mode!")
        except RuntimeError as e:
            print_ok(f"Image correctly rejected: {str(e)[:80]}")

        stats = await store.get_stats()
        print(f"  Basic mode stats: {json.dumps(stats)}")
        await store.close()

        # --- 3. Test ADVANCED mode (with Gemini key) ---
        if not gemini_key:
            print_header("3. Advanced Mode — SKIPPED (no Gemini key)")
            print("  Pass Gemini API key as first argument to test multimodal:")
            print("  python tests/live_multimodal_test.py YOUR_GEMINI_KEY")
        else:
            print_header("3. Advanced Mode — Gemini Flash Lite")

            store2 = MemoryStore(tmpdir / "test_advanced.db", dimensions=32)
            await store2.initialize()

            mm = MultimodalProcessor(
                provider="gemini",
                api_key=gemini_key,
                model="gemini-2.5-flash-lite",
            )

            ingest_adv = IngestAgent(store2, embedder, real_llm_caller, config, multimodal=mm)

            # Text file still works
            t0 = time.time()
            mem = await ingest_adv.ingest_file(text_file)
            print_ok(f"Text file: {time.time()-t0:.1f}s | {mem.topics[:3]}")

            # Image now works via Gemini
            t0 = time.time()
            try:
                mem = await ingest_adv.ingest_file(img_file)
                print_ok(f"Image file: {time.time()-t0:.1f}s | content={mem.content[:150]}...")
                print(f"  Entities: {mem.entities}")
                print(f"  Topics: {mem.topics}")
                print(f"  Metadata: {mem.metadata}")
            except Exception as e:
                print_fail(f"Image processing failed: {e}")

            # Query across both text and image memories
            print_header("4. Query across multimodal memories")
            query_agent = QueryAgent(store2, embedder, real_llm_caller, config)
            t0 = time.time()
            result = await query_agent.query("What do we know about our marketing performance?")
            print(f"  Answer ({time.time()-t0:.1f}s): {result.answer[:300]}")
            print(f"  Citations: {len(result.citations)}")

            stats2 = await store2.get_stats()
            print(f"\n  Advanced mode stats: {json.dumps(stats2)}")

            await mm.close()
            await store2.close()

        print_header("DONE!")


if __name__ == "__main__":
    asyncio.run(main())
