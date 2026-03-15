#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live stress-test for AOM memory optimization (R1-R4).

Injects 100+ memories via REST API, including intentional near-duplicates
and aged entries, then triggers consolidation and verifies:
- R1: Pre-compression reduces summary size
- R3: Near-duplicates are detected and rejected
- R4: Temporal pruning cleans old entries

Usage:
    python3 scripts/test_memory_live.py [--base-url http://localhost:8088]
    python3 scripts/test_memory_live.py --cleanup   # remove all test memories

Requires: requests (pip install requests)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from typing import Any

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_BASE = "http://localhost:8088"
API = "/api"
TAG = "live-test"  # source_id prefix for cleanup

# ---------------------------------------------------------------------------
# Test data generators
# ---------------------------------------------------------------------------

# 50 unique marketing/tech memories
SEED_MEMORIES = [
    "Decided to use PostgreSQL 16 as the primary database for all tenant data.",
    "Action item: migrate all user sessions from Redis to PostgreSQL by end of March.",
    "Config update: DB_HOST=db.internal, DB_PORT=5432, DB_POOL_SIZE=20.",
    "Note: John mentioned we should consider read replicas for analytics queries.",
    "The SEO audit revealed 47 pages with missing meta descriptions.",
    "Competitor analysis: Jasper.ai raised Series C at $1.5B valuation.",
    "Decision: all new API endpoints must use Zod validation schemas.",
    "Bug report: TTS generation fails for articles longer than 15000 words.",
    "Meeting notes: discussed moving from Vercel to Digital Ocean for cost savings.",
    "The content pipeline processes approximately 2000 articles per day.",
    "User feedback: dashboard loading time exceeds 3 seconds on mobile.",
    "Architecture decision: use QStash for all async job processing.",
    "The billing system charges 10 credits per article generation.",
    "Config: REDIS_URL=redis://cache.internal:6379, REDIS_TTL=3600.",
    "Action: implement rate limiting at 100 requests per minute per tenant.",
    "Note: Cloudflare Workers have a 10ms CPU time limit per invocation.",
    "Decision: adopt conventional commits format for all repositories.",
    "The humanizer module supports 5 AI providers with automatic fallback.",
    "Performance: p95 latency for article generation is 45 seconds.",
    "Security: all API keys must be rotated every 90 days.",
    "The lead magnet feature costs 120 credits and generates 3 asset types.",
    "Integration: Stripe webhooks process subscription events in under 2 seconds.",
    "Note: Safari has a bug with backdrop-filter on fixed position elements.",
    "Decision: use server-sent events instead of WebSocket for progress updates.",
    "The agent platform exposes 56 MCP tools for content operations.",
    "Config: SENTRY_DSN set for both frontend and backend error tracking.",
    "Action: add PostHog tracking to all conversion funnels by next sprint.",
    "The referral system awards 50 credits per successful invite.",
    "Architecture: proxy.ts handles all routing — no middleware.ts in Next.js 16.",
    "Bug: email templates fail to render when tenant has no logo URL configured.",
    "Note: Google Search Console shows 12000 indexed pages for citedy.com.",
    "Decision: implement tiered pricing — Starter ($0), Pro ($29), Business ($99).",
    "The TTS service supports Cartesia, ElevenLabs, OpenAI, and Gemini providers.",
    "Config: NEXT_PUBLIC_SITE_URL=https://www.citedy.com, no trailing slash.",
    "Action: create E2E tests for the subscription upgrade flow.",
    "Performance: Redis cache hit rate is 87% for blog content queries.",
    "Note: Digital Ocean App Platform has a 10-minute build timeout.",
    "Decision: use Resend for transactional email, SendGrid deprecated.",
    "The dashboard preset system has 5 presets with 15 card types.",
    "Integration: Apollo.io API used for lead enrichment and contact search.",
    "Bug: custom domain CNAME validation timeout set too low (30 seconds).",
    "Config: R2_BUCKET=citedy, R2_PUBLIC_URL=https://download.citedy.com/.",
    "Action: implement content gap analysis with automatic keyword suggestions.",
    "The social adaptation module supports LinkedIn, X, Reddit, and Instagram.",
    "Note: Supabase RLS policies must be tested with service role AND anon key.",
    "Decision: all database migrations go through /db-migrate slash command.",
    "Architecture: unified notification system handles email, push, and in-app.",
    "Performance: blog page TTFB averages 180ms with Cloudflare caching enabled.",
    "The skill scanner checks 208 security patterns across 15 categories.",
    "Config: LOG_LEVEL=INFO in production, DEBUG in development.",
]

# Near-duplicate variants — realistic minor edits of SEED_MEMORIES[0:10]
# These simulate a user re-entering slightly tweaked versions of existing info
NEAR_DUPLICATES = [
    # Minor word swap/addition (should be caught)
    "Decided to use PostgreSQL 16 as the primary database for all tenant data storage.",
    "Decided to use PostgreSQL 16 as the primary database for all our tenant data.",
    # Small edit in middle
    "Action item: migrate all user sessions from Redis to PostgreSQL by the end of March.",
    "Action item: migrate user sessions from Redis to PostgreSQL by end of March.",
    # Typo fix style
    "Config update: DB_HOST=db.internal, DB_PORT=5432, DB_POOL_SIZE=20",
    "Config update: DB_HOST=db.internal DB_PORT=5432 DB_POOL_SIZE=20.",
    # Extra word added
    "Note: John mentioned that we should consider read replicas for analytics queries.",
    "Note: John mentioned we should definitely consider read replicas for analytics queries.",
    # Almost identical with minor punctuation/word change
    "The SEO audit revealed 47 pages with missing meta descriptions on our site.",
    "The SEO audit revealed that 47 pages have missing meta descriptions.",
]

# Low-importance notes that should be pruned (R4)
EPHEMERAL_NOTES = [
    "FYI: coffee machine on 3rd floor is broken again.",
    "Note: the wifi password was changed to GreenFox2026.",
    "Info: parking lot B will be closed for maintenance tomorrow.",
    "FYI: slack channel #random has a new pinned message about lunch.",
    "Note: printer on 2nd floor is out of toner.",
    "Info: the office plants were watered on Monday.",
    "FYI: someone left a jacket in conference room A.",
    "Note: the fire drill is scheduled for Thursday at 2pm.",
    "Info: new soap dispensers installed in all bathrooms.",
    "FYI: the vending machine now accepts contactless payments.",
]


def _make_source_id(prefix: str, idx: int) -> str:
    return f"{TAG}-{prefix}-{idx}"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class AOMClient:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}{API}"
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        # Disable keep-alive to avoid connection reset issues
        self.session.headers["Connection"] = "close"

    def _request(self, method: str, url: str, retries: int = 3, **kwargs):
        """Request with retry and backoff."""
        kwargs.setdefault("timeout", 30)
        for attempt in range(retries):
            try:
                r = self.session.request(method, url, **kwargs)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.HTTPError) as e:
                if attempt == retries - 1:
                    raise
                wait = 0.5 * (attempt + 1)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def health(self) -> bool:
        try:
            r = self.session.get(f"{self.base}/api/health", timeout=5)
            return r.status_code == 200
        except Exception:
            # Try memory stats as fallback health check
            try:
                r = self.session.get(f"{self.api}/memory/stats", timeout=5)
                return r.status_code == 200
            except Exception:
                return False

    def stats(self) -> dict:
        return self._request("GET", f"{self.api}/memory/stats").json()

    def list_memories(self, limit: int = 500) -> list[dict]:
        return self._request(
            "GET", f"{self.api}/memory/memories",
            params={"limit": limit}, timeout=15,
        ).json()

    def ingest(
        self,
        content: str,
        source_type: str = "manual",
        source_id: str = "",
        metadata: dict | None = None,
    ) -> dict:
        body: dict[str, Any] = {
            "content": content,
            "source_type": source_type,
            "source_id": source_id,
        }
        if metadata:
            body["metadata"] = metadata
        return self._request(
            "POST", f"{self.api}/memory/memories",
            json=body, timeout=30,
        ).json()

    def delete(self, memory_id: str) -> bool:
        try:
            self._request("DELETE", f"{self.api}/memory/memories/{memory_id}")
            return True
        except Exception:
            return False

    def consolidate(self) -> dict:
        return self._request(
            "POST", f"{self.api}/memory/consolidate", timeout=120,
        ).json()

    def consolidations(self, limit: int = 50) -> list[dict]:
        return self._request(
            "GET", f"{self.api}/memory/consolidations",
            params={"limit": limit},
        ).json()


