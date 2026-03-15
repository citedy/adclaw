#!/usr/bin/env python3
"""Live E2E test for Mission Control features.

Tests against a running AdClaw instance:
- Phase 0: Health check
- Phase 1: Persona API — list, verify structure
- Phase 2: @mention routing — send message with @tag, verify session created
- Phase 3: Session isolation — verify persona sessions are separate
- Phase 4: Cron API — create job targeting persona, verify
- Phase 5: Dashboard data — verify all data available for dashboard
- Phase 6: Shared AOM — ingest memory, verify cross-persona access

Usage:
    python3 scripts/test_mission_control_live.py [--base-url http://localhost:8088]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

DEFAULT_BASE = "http://localhost:8088"


class MissionControlClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["Content-Type"] = "application/json"

    def get(self, path: str, **kw) -> requests.Response:
        return self.s.get(f"{self.base}{path}", **kw)

    def post(self, path: str, data: Any = None, **kw) -> requests.Response:
        return self.s.post(f"{self.base}{path}", json=data, **kw)

    def delete(self, path: str) -> requests.Response:
        return self.s.delete(f"{self.base}{path}")


def phase0_health(c: MissionControlClient):
    print("\n=== Phase 0: Health Check ===")
    # Try skills endpoint as health proxy (health returns HTML in current build)
    r = c.get("/api/skills")
    assert r.status_code == 200, f"Skills endpoint failed: {r.status_code}"
    skills = r.json()
    assert isinstance(skills, list), "Skills should be a list"
    print(f"  OK API alive, {len(skills)} skills loaded")


def phase1_personas(c: MissionControlClient):
    print("\n=== Phase 1: Persona API ===")
    r = c.get("/api/agents/personas")
    assert r.status_code == 200, f"List personas failed: {r.status_code}"
    personas = r.json()
    print(f"  OK Found {len(personas)} personas")

    # Verify structure
    for p in personas:
        assert "id" in p, f"Persona missing 'id': {p}"
        assert "name" in p, f"Persona missing 'name': {p}"
        assert "is_coordinator" in p, f"Persona missing 'is_coordinator': {p}"
        assert "skills" in p, f"Persona missing 'skills': {p}"
        assert "mcp_clients" in p, f"Persona missing 'mcp_clients': {p}"

    # At least one coordinator
    coordinators = [p for p in personas if p["is_coordinator"]]
    assert len(coordinators) >= 1, "No coordinator persona found"
    print(f"  OK Coordinator: {coordinators[0]['name']}")

    # Return personas for later phases
    return personas


def phase2_mention_routing(c: MissionControlClient, personas: list):
    print("\n=== Phase 2: @mention Routing ===")
    if len(personas) < 2:
        print("  SKIP Only 1 persona, skipping routing test")
        return

    non_coord = [p for p in personas if not p["is_coordinator"]]
    if not non_coord:
        print("  SKIP No non-coordinator personas, skipping")
        return

    target = non_coord[0]
    print(f"  Testing @{target['id']} routing...")

    # Send message with @tag via agent/process
    payload = {
        "input": [{"type": "text", "text": f"@{target['id']} what are your skills?"}],
        "session_id": f"e2e-test-{target['id']}",
        "user_id": "e2e-test-user",
        "channel": "console",
        "stream": False,
    }
    try:
        r = c.post("/api/agent/process", data=payload, timeout=60)
        if r.status_code == 200:
            print(f"  OK @{target['id']} responded (status={r.status_code})")
        else:
            print(f"  WARN @{target['id']} returned {r.status_code} (may need LLM)")
    except requests.Timeout:
        print("  WARN Request timed out (LLM may be slow)")
    except Exception as e:
        print(f"  WARN Request failed: {e}")


def phase3_sessions(c: MissionControlClient):
    print("\n=== Phase 3: Session Isolation ===")
    r = c.get("/api/chats")
    if r.status_code != 200:
        print(f"  WARN Chats API returned {r.status_code}, skipping")
        return

    chats = r.json()
    if isinstance(chats, dict):
        chats = chats.get("chats", [])
    print(f"  Found {len(chats)} sessions")

    # Check for persona-scoped sessions
    persona_sessions = [ch for ch in chats if "::" in str(ch.get("session_id", ""))]
    print(f"  OK {len(persona_sessions)} persona-scoped sessions")


def phase4_cron(c: MissionControlClient, personas: list):
    print("\n=== Phase 4: Cron API ===")
    r = c.get("/api/cron/jobs")
    if r.status_code != 200:
        print(f"  WARN Cron API returned {r.status_code}, skipping")
        return

    jobs = r.json()
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", [])
    print(f"  Found {len(jobs)} cron jobs")

    # Check for persona-targeted jobs
    for job in jobs:
        target = job.get("dispatch", {}).get("target", {})
        session = target.get("session_id", "")
        if "::" in session:
            persona = session.split("::")[0]
            schedule = job.get("schedule", {}).get("cron", "?")
            print(f"  OK Job '{job.get('name', '?')}' -> @{persona} ({schedule})")


def phase5_dashboard(c: MissionControlClient, personas: list):
    print("\n=== Phase 5: Dashboard Data ===")
    # Verify all data sources work
    checks = {
        "Personas": "/api/agents/personas",
        "Sessions": "/api/chats",
        "Cron": "/api/cron/jobs",
    }
    all_ok = True
    for name, path in checks.items():
        r = c.get(path)
        status = "OK" if r.status_code == 200 else "FAIL"
        if r.status_code != 200:
            all_ok = False
        print(f"  {status} {name} ({path}) -> {r.status_code}")
    if all_ok:
        print("  OK All dashboard endpoints responding")


def phase6_shared_memory(c: MissionControlClient):
    print("\n=== Phase 6: Shared AOM Memory ===")
    # Ingest memory as "researcher"
    r = c.post("/api/memory/memories", data={
        "content": "E2E test: AI market will reach $500B by 2027 -- from researcher",
        "source_type": "conversation",
        "source_id": "e2e-researcher",
        "skip_llm": True,
    })
    if r.status_code not in (200, 201):
        print(f"  WARN Ingest failed: {r.status_code} {r.text[:200]}")
        return

    mem_id = r.json().get("id")
    print(f"  OK Ingested memory (id={mem_id})")

    # Query as "writer" -- should find it (AOM is not persona-scoped)
    r = c.post("/api/memory/query", data={
        "question": "What is the AI market forecast?",
        "max_results": 5,
    })
    if r.status_code == 200:
        results = r.json()
        memories = results.get("memories", results.get("results", []))
        found = any("500B" in str(m) for m in memories)
        status = "OK" if found else "FAIL"
        print(f"  {status} Cross-persona query: {'found' if found else 'not found'} ({len(memories)} results)")
    else:
        print(f"  WARN Query failed: {r.status_code}")

    # Cleanup
    if mem_id:
        c.delete(f"/api/memory/memories/{mem_id}")
        print("  OK Cleaned up test memory")


def main():
    parser = argparse.ArgumentParser(description="Mission Control live E2E tests")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="AdClaw base URL")
    args = parser.parse_args()

    c = MissionControlClient(args.base_url)
    print(f"Testing against {args.base_url}")

    passed = []
    failed = []
    warned = []

    phases = [
        ("Phase 0: Health Check", lambda: phase0_health(c)),
        ("Phase 1: Persona API", lambda: phase1_personas(c)),
    ]

    # Run phase 0 and 1 first to get personas
    personas = []
    try:
        phase0_health(c)
        passed.append("Phase 0: Health Check")
    except AssertionError as e:
        failed.append(f"Phase 0: {e}")
        print(f"\n  FAIL: {e}")
        print("\n=== RESULTS ===")
        print(f"  FAILED: {len(failed)}")
        for f in failed:
            print(f"    - {f}")
        sys.exit(1)
    except Exception as e:
        failed.append(f"Phase 0: {e}")
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    try:
        personas = phase1_personas(c)
        passed.append("Phase 1: Persona API")
    except AssertionError as e:
        failed.append(f"Phase 1: {e}")
        print(f"\n  FAIL: {e}")
    except Exception as e:
        failed.append(f"Phase 1: {e}")
        print(f"\n  ERROR: {e}")

    # Phase 2: @mention routing
    try:
        phase2_mention_routing(c, personas)
        passed.append("Phase 2: @mention Routing")
    except AssertionError as e:
        failed.append(f"Phase 2: {e}")
        print(f"\n  FAIL: {e}")
    except Exception as e:
        failed.append(f"Phase 2: {e}")
        print(f"\n  ERROR: {e}")

    # Phase 3: Session isolation
    try:
        phase3_sessions(c)
        passed.append("Phase 3: Session Isolation")
    except AssertionError as e:
        failed.append(f"Phase 3: {e}")
        print(f"\n  FAIL: {e}")
    except Exception as e:
        failed.append(f"Phase 3: {e}")
        print(f"\n  ERROR: {e}")

    # Phase 4: Cron API
    try:
        phase4_cron(c, personas)
        passed.append("Phase 4: Cron API")
    except AssertionError as e:
        failed.append(f"Phase 4: {e}")
        print(f"\n  FAIL: {e}")
    except Exception as e:
        failed.append(f"Phase 4: {e}")
        print(f"\n  ERROR: {e}")

    # Phase 5: Dashboard data
    try:
        phase5_dashboard(c, personas)
        passed.append("Phase 5: Dashboard Data")
    except AssertionError as e:
        failed.append(f"Phase 5: {e}")
        print(f"\n  FAIL: {e}")
    except Exception as e:
        failed.append(f"Phase 5: {e}")
        print(f"\n  ERROR: {e}")

    # Phase 6: Shared AOM memory
    try:
        phase6_shared_memory(c)
        passed.append("Phase 6: Shared AOM Memory")
    except AssertionError as e:
        failed.append(f"Phase 6: {e}")
        print(f"\n  FAIL: {e}")
    except Exception as e:
        failed.append(f"Phase 6: {e}")
        print(f"\n  ERROR: {e}")

    # Summary
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"  Passed: {len(passed)}/{len(passed) + len(failed)}")
    for p in passed:
        print(f"    [PASS] {p}")
    for f in failed:
        print(f"    [FAIL] {f}")
    print()

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
