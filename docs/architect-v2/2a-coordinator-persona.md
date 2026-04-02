# 2A: Coordinator Persona — Synthesis-Driven Orchestration

## Problem Statement

AdClaw supports multiple personas (`PersonaConfig` in `config.py`) with `@mention` routing via `PersonaManager.resolve_tag()`. Each persona runs independently: a user sends `@seo-expert analyze my site`, the message routes to the SEO persona, and that persona replies in isolation.

There is no synthesis layer. Nobody reads results from multiple persona executions to identify patterns, contradictions, or next steps. Nobody decides when a persona is stuck and should be replaced with a different approach. The `is_coordinator` flag exists on `PersonaConfig` and is validated (only one allowed), but the coordinator has no special runtime behavior — it is just another persona with a different `soul_md`.

The `delegation_executor.py` performs one-shot LLM calls with persona system prompts but has no feedback loop: delegate, get answer, done. No iteration, no synthesis, no strategy.

### What We Lose Without Coordination

1. **Wasted work** — persona A produces results that persona B needs but never sees
2. **No pivots** — a stuck persona keeps retrying the same approach
3. **No strategy** — multi-step campaigns (SEO audit -> content plan -> ad copy) require manual sequencing
4. **No learning** — successful patterns are not captured for reuse

## Design: Synthesis-Driven Orchestration

Inspired by Claude Code's Coordinator Mode. The coordinator does NOT execute skills directly. It reads, thinks, and directs.

### Core Principles

1. **Synthesis-first**: The coordinator reads outputs from persona executions, understands what happened, and produces specific next-step instructions. Generic delegation ("based on results, optimize further") is forbidden — the coordinator must state exactly what to do and why.

2. **Continue vs Pivot**: If a persona is succeeding, the coordinator refines the task. If a persona is stuck or repeating itself, the coordinator pivots to a different approach or a different persona entirely.

3. **Strategy as artifact**: The coordinator produces a `TaskStrategy` object stored in AOM. The next persona execution picks up the strategy from memory, not from a direct message chain.

4. **No skill execution**: The coordinator persona has an empty `skills: []` list. Its only tools are AOM query, AOM write, and the delegation tool.

### Architecture

```
User message (no @mention)
        |
        v
  PersonaManager.resolve_tag() -> None (no tag)
        |
        v
  Is coordinator configured?
   yes /         \ no
      v           v
  Coordinator    Default agent (existing behavior)
  reads AOM
  for recent
  persona
  activity
      |
      v
  Synthesize:
  - What worked?
  - What failed?
  - What's next?
      |
      v
  Emit TaskStrategy
  to AOM
      |
      v
  Route to best-fit
  persona via
  delegation_executor
      |
      v
  Persona executes
  (results auto-captured
   by AOM capture hook)
```

### Cron-Based Coordination Loop

The coordinator runs on a cron schedule (e.g., every 30 minutes). Each cycle:

1. Query AOM for recent persona activity (last N minutes)
2. Identify open strategies and their status
3. Synthesize results into updated strategy
4. Emit next delegation or mark strategy complete

```json
{
  "personas": [
    {
      "id": "coordinator",
      "name": "Coordinator",
      "is_coordinator": true,
      "soul_md": "You are a strategic coordinator...",
      "skills": [],
      "cron": {
        "enabled": true,
        "schedule": "*/30 * * * *",
        "prompt": "Review recent persona activity and update strategies.",
        "output": "chat"
      }
    },
    {
      "id": "seo-expert",
      "name": "SEO Expert",
      "skills": ["seo-audit", "keyword-research", "backlink-analysis"],
      "soul_md": "You are an SEO specialist..."
    },
    {
      "id": "content-writer",
      "name": "Content Writer",
      "skills": ["blog-writer", "social-post-creator"],
      "soul_md": "You are a content strategist..."
    }
  ]
}
```

## Implementation Plan

### 1. TaskStrategy Model

New Pydantic model stored in AOM as a structured memory entry.

