#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live AOM test with real LLM (aliyun-intl qwen3.5-plus).

Run: python tests/live_aom_test.py
"""

import asyncio
import json
import os
import sys
import time
import tempfile
from pathlib import Path

import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adclaw.memory_agent.store import MemoryStore
from adclaw.memory_agent.embeddings import FakeEmbeddingPipeline
from adclaw.memory_agent.ingest import IngestAgent
from adclaw.memory_agent.consolidate import ConsolidationEngine
from adclaw.memory_agent.query import QueryAgent
from adclaw.memory_agent.models import AOMConfig

# --- Real LLM caller via OpenAI-compatible API ---
API_KEY = os.environ.get("QWEN_API_KEY", "")
API_URL = os.environ.get("QWEN_API_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
MODEL = os.environ.get("QWEN_MODEL", "qwen-plus")


async def real_llm_caller(prompt: str) -> str:
    """Call qwen3.5-plus via OpenAI-compatible API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        # Strip thinking tags if present (qwen3.5 sometimes uses them)
        if "<think>" in content and "</think>" in content:
            think_end = content.index("</think>") + len("</think>")
            content = content[think_end:].strip()
        return content


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_ok(text):
    print(f"  [OK] {text}")


def print_fail(text):
    print(f"  [FAIL] {text}")


async def main():
    print_header("AOM Live Test — Real LLM (qwen3.5-plus)")

    # --- 1. Test LLM connectivity ---
    print_header("1. LLM Connectivity")
    t0 = time.time()
    try:
        resp = await real_llm_caller("Say 'hello' in one word.")
        print_ok(f"LLM responded in {time.time()-t0:.1f}s: {resp[:100]}")
    except Exception as e:
        print_fail(f"LLM unreachable: {e}")
        return

    # --- 2. Initialize components ---
    print_header("2. Initialize AOM Components")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "aom_live_test.db"
        store = MemoryStore(db_path, dimensions=32)
        await store.initialize()
        print_ok(f"MemoryStore initialized: {db_path}")

        embedder = FakeEmbeddingPipeline(dimensions=32)
        print_ok("FakeEmbeddingPipeline ready (32 dims)")

        config = AOMConfig(
            enabled=True,
            embedding_dimensions=32,
            importance_threshold=0.2,
        )

        ingest = IngestAgent(store, embedder, real_llm_caller, config)
        print_ok("IngestAgent ready")

        # --- 3. Ingest with REAL LLM extraction ---
        print_header("3. Ingest — Real LLM Entity/Topic Extraction")

        test_data = [
            {
                "content": '{"keyword": "buy running shoes online", "search_volume": 14800, "cpc": "$2.30", "competition": "high"}',
                "source_type": "mcp_tool",
                "source_id": "ahrefs_keywords",
            },
            {
                "content": "Competitor analysis: Nike.com ranks #1 for 'running shoes' with Domain Authority 95. Their top landing page has 2,340 backlinks from 890 referring domains.",
                "source_type": "mcp_tool",
                "source_id": "ahrefs_backlinks",
            },
            {
                "content": "Google Ads campaign 'Spring Running': CTR 3.8%, CPC $1.95, Conversions 127, ROAS 4.2x. Top performing ad group: 'trail running shoes' with 5.1% CTR.",
                "source_type": "mcp_tool",
                "source_id": "google_ads",
            },
            {
                "content": "Email campaign 'March Newsletter': sent to 15,000 subscribers, open rate 24.3%, click rate 3.7%, 12 unsubscribes. Best subject line: 'Your spring running guide'.",
                "source_type": "skill",
                "source_id": "sendgrid_analytics",
            },
            {
                "content": "Social media report: Instagram post about new trail shoes got 1,240 likes, 89 comments, 45 saves. Engagement rate 4.8% vs account average 2.1%.",
                "source_type": "mcp_tool",
                "source_id": "instagram_insights",
            },
        ]

        for i, item in enumerate(test_data):
            t0 = time.time()
            mem = await ingest.ingest(
                content=item["content"],
                source_type=item["source_type"],
                source_id=item["source_id"],
            )
            elapsed = time.time() - t0
            print_ok(
                f"[{i+1}/{len(test_data)}] Ingested in {elapsed:.1f}s | "
                f"entities={mem.entities[:3]} | topics={mem.topics[:3]} | "
                f"importance={mem.importance:.2f}"
            )

        stats = await store.get_stats()
        print(f"\n  Store stats: {json.dumps(stats, indent=2)}")

        # --- 4. Test deduplication ---
        print_header("4. Deduplication Test")
        dup_mem = await ingest.ingest(
            content=test_data[0]["content"],
            source_type="mcp_tool",
            source_id="duplicate_test",
        )
        stats2 = await store.get_stats()
        if stats2["total_memories"] == stats["total_memories"]:
            print_ok(f"Dedup works: still {stats2['total_memories']} memories")
        else:
            print_fail(f"Dedup failed: {stats['total_memories']} → {stats2['total_memories']}")

        # --- 5. Consolidation with REAL LLM ---
        print_header("5. Consolidation — Real LLM Insight Generation")
        engine = ConsolidationEngine(store, embedder, real_llm_caller, config)
        t0 = time.time()
        insights = await engine.run_consolidation_cycle()
        elapsed = time.time() - t0
        print_ok(f"Generated {len(insights)} insights in {elapsed:.1f}s")
        for ins in insights:
            print(f"\n  Insight: {ins.insight[:200]}")
            print(f"  Importance: {ins.importance}")
            print(f"  Based on {len(ins.memory_ids)} memories")

        # --- 6. Query with REAL LLM synthesis ---
        print_header("6. Query — Real LLM Hybrid Search + Synthesis")

        questions = [
            "What do we know about running shoes marketing performance?",
            "What is our email campaign open rate?",
            "How does our Instagram engagement compare to average?",
        ]

        query_agent = QueryAgent(store, embedder, real_llm_caller, config)
        for q in questions:
            t0 = time.time()
            result = await query_agent.query(q, max_results=5)
            elapsed = time.time() - t0
            print(f"\n  Q: {q}")
            print(f"  A ({elapsed:.1f}s): {result.answer[:300]}")
            print(f"  Citations: {len(result.citations)}")
            for c in result.citations[:3]:
                print(f"    - [{c.memory.source_type}/{c.memory.source_id}] score={c.score:.4f}")

        # --- 7. List all memories ---
        print_header("7. Final Memory Dump")
        all_mems = await store.list_memories(limit=20)
        for m in all_mems:
            print(f"\n  [{m.source_type}/{m.source_id}] imp={m.importance:.2f}")
            print(f"    entities: {m.entities}")
            print(f"    topics: {m.topics}")
            print(f"    content: {m.content[:100]}...")

        # --- 8. Cleanup ---
        await store.close()
        print_header("DONE — All live tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