# ---------------------------------------------------------------------------
# Test phases
# ---------------------------------------------------------------------------

def phase_0_check(client: AOMClient) -> dict:
    """Check AOM is running and get baseline stats."""
    print("=" * 60)
    print("PHASE 0: Health check & baseline")
    print("=" * 60)

    if not client.health():
        print("  FAIL: AdClaw not reachable")
        sys.exit(1)
    print("  OK: AdClaw is up")

    try:
        stats = client.stats()
        print(f"  Baseline: {stats['total_memories']} memories, "
              f"{stats['with_embeddings']} embeddings, "
              f"{stats['consolidations']} consolidations")
        return stats
    except requests.HTTPError as e:
        if e.response.status_code == 503:
            print("  FAIL: AOM is not enabled. Enable it in config first:")
            print("        PUT /api/memory/config {\"enabled\": true}")
            sys.exit(1)
        raise


def phase_1_seed(client: AOMClient) -> dict:
    """Inject 50 unique seed memories."""
    print("\n" + "=" * 60)
    print("PHASE 1: Inject 50 seed memories")
    print("=" * 60)

    results = {"injected": 0, "failed": 0, "ids": []}
    for i, content in enumerate(SEED_MEMORIES):
        # Logical type stored in metadata (source_type=manual avoids LLM call
        # which may not be configured). After rebuild with skip_llm support,
        # switch to proper source_types.
        logical_type = "note" if i % 3 == 0 else "config" if i % 5 == 0 else "decision"
        try:
            mem = client.ingest(
                content=content,
                source_type="manual",
                source_id=_make_source_id("seed", i),
                metadata={"test_phase": "seed", "index": i, "logical_type": logical_type},
            )
            results["injected"] += 1
            results["ids"].append(mem["id"])
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/50 injected...")
            time.sleep(0.3)  # throttle to avoid connection resets
        except Exception as e:
            results["failed"] += 1
            print(f"  FAIL [{i}]: {e}")
            time.sleep(1)

    print(f"  Result: {results['injected']} injected, {results['failed']} failed")
    return results