```python
# src/adclaw/agents/coordinator/models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PersonaOutcome(BaseModel):
    """Summary of a single persona execution within a strategy."""

    persona_id: str
    task_given: str
    status: Literal["success", "partial", "failed", "stuck", "pending"] = "pending"
    key_findings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    iteration: int = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class NextStep(BaseModel):
    """A specific next action the coordinator has decided on."""

    persona_id: str
    task: str
    rationale: str
    priority: int = 1  # 1 = highest
    depends_on: Optional[str] = None  # forward-looking: persona_id that must finish first


class TaskStrategy(BaseModel):
    """A multi-step strategy the coordinator maintains across cron cycles.

    Stored in AOM with source_type='manual' and metadata
    {"coordinator_strategy": True}. Memory.source_type is a
    Literal enum ("mcp_tool"|"skill"|"chat"|"file_inbox"|"manual"),
    so custom source types are not supported — use metadata instead.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    status: Literal["active", "completed", "abandoned"] = "active"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    outcomes: list[PersonaOutcome] = Field(default_factory=list)
    next_steps: list[NextStep] = Field(default_factory=list)
    synthesis: str = ""  # coordinator's analysis of the current state

    # Pivot tracking
    pivot_count: int = 0
    max_pivots: int = 3  # abandon after N pivots on same goal

    def add_outcome(self, outcome: PersonaOutcome) -> None:
        self.outcomes.append(outcome)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def should_pivot(self, persona_id: str) -> bool:
        """Check if a persona has been stuck/failed enough to warrant a pivot."""
        recent = [
            o for o in self.outcomes
            if o.persona_id == persona_id
            and o.status in ("failed", "stuck")
        ]
        return len(recent) >= 2

    def should_abandon(self) -> bool:
        return self.pivot_count >= self.max_pivots
```

### 2. Coordinator Synthesis Engine

The core logic that reads AOM, builds context, and produces strategy updates.

```python
# src/adclaw/agents/coordinator/synthesis.py
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from .models import TaskStrategy, PersonaOutcome, NextStep

logger = logging.getLogger(__name__)

# Forbidden phrases in coordinator output — forces specificity
FORBIDDEN_PHRASES = [
    "based on results",
    "as appropriate",
    "optimize further",
    "continue as needed",
    "if applicable",
    "when possible",
]

SYNTHESIS_SYSTEM_PROMPT = """\
You are the Coordinator for a team of specialist personas.
Your job is SYNTHESIS — not execution.

## Rules
1. NEVER say "based on results" or "optimize further" — be SPECIFIC.
   BAD: "Based on SEO results, optimize the content."
   GOOD: "The SEO audit found 3 pages with missing H1 tags (/, /pricing, /blog).
          @content-writer: rewrite the H1 for each page targeting these keywords: [list]."

2. For each persona outcome, state:
   - What specifically succeeded or failed
   - Why it matters for the overall goal
   - What EXACT next action to take (persona, task, expected output)

3. If a persona is stuck (same error twice), PIVOT:
   - Try a different persona for the same subtask
   - Or break the subtask into smaller pieces
   - Or abandon and explain why

4. Output valid JSON matching the TaskStrategy schema.

## Team
{team_summary}

## Current Strategy
{current_strategy}

## Recent Activity (from AOM)
{recent_activity}

## Your Task
Analyze the above and produce an updated TaskStrategy JSON with:
- Updated synthesis (your analysis)
- Updated outcomes (mark completed/failed)
- New next_steps (specific tasks for specific personas)
"""


def validate_synthesis(synthesis: str) -> list[str]:
    """Check coordinator output for forbidden vague phrases."""
    violations = []
    lower = synthesis.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lower:
            violations.append(f"Forbidden phrase: '{phrase}'")
    return violations


async def run_synthesis_cycle(
    aom_manager,
    persona_manager,
    chat_model,
    active_strategy: Optional[TaskStrategy] = None,
) -> TaskStrategy:
    """Run one coordinator synthesis cycle.

    1. Query AOM for recent persona activity
    2. Build synthesis prompt
    3. Call LLM for analysis
    4. Parse and validate strategy update
    5. Store updated strategy in AOM

    Args:
        aom_manager: AOM manager with query_agent and ingest_agent
        persona_manager: PersonaManager with team info
        chat_model: LLM model for synthesis
        active_strategy: Current strategy to update, or None to create new

    Returns:
        Updated or new TaskStrategy
    """
    # 1. Query AOM for recent persona activity
    # skip_synthesis=True: we do our own synthesis, no need for AOM's LLM pass
    query_result = await aom_manager.query_agent.query(
        "Recent persona execution results, tool outputs, and task completions "
        "from the last 2 hours",
        skip_synthesis=True,
    )

    recent_activity = ""
    if query_result.citations:
        for citation in query_result.citations:
            mem = citation.memory
            recent_activity += (
                f"[{mem.source_type}:{mem.source_id}] "
                f"({mem.created_at})\n{mem.content}\n\n"
            )
    if not recent_activity:
        recent_activity = "(No recent persona activity found in AOM)"

    # 2. Build synthesis prompt
    team_summary = persona_manager.get_team_summary()
    strategy_json = (
        active_strategy.model_dump_json(indent=2)
        if active_strategy
        else '{"status": "new", "goal": "Determine goal from recent activity"}'
    )

    prompt = SYNTHESIS_SYSTEM_PROMPT.format(
        team_summary=team_summary,
        current_strategy=strategy_json,
        recent_activity=recent_activity,
    )

    # 3. Call LLM
    from agentscope.message import Msg

    response = chat_model([
        Msg(name="system", content=prompt, role="system"),
        Msg(
            name="user",
            content="Analyze the recent activity and produce an updated TaskStrategy.",
            role="user",
        ),
    ])
    response_text = (
        response.content if hasattr(response, "content") else str(response)
    )

    # 4. Parse strategy from response
    strategy = _parse_strategy_from_response(response_text, active_strategy)

    # 5. Validate synthesis quality
    violations = validate_synthesis(strategy.synthesis)
    if violations:
        logger.warning(
            "Coordinator synthesis has %d quality violations: %s",
            len(violations),
            violations,
        )

    # 6. Store in AOM
    # NOTE: IngestAgent.ingest() does not accept topics/importance directly —
    # those are extracted by the LLM step internally. Pass them via metadata
    # for manual override if skip_llm=True. source_type must be a valid
    # Memory Literal; use "manual" and tag via metadata.
    await aom_manager.ingest_agent.ingest(
        content=strategy.model_dump_json(),
        source_type="manual",
        source_id=strategy.id,
        metadata={"coordinator_strategy": True, "strategy_id": strategy.id},
    )

    return strategy


def _parse_strategy_from_response(
    response_text: str,
    fallback: Optional[TaskStrategy] = None,
) -> TaskStrategy:
    """Extract TaskStrategy JSON from LLM response text."""
    # Try to find JSON block in response
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
    else:
        # Try raw JSON parse
        raw = response_text.strip()

    try:
        data = json.loads(raw)
        return TaskStrategy(**data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse strategy JSON: %s", exc)
        if fallback:
            # Don't mutate the original fallback — create a copy with error info
            error_strategy = fallback.model_copy(update={
                "synthesis": f"[Parse error — raw LLM output]\n{response_text[:2000]}"
            })
            return error_strategy
        return TaskStrategy(
            goal="Unable to determine",
            synthesis=f"[Parse error]\n{response_text[:2000]}",
        )
```

### 3. Coordinator Cron Handler

Integrates with the existing persona cron system (`persona_sync.py`).