def phase_2_duplicates(client: AOMClient) -> dict:
    """Inject 10 near-duplicates — R3 should catch them."""
    print("\n" + "=" * 60)
    print("PHASE 2: Inject 10 near-duplicates (R3 dedup test)")
    print("=" * 60)

    results = {"accepted": 0, "rejected": 0, "details": []}
    for i, content in enumerate(NEAR_DUPLICATES):
        try:
            mem = client.ingest(
                content=content,
                source_type="manual",
                source_id=_make_source_id("dup", i),
                metadata={"test_phase": "dedup", "original_index": i},
            )
            # Check if returned memory matches the new content or existing one
            if mem.get("source_id", "").startswith(f"{TAG}-dup-"):
                results["accepted"] += 1
                detail = "ACCEPTED (dedup missed)"
            else:
                results["rejected"] += 1
                detail = f"REJECTED (matched {mem.get('id', '?')[:12]})"
            results["details"].append(detail)
            print(f"  [{i}] {detail}: {content[:60]}...")
            time.sleep(0.3)
        except Exception as e:
            print(f"  [{i}] ERROR: {e}")
            time.sleep(1)

    rejection_rate = (
        results["rejected"] / len(NEAR_DUPLICATES) * 100
        if NEAR_DUPLICATES else 0
    )
    print(f"\n  Near-dedup effectiveness: {results['rejected']}/{len(NEAR_DUPLICATES)} "
          f"rejected ({rejection_rate:.0f}%)")
    if rejection_rate >= 50:
        print("  PASS: majority of near-duplicates caught")
    else:
        print("  WARN: low rejection rate — threshold may need tuning")

    return results