```python
# src/adclaw/agents/coordinator/cron_handler.py
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from .models import PersonaOutcome, TaskStrategy
from .synthesis import run_synthesis_cycle
from ..persona_manager import PersonaManager
from ..tools.delegation_executor import execute_delegation

logger = logging.getLogger(__name__)


async def coordinator_cron_tick(
    persona_manager: PersonaManager,
    aom_manager,
    chat_model,
) -> str:
    """Execute one coordinator cron cycle.

    Called by the cron system when the coordinator's schedule fires.

    Returns:
        Human-readable summary of what the coordinator decided.
    """
    coordinator = persona_manager.get_coordinator()
    if coordinator is None:
        return "No coordinator persona configured."

    # Load active strategy from AOM
    active_strategy = await _load_active_strategy(aom_manager)

    # Run synthesis
    strategy = await run_synthesis_cycle(
        aom_manager=aom_manager,
        persona_manager=persona_manager,
        chat_model=chat_model,
        active_strategy=active_strategy,
    )

    # Check for abandonment
    if strategy.should_abandon():
        strategy.status = "abandoned"
        logger.warning(
            "Strategy '%s' abandoned after %d pivots",
            strategy.id,
            strategy.pivot_count,
        )
        return f"Strategy abandoned: {strategy.goal} (too many pivots)"

    # Execute next steps, tracking which ones were actually executed
    results = []
    executed_indices: set[int] = set()
    for idx, step in enumerate(strategy.next_steps):
        persona = persona_manager.get_persona(step.persona_id)
        if persona is None:
            logger.warning("Unknown persona '%s' in next_steps", step.persona_id)
            executed_indices.add(idx)  # remove invalid steps
            continue

        if step.depends_on:
            # Check if dependency is met
            dep_outcomes = [
                o for o in strategy.outcomes
                if o.persona_id == step.depends_on and o.status == "success"
            ]
            if not dep_outcomes:
                logger.debug(
                    "Skipping step for %s — waiting on %s",
                    step.persona_id,
                    step.depends_on,
                )
                continue  # NOT marked as executed — preserve for next cycle

        executed_indices.add(idx)

        logger.info(
            "Coordinator delegating to @%s: %s",
            step.persona_id,
            step.task[:120],
        )
        # execute_delegation is sync — run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, execute_delegation, persona, step.task, persona_manager
        )

        # Detect failure by checking for the "Delegation failed:" prefix
        # that execute_delegation returns on exception
        outcome_status = "failed" if result.startswith("Delegation failed:") else "success"
        strategy.add_outcome(PersonaOutcome(
            persona_id=step.persona_id,
            task_given=step.task,
            status=outcome_status,
            key_findings=[result[:500]],
        ))
        results.append(f"@{step.persona_id}: {outcome_status}")

    # Remove executed/invalid steps; preserve deferred steps with unmet depends_on
    strategy.next_steps = [
        s for idx, s in enumerate(strategy.next_steps)
        if idx not in executed_indices
    ]

    # Persist updated strategy
    await aom_manager.ingest_agent.ingest(
        content=strategy.model_dump_json(),
        source_type="manual",
        source_id=strategy.id,
        metadata={"coordinator_strategy": True, "strategy_id": strategy.id},
    )

    summary = (
        f"Strategy: {strategy.goal}\n"
        f"Synthesis: {strategy.synthesis[:300]}\n"
        f"Delegations: {'; '.join(results) if results else 'none (waiting)'}"
    )
    return summary


async def _load_active_strategy(aom_manager) -> Optional[TaskStrategy]:
    """Load the most recent active strategy from AOM.

    Iterates all citations and returns the active strategy with the
    latest updated_at timestamp, not just the first one found.
    """
    try:
        result = await aom_manager.query_agent.query(
            "coordinator strategy active",
            skip_synthesis=True,
        )
        candidates: list[TaskStrategy] = []
        for citation in result.citations:
            mem = citation.memory
            if mem.metadata.get("coordinator_strategy"):
                try:
                    data = json.loads(mem.content)
                    strategy = TaskStrategy(**data)
                    if strategy.status == "active":
                        candidates.append(strategy)
                except (json.JSONDecodeError, ValueError):
                    continue
        if candidates:
            # Return the newest strategy by updated_at timestamp
            return max(candidates, key=lambda s: s.updated_at)
    except Exception as exc:
        logger.warning("Failed to load active strategy: %s", exc)
    return None
```

### 4. Integration with PersonaManager

Minimal changes to existing code.

```python
# Changes to src/adclaw/agents/persona_manager.py

class PersonaManager:
    # ... existing code ...

    def route_message(self, text: str) -> tuple[str | None, str]:
        """Route a message to the appropriate persona.

        Returns (persona_id, cleaned_text).
        If no @mention and a coordinator exists, routes to coordinator.
        If no @mention and no coordinator, returns (None, text) for default agent.
        """
        # Check for explicit @mention
        persona_id = self.resolve_tag(text)
        if persona_id is not None:
            return persona_id, self.strip_tag(text)

        # No @mention — route to coordinator if configured
        coordinator = self.get_coordinator()
        if coordinator is not None:
            return coordinator.id, text

        # No coordinator, no mention — default agent handles it
        return None, text
```

### 5. Coordinator Persona Config in PersonaConfig

Already exists — `is_coordinator: bool = False` on `PersonaConfig` with single-coordinator validation. No changes needed to the model.

The coordinator differs at runtime:
- Empty `skills: []` (no direct tool execution)
- System prompt includes synthesis instructions via `soul_md`
- Cron-driven (not user-message-driven, though it can respond to direct `@coordinator` mentions)

### 6. Wire Into Cron System

```python
# Changes to src/adclaw/app/crons/persona_sync.py

def build_persona_cron_jobs(personas: list[PersonaConfig]) -> list[dict]:
    """Build cron job specifications from persona configs."""
    jobs = []
    for persona in personas:
        if not persona.cron or not persona.cron.enabled:
            continue
        if not persona.cron.schedule or not persona.cron.prompt:
            continue

        job = {
            "id": f"persona_{persona.id}",
            "name": f"Persona: {persona.name}",
            "enabled": True,
            "schedule": persona.cron.schedule,
            "prompt": persona.cron.prompt,
            "persona_id": persona.id,
            "output_mode": persona.cron.output,
        }

        # Coordinator gets a special handler
        if persona.is_coordinator:
            job["handler"] = "coordinator_cron_tick"

        jobs.append(job)
    return jobs
```

## Cost Analysis

### LLM Calls Per Coordinator Cycle

| Step | Calls | Tokens (est.) |
|------|-------|---------------|
| AOM query (embedding only, skip_synthesis=True) | 0 LLM | ~0 |
| Load active strategy (embedding only) | 0 LLM | ~0 |
| Coordinator synthesis prompt | 1 LLM | ~2K input + ~1K output |
| Per delegation (1-3 per cycle) | 1-3 LLM | ~1.5K each |
| **Total per cycle** | **2-4 LLM** | **~5-7.5K tokens** |

### With `glm-5` at Aliyun Coding Plan Pricing

- 30-minute cron = 48 cycles/day
- ~6K tokens/cycle = ~288K tokens/day
- At Coding Plan rates: effectively free (included in plan)

### Without Coordinator (Status Quo)

- Zero synthesis overhead
- But: manual sequencing, no automatic pivots, wasted persona runs

### Break-Even

The coordinator pays for itself if it prevents even one wasted persona execution per day (each persona run costs ~1.5K tokens and human attention to trigger the next step).

## Testing Strategy

### Unit Tests