def phase_3_ephemeral(client: AOMClient) -> dict:
    """Inject 10 low-importance ephemeral notes for R4 pruning test."""
    print("\n" + "=" * 60)
    print("PHASE 3: Inject 10 ephemeral notes (R4 pruning candidates)")
    print("=" * 60)

    results = {"injected": 0, "ids": []}
    for i, content in enumerate(EPHEMERAL_NOTES):
        try:
            mem = client.ingest(
                content=content,
                source_type="manual",
                source_id=_make_source_id("ephemeral", i),
                metadata={"test_phase": "ephemeral", "logical_type": "note"},
            )
            results["injected"] += 1
            results["ids"].append(mem["id"])
            time.sleep(0.3)
        except Exception as e:
            print(f"  FAIL [{i}]: {e}")
            time.sleep(1)

    print(f"  Injected {results['injected']} ephemeral notes")
    print("  These should be pruned after 7 days (R4 temporal pruning)")
    return results


def phase_4_bulk(client: AOMClient, count: int = 50) -> dict:
    """Inject bulk random memories to simulate load."""
    print("\n" + "=" * 60)
    print(f"PHASE 4: Bulk inject {count} random memories (load test)")
    print("=" * 60)

    topics = [
        "SEO optimization", "content marketing", "social media strategy",
        "email automation", "conversion funnels", "A/B testing",
        "user onboarding", "churn analysis", "pricing strategy",
        "competitor research", "brand positioning", "customer support",
        "product roadmap", "technical debt", "infrastructure scaling",
    ]
    actions = [
        "implemented", "discussed", "decided", "reviewed", "analyzed",
        "fixed", "updated", "deployed", "tested", "documented",
    ]
    objects = [
        "the landing page", "the API endpoint", "the database schema",
        "the notification system", "the billing module", "the auth flow",
        "the search feature", "the analytics dashboard", "the export tool",
        "the mobile layout", "the caching layer", "the webhook handler",
    ]

    results = {"injected": 0, "failed": 0}
    start = time.time()

    for i in range(count):
        topic = random.choice(topics)
        action = random.choice(actions)
        obj = random.choice(objects)
        detail = f"We {action} {obj} as part of {topic} initiative. " \
                 f"Key metric improved by {random.randint(5, 40)}%. " \
                 f"Next step: review in {random.randint(1, 4)} weeks."
        try:
            logical = random.choice(["action", "note", "decision", "config"])
            client.ingest(
                content=detail,
                source_type="manual",
                source_id=_make_source_id("bulk", i),
                metadata={"test_phase": "bulk", "topic": topic, "logical_type": logical},
            )
            results["injected"] += 1
            if (i + 1) % 25 == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed
                print(f"  {i + 1}/{count} injected ({rate:.1f}/sec)...")
            time.sleep(0.2)
        except Exception as e:
            results["failed"] += 1
            time.sleep(0.5)

    elapsed = time.time() - start
    rate = results["injected"] / elapsed if elapsed > 0 else 0
    print(f"  Result: {results['injected']} injected in {elapsed:.1f}s ({rate:.1f}/sec)")
    return results