```python
# tests/test_coordinator_models.py
import pytest
from adclaw.agents.coordinator.models import (
    TaskStrategy,
    PersonaOutcome,
    NextStep,
)


class TestTaskStrategy:
    def test_create_strategy(self):
        strategy = TaskStrategy(goal="Improve SEO for /pricing page")
        assert strategy.status == "active"
        assert strategy.pivot_count == 0
        assert strategy.outcomes == []
        assert strategy.next_steps == []

    def test_add_outcome(self):
        strategy = TaskStrategy(goal="test")
        outcome = PersonaOutcome(
            persona_id="seo-expert",
            task_given="Audit /pricing page",
            status="success",
            key_findings=["Missing H1 tag", "No meta description"],
        )
        strategy.add_outcome(outcome)
        assert len(strategy.outcomes) == 1
        assert strategy.outcomes[0].persona_id == "seo-expert"

    def test_should_pivot_after_two_failures(self):
        strategy = TaskStrategy(goal="test")
        strategy.add_outcome(PersonaOutcome(
            persona_id="seo-expert",
            task_given="task1",
            status="failed",
        ))
        assert not strategy.should_pivot("seo-expert")

        strategy.add_outcome(PersonaOutcome(
            persona_id="seo-expert",
            task_given="task2",
            status="failed",
        ))
        assert strategy.should_pivot("seo-expert")

    def test_should_not_pivot_different_persona(self):
        strategy = TaskStrategy(goal="test")
        strategy.add_outcome(PersonaOutcome(
            persona_id="seo-expert",
            task_given="task1",
            status="failed",
        ))
        strategy.add_outcome(PersonaOutcome(
            persona_id="content-writer",
            task_given="task2",
            status="failed",
        ))
        assert not strategy.should_pivot("seo-expert")

    def test_should_abandon_after_max_pivots(self):
        strategy = TaskStrategy(goal="test", max_pivots=3)
        strategy.pivot_count = 3
        assert strategy.should_abandon()

    def test_serialization_roundtrip(self):
        strategy = TaskStrategy(
            goal="SEO campaign",
            synthesis="Found 3 issues",
            next_steps=[
                NextStep(
                    persona_id="content-writer",
                    task="Rewrite H1 tags",
                    rationale="SEO audit found missing H1s",
                ),
            ],
        )
        json_str = strategy.model_dump_json()
        restored = TaskStrategy.model_validate_json(json_str)
        assert restored.goal == strategy.goal
        assert len(restored.next_steps) == 1


class TestValidateSynthesis:
    def test_catches_forbidden_phrases(self):
        from adclaw.agents.coordinator.synthesis import validate_synthesis

        violations = validate_synthesis(
            "Based on results, optimize further as appropriate."
        )
        assert len(violations) == 3

    def test_passes_specific_synthesis(self):
        from adclaw.agents.coordinator.synthesis import validate_synthesis

        violations = validate_synthesis(
            "The /pricing page is missing an H1 tag. "
            "@content-writer should add 'Enterprise Pricing Plans' as H1."
        )
        assert len(violations) == 0
```

### Integration Tests

```python
# tests/test_coordinator_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from adclaw.agents.coordinator.cron_handler import coordinator_cron_tick
from adclaw.agents.coordinator.models import TaskStrategy
from adclaw.agents.persona_manager import PersonaManager
from adclaw.config.config import PersonaConfig


@pytest.fixture
def personas():
    return [
        PersonaConfig(
            id="coordinator",
            name="Coordinator",
            is_coordinator=True,
            soul_md="You coordinate the team.",
        ),
        PersonaConfig(
            id="seo-expert",
            name="SEO Expert",
            soul_md="You are an SEO specialist.",
            skills=["seo-audit"],
        ),
    ]


@pytest.fixture
def persona_manager(personas):
    return PersonaManager(working_dir="/tmp/test-adclaw", personas=personas)


@pytest.fixture
def mock_aom():
    aom = MagicMock()
    aom.query_agent = AsyncMock()
    aom.query_agent.query = AsyncMock(return_value=MagicMock(
        citations=[], consolidations=[], answer=""
    ))
    aom.ingest_agent = AsyncMock()
    aom.ingest_agent.ingest = AsyncMock()
    return aom


@pytest.fixture
def mock_chat_model():
    model = MagicMock()
    strategy = TaskStrategy(
        goal="Test goal",
        synthesis="Specific finding: page /about has no meta description.",
        next_steps=[],
    )
    model.return_value = MagicMock(content=f"```json\n{strategy.model_dump_json()}\n```")
    return model


@pytest.mark.asyncio
async def test_coordinator_cron_no_coordinator(persona_manager, mock_aom, mock_chat_model):
    """When no coordinator configured, return early."""
    pm = PersonaManager(working_dir="/tmp/test", personas=[
        PersonaConfig(id="seo", name="SEO", soul_md="test"),
    ])
    result = await coordinator_cron_tick(pm, mock_aom, mock_chat_model)
    assert "No coordinator" in result


@pytest.mark.asyncio
async def test_coordinator_cron_runs_synthesis(
    persona_manager, mock_aom, mock_chat_model
):
    """Coordinator cron runs synthesis and stores strategy."""
    result = await coordinator_cron_tick(
        persona_manager, mock_aom, mock_chat_model
    )
    assert "Strategy:" in result
    # Verify AOM ingest was called
    mock_aom.ingest_agent.ingest.assert_called()


@pytest.mark.asyncio
async def test_coordinator_delegates_next_steps(persona_manager, mock_aom):
    """Coordinator executes delegations for next_steps."""
    strategy = TaskStrategy(
        goal="Fix SEO",
        synthesis="Found issues.",
        next_steps=[{
            "persona_id": "seo-expert",
            "task": "Audit /pricing page for H1 tags",
            "rationale": "Missing H1 detected in crawl",
        }],
    )
    model = MagicMock()
    model.return_value = MagicMock(
        content=f"```json\n{strategy.model_dump_json()}\n```"
    )

    with patch(
        "adclaw.agents.coordinator.cron_handler.execute_delegation",
        return_value="Found 2 missing H1 tags on /pricing",
    ) as mock_deleg:
        result = await coordinator_cron_tick(
            persona_manager, mock_aom, model
        )
        mock_deleg.assert_called_once()
        assert "seo-expert" in result
```

### Manual Smoke Test

```bash
# 1. Add coordinator to config.json
cat >> /tmp/test-config.json << 'EOF'
{
  "agents": {
    "personas": [
      {
        "id": "coordinator",
        "name": "Coordinator",
        "is_coordinator": true,
        "soul_md": "You coordinate the marketing team. Be specific.",
        "skills": [],
        "cron": {
          "enabled": true,
          "schedule": "*/30 * * * *",
          "prompt": "Review recent activity and update strategies."
        }
      },
      {
        "id": "seo-expert",
        "name": "SEO Expert",
        "soul_md": "You specialize in technical SEO audits.",
        "skills": ["seo-audit", "keyword-research"]
      }
    ]
  }
}
EOF

# 2. Verify config validation
python3 -c "
from adclaw.config.config import AgentsConfig, PersonaConfig
import json
with open('/tmp/test-config.json') as f:
    data = json.load(f)
config = AgentsConfig(**data['agents'])
print(f'Personas: {len(config.personas)}')
print(f'Coordinator: {[p.id for p in config.personas if p.is_coordinator]}')
"

# 3. Run coordinator cycle manually (requires AOM + LLM)
python3 -c "
import asyncio
from adclaw.agents.coordinator.cron_handler import coordinator_cron_tick
# ... setup aom_manager, persona_manager, chat_model ...
# result = asyncio.run(coordinator_cron_tick(...))
print('Manual test requires running AOM instance')
"
```

## File Layout

```
src/adclaw/agents/coordinator/
    __init__.py
    models.py          # TaskStrategy, PersonaOutcome, NextStep
    synthesis.py        # run_synthesis_cycle, validate_synthesis
    cron_handler.py     # coordinator_cron_tick
```

## Migration Path

1. **Phase 1 (this doc)**: Coordinator as cron job. Reads AOM, writes strategies, delegates via `execute_delegation`. No changes to message routing.

2. **Phase 2**: Coordinator intercepts untagged messages (the `route_message` method above). User sends "improve my SEO" without @mention, coordinator decides which persona handles it.

3. **Phase 3**: Multi-turn coordination. Coordinator maintains conversation context across multiple cron cycles, building up a campaign strategy over hours/days.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Coordinator produces vague instructions | `validate_synthesis()` checks for forbidden phrases; log warnings |
| Infinite delegation loops | `max_pivots=3` on TaskStrategy; `should_abandon()` check |
| AOM query returns stale data | Strategy has `updated_at`; synthesis prompt includes timestamps |
| LLM fails to produce valid JSON | `_parse_strategy_from_response` with fallback; raw output preserved |
| Coordinator cost exceeds budget | 48 cycles/day at ~6K tokens = ~288K tokens; free on Coding Plan |
| Coordinator conflicts with user's @mention | Explicit @mention always wins over coordinator routing |