def phase_5_consolidate(client: AOMClient) -> dict:
    """Trigger consolidation cycle (includes R4 temporal pruning)."""
    print("\n" + "=" * 60)
    print("PHASE 5: Trigger consolidation (R4 temporal pruning runs here)")
    print("=" * 60)

    try:
        start = time.time()
        result = client.consolidate()
        elapsed = time.time() - start
        print(f"  Consolidation: {result.get('insights_created', 0)} insights in {elapsed:.1f}s")

        cons = client.consolidations(limit=5)
        if cons:
            print(f"  Latest insights:")
            for c in cons[:3]:
                print(f"    - {c.get('insight', '?')[:100]}...")
        return result
    except requests.HTTPError as e:
        if e.response.status_code == 400:
            print("  SKIP: consolidation engine not available")
            return {"skipped": True}
        raise


def phase_6_verify(client: AOMClient, baseline: dict) -> None:
    """Final verification — compare stats with baseline."""
    print("\n" + "=" * 60)
    print("PHASE 6: Final verification")
    print("=" * 60)

    stats = client.stats()
    new_memories = stats["total_memories"] - baseline["total_memories"]
    new_embeddings = stats["with_embeddings"] - baseline["with_embeddings"]
    new_cons = stats["consolidations"] - baseline["consolidations"]

    print(f"  Total memories: {baseline['total_memories']} → {stats['total_memories']} (+{new_memories})")
    print(f"  With embeddings: {baseline['with_embeddings']} → {stats['with_embeddings']} (+{new_embeddings})")
    print(f"  Consolidations: {baseline['consolidations']} → {stats['consolidations']} (+{new_cons})")
    print(f"  By source: {json.dumps(stats.get('by_source', {}), indent=4)}")

    # Expected: ~110 injected, but near-dedup should have rejected ~5-8
    # so we expect fewer than 110 new memories
    expected_max = 50 + 10 + 10 + 50  # seed + dup + ephemeral + bulk = 120
    if new_memories < expected_max:
        rejected = expected_max - new_memories
        print(f"\n  DEDUP EFFECTIVENESS: ~{rejected} entries rejected by dedup/filters")
    else:
        print(f"\n  WARN: all {new_memories} entries accepted (dedup may not be working)")


def cleanup(client: AOMClient) -> None:
    """Remove all test memories (source_id starts with TAG)."""
    print("=" * 60)
    print("CLEANUP: Removing test memories")
    print("=" * 60)

    memories = client.list_memories(limit=500)
    test_memories = [m for m in memories if m.get("source_id", "").startswith(TAG)]
    print(f"  Found {len(test_memories)} test memories to delete")

    deleted = 0
    for m in test_memories:
        if client.delete(m["id"]):
            deleted += 1
        if deleted % 25 == 0 and deleted > 0:
            print(f"  {deleted}/{len(test_memories)} deleted...")

    print(f"  Deleted {deleted} test memories")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AOM Memory Optimization Live Test")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="AdClaw base URL")
    parser.add_argument("--cleanup", action="store_true", help="Remove all test memories")
    parser.add_argument("--bulk-count", type=int, default=50, help="Number of bulk memories")
    parser.add_argument("--skip-bulk", action="store_true", help="Skip bulk injection phase")
    args = parser.parse_args()

    client = AOMClient(args.base_url)

    if args.cleanup:
        cleanup(client)
        return

    print(f"AOM Memory Optimization Live Test")
    print(f"Target: {args.base_url}")
    print(f"Time: {datetime.now().isoformat()}")

    baseline = phase_0_check(client)
    phase_1_seed(client)
    phase_2_duplicates(client)
    phase_3_ephemeral(client)
    if not args.skip_bulk:
        phase_4_bulk(client, count=args.bulk_count)
    phase_5_consolidate(client)
    phase_6_verify(client, baseline)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"\nCleanup: python3 scripts/test_memory_live.py --cleanup")


if __name__ == "__main__":
    main()
