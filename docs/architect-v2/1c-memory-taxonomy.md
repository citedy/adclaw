# 1C: Memory Type Taxonomy

## Problem Statement

The current AOM (Always-On Memory) stores every memory as a flat `Memory` entry with `topics`, `entities`, and `importance` but **no type classification**. All memories are structurally identical regardless of whether they represent a user preference, a project deadline, a behavioral correction, or a link to an external resource.

This causes three concrete problems:

1. **Retrieval noise** -- when the agent searches for "how should I write emails," it gets project facts, reference links, and user preferences jumbled together with equal weight.
2. **Incorrect consolidation** -- `ConsolidationEngine` clusters memories by embedding similarity alone. A feedback correction ("Never use emojis in emails") can be merged with a project fact ("Email campaign launched March 10") because both mention "email."
3. **No decay/priority model** -- feedback corrections should persist indefinitely and rank higher during active tasks, while completed project context should decay. Without types, there is no lever to implement this.

### Current Memory Model (baseline)

From `src/adclaw/memory_agent/models.py`:

```python
class Memory(BaseModel):
    id: str = Field(default_factory=_uuid4)
    content: str
    content_hash: str = ""
    source_type: Literal["mcp_tool", "skill", "chat", "file_inbox", "manual"] = "manual"
    source_id: str = ""
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    importance: float = 0.5
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    is_deleted: int = 0
    last_consolidated_at: Optional[str] = None
```

Note: `source_type` describes *where* the memory came from (tool call, chat, file). It does NOT describe *what kind* of knowledge the memory represents. The taxonomy adds that missing dimension.

---

## Design: Four Memory Types

### 1. `user` -- User Preferences, Goals, Knowledge

Persistent facts about the user that do not expire.

| Field | Example |
|-------|---------|
| content | "User prefers formal tone in all client communications" |
| entities | ["client communications"] |
| topics | ["writing-style", "preferences"] |

**Signals for classification:**
- Contains "I prefer", "I like", "I want", "always use", "my style"
- Describes personal knowledge, expertise, or background
- References recurring preferences across sessions

### 2. `feedback` -- Behavioral Corrections

Rules the agent must follow. Highest retrieval priority during active tasks. Never consolidated with other types.

| Field | Example |
|-------|---------|
| content | "Don't use emojis in emails. Client considers them unprofessional. Strip emojis before sending." |

**Internal structure** (stored in `metadata.feedback_structure`):
```json
{
  "rule": "No emojis in emails",
  "reason": "Client considers them unprofessional",
  "application": "Strip emojis before sending any email draft"
}
```

**Signals for classification:**
- Contains "don't", "never", "stop doing", "wrong", "instead of"
- Follows a correction event (user rejected agent output)
- References specific agent behavior to change

### 3. `project` -- Ongoing Work Context

Time-bound facts about current work. Relative dates are converted to absolute dates at ingest time.

| Field | Example |
|-------|---------|
| content | "Campaign deadline is 2026-03-15. Budget approved for $5000." |
| entities | ["campaign", "$5000"] |
| topics | ["deadline", "budget"] |

**Date normalization:** "next Friday" ingested on 2026-03-10 becomes "2026-03-14 (Friday)".

**Signals for classification:**
- Contains dates, deadlines, budgets, status updates
- References specific projects, campaigns, tasks
- Contains "working on", "deadline", "launched", "status"

### 4. `reference` -- Pointers to External Resources

Links, file paths, and document references. Compact -- the content is a pointer, not the full resource.

| Field | Example |
|-------|---------|
| content | "Brand guidelines PDF at https://drive.google.com/file/d/abc123" |
| entities | ["brand guidelines", "drive.google.com"] |

**Signals for classification:**
- Contains URLs, file paths, "see document", "located at"
- Points to external resources rather than containing knowledge inline

### What NOT to Save

The `IngestAgent` should reject or skip content that falls into these categories:

| Category | Example | Reason |
|----------|---------|--------|
| Derivable from conversation | "User just asked about SEO" | Redundant with chat history |
| Temporary task state | "Currently generating paragraph 3" | Ephemeral, no future value |
| Already-completed actions | "Sent the email to client" | Action log, not knowledge |
| Raw LLM output | Full generated article text | Too large, not structured knowledge |
| Duplicate of existing memory | Near-duplicate caught by `ShingleCache` | Already handled by dedup |

---

## Implementation Plan

### Step 1: Extend the Memory Model

```python
# src/adclaw/memory_agent/models.py — add MemoryType and new field

MemoryType = Literal["user", "feedback", "project", "reference"]


class Memory(BaseModel):
    """A single memory entry."""

    id: str = Field(default_factory=_uuid4)
    content: str
    content_hash: str = ""
    memory_type: MemoryType = "user"  # NEW FIELD
    source_type: Literal["mcp_tool", "skill", "chat", "file_inbox", "manual"] = "manual"
    source_id: str = ""
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    importance: float = 0.5
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    is_deleted: int = 0
    last_consolidated_at: Optional[str] = None

    def compute_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()

    def model_post_init(self, _context: Any) -> None:
        if not self.content_hash:
            self.content_hash = self.compute_hash()
```

**Important:** `MemoryType` uses the existing `Literal` import already present in `models.py`. No additional imports needed.

### Step 2: Type Inference in IngestAgent

Add a two-stage classifier: fast keyword heuristic first, LLM fallback for ambiguous cases.

```python
# src/adclaw/memory_agent/type_classifier.py

from __future__ import annotations

import re
from typing import Optional

from .models import MemoryType

# --- Keyword heuristics (fast path) ---

_FEEDBACK_SIGNALS = re.compile(
    r"(?i)\b("
    r"don'?t|never|stop\s+doing|wrong|instead\s+of|"
    r"should\s+not|must\s+not|avoid|"
    r"correction|fix\s+this|not\s+like\s+that"
    r")\b"
)

_REFERENCE_SIGNALS = re.compile(
    r"(?i)("
    r"https?://|www\.|"
    r"/[\w.-]+/[\w.-]+\.\w{1,5}|"  # file paths like /docs/guide.pdf, /var/log/app2.log
    r"see\s+(the\s+)?document|"
    r"located\s+at|link\s+to|"
    r"drive\.google\.com|notion\.so|figma\.com"
    r")"
)

_PROJECT_SIGNALS = re.compile(
    r"(?i)\b("
    r"deadline|due\s+date|launch|milestone|sprint|"
    r"budget|status|working\s+on|campaign|"
    r"\d{4}-\d{2}-\d{2}|"  # ISO dates
    r"next\s+(week|month|friday|monday)|"
    r"by\s+(end\s+of|march|april|may|june)"
    r")\b"
)

_USER_SIGNALS = re.compile(
    r"(?i)\b("
    r"i\s+prefer|i\s+like|i\s+want|my\s+style|"
    r"always\s+use|i\s+usually|"
    r"my\s+background|i\s+know|i\s+am\s+a"
    r")\b"
)


def classify_keyword(content: str) -> Optional[MemoryType]:
    """Fast keyword-based classification. Returns None if ambiguous."""
    scores: dict[MemoryType, int] = {
        "user": 0,
        "feedback": 0,
        "project": 0,
        "reference": 0,
    }

    scores["feedback"] = len(_FEEDBACK_SIGNALS.findall(content))
    scores["reference"] = len(_REFERENCE_SIGNALS.findall(content))
    scores["project"] = len(_PROJECT_SIGNALS.findall(content))
    scores["user"] = len(_USER_SIGNALS.findall(content))

    top = max(scores, key=lambda k: scores[k])
    runner_up = sorted(scores.values(), reverse=True)[1]

    # Only return if clear winner (2+ gap or sole match)
    if scores[top] >= 2 and scores[top] - runner_up >= 2:
        return top
    if scores[top] >= 1 and runner_up == 0:
        return top

    return None  # ambiguous -- needs LLM


# --- LLM classification prompt ---

TYPE_CLASSIFICATION_PROMPT = """Classify this memory into exactly one type.

Types:
- "user": user preferences, goals, personal knowledge (e.g. "I prefer formal tone")
- "feedback": corrections to agent behavior (e.g. "Don't use emojis in emails")
- "project": ongoing work context with dates/status (e.g. "Campaign deadline March 15")
- "reference": pointers to external resources (e.g. "Brand guide at drive.google.com/...")

Memory content:
{content}

Respond with ONLY the type name (user/feedback/project/reference):"""


async def classify_with_llm(
    content: str,
    llm_caller,
) -> MemoryType:
    """LLM-based classification for ambiguous content."""
    prompt = TYPE_CLASSIFICATION_PROMPT.format(content=content[:1500])
    raw = await llm_caller(prompt)
    raw = raw.strip().lower().strip('"').strip("'")

    if raw in ("user", "feedback", "project", "reference"):
        return raw  # type: ignore[return-value]

    # Fallback: extract first matching word
    for t in ("feedback", "reference", "project", "user"):
        if t in raw:
            return t  # type: ignore[return-value]

    return "user"  # safe default


async def classify_memory(
    content: str,
    llm_caller=None,
) -> MemoryType:
    """Two-stage classifier: keyword heuristic, then LLM fallback."""
    result = classify_keyword(content)
    if result is not None:
        return result

    if llm_caller is not None:
        return await classify_with_llm(content, llm_caller)

    return "user"  # no LLM available, default to user
```

### Step 3: Integrate Classification into IngestAgent

```python
# In src/adclaw/memory_agent/ingest.py — changes to ingest() method

from .models import MemoryType
from .type_classifier import classify_memory

async def ingest(
    self,
    content: str,
    source_type: str = "manual",
    source_id: str = "",
    skip_llm: bool = False,
    metadata: Optional[dict] = None,
    memory_type: Optional[MemoryType] = None,  # NEW: allow explicit type
) -> Memory:
    # ... existing sanitization and extraction code ...

    # Type classification (after extraction, before creating Memory)
    if memory_type is None:
        llm = None if skip_llm else self.llm_caller
        memory_type = await classify_memory(content, llm_caller=llm)

    # Extract feedback structure if type is feedback
    if memory_type == "feedback":
        metadata = metadata or {}
        if "feedback_structure" not in metadata and not skip_llm:
            try:
                metadata["feedback_structure"] = await self._extract_feedback_structure(content)
            except Exception:
                pass  # best-effort

    memory = Memory(
        content=content,
        memory_type=memory_type,  # NEW
        source_type=source_type,
        source_id=source_id,
        entities=entities,
        topics=topics,
        importance=importance,
        metadata=metadata or {},
    )
    # ... rest of method unchanged ...


async def _extract_feedback_structure(self, content: str) -> dict:
    """Extract rule/reason/application from feedback content."""
    prompt = (
        "Extract the correction structure from this feedback.\n"
        "Return JSON with keys: rule, reason, application.\n\n"
        f"Feedback: {content[:1000]}\n\nJSON:"
    )
    raw = await self.llm_caller(prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    return json.loads(raw)  # json already imported at top of ingest.py
```

### Step 4: Type-Aware Retrieval in QueryAgent

```python
# In src/adclaw/memory_agent/query.py — changes to query() method

async def query(
    self,
    question: str,
    max_results: int = 10,
    skip_synthesis: bool = False,
    type_filter: Optional[str] = None,       # NEW: filter by type
    boost_feedback: bool = True,              # NEW: boost feedback type
) -> QueryResult:
    # ... existing vector + keyword search ...

    # 4. Fetch full memories (with type filter)
    citations: List[MemorySearchResult] = []
    for doc_id, score in merged[:max_results * 2]:  # fetch extra, filter below
        mem = await self.store.get_memory(doc_id)
        if mem and mem.is_deleted == 0:
            # Apply type filter
            if type_filter and mem.memory_type != type_filter:
                continue

            # Boost feedback memories (they represent rules the agent MUST follow)
            effective_score = score
            if boost_feedback and mem.memory_type == "feedback":
                effective_score *= 1.5

            citations.append(MemorySearchResult(memory=mem, score=effective_score))

    # Re-sort by boosted score
    citations.sort(key=lambda c: c.score, reverse=True)
    citations = citations[:max_results]

    # ... rest unchanged ...
```

### Step 5: Type-Aware Consolidation

The key rule: **never merge memories across types**. A feedback correction and a project fact about the same topic (e.g., "email") must remain separate.

```python
# In src/adclaw/memory_agent/consolidate.py — changes to run_consolidation_cycle()

async def run_consolidation_cycle(self) -> List[Consolidation]:
    memories = await self.store.get_unconsolidated_memories(limit=50)
    if len(memories) < 2:
        return []

    # Group by memory_type FIRST, then cluster within each group
    by_type: dict[str, list[Memory]] = {}
    for mem in memories:
        t = mem.memory_type
        by_type.setdefault(t, []).append(mem)

    all_consolidations = []
    for memory_type, type_memories in by_type.items():
        if len(type_memories) < 2:
            continue

        # Skip feedback — feedback memories should not be consolidated
        if memory_type == "feedback":
            continue

        # Cluster within this type only
        consolidations = await self._cluster_and_consolidate(type_memories)
        all_consolidations.extend(consolidations)

    return all_consolidations
```

### Step 6: Schema Migration

```python
# src/adclaw/memory_agent/store.py — add to _create_tables() or a migration function

_MIGRATION_ADD_MEMORY_TYPE = """
-- Add memory_type column (default 'user' for existing rows)
ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'user';

-- Index for type-filtered queries
CREATE INDEX IF NOT EXISTS idx_memories_type
    ON memories(memory_type, is_deleted);

-- Composite index for type + importance ordering
CREATE INDEX IF NOT EXISTS idx_memories_type_importance
    ON memories(memory_type, importance DESC)
    WHERE is_deleted = 0;
"""


async def migrate_add_memory_type(db: aiosqlite.Connection) -> bool:
    """Add memory_type column if it doesn't exist. Returns True if migration ran."""
    cursor = await db.execute("PRAGMA table_info(memories)")
    columns = [row[1] for row in await cursor.fetchall()]

    if "memory_type" in columns:
        return False  # already migrated

    await db.executescript(_MIGRATION_ADD_MEMORY_TYPE)
    await db.commit()

    logger.info("Migration: added memory_type column to memories table")
    return True
```

The migration is safe to run on an existing database:
- `ALTER TABLE ... ADD COLUMN ... DEFAULT 'user'` backfills all existing rows with `"user"`.
- All existing code that does not pass `memory_type` will continue to work (the column defaults to `"user"`).
- The migration check uses `PRAGMA table_info` so it is idempotent.

### Step 6b: Update Store CRUD for memory_type

The `insert_memory` and `_row_to_memory` methods must include the new column. Without this, `memory_type` is silently dropped on insert and missing on read.

```python
# src/adclaw/memory_agent/store.py — update insert_memory()

# In the INSERT INTO memories SQL, add memory_type to both column list and VALUES:
await self._db.execute(
    """INSERT INTO memories
       (id, content, content_hash, memory_type, source_type, source_id,
        entities, topics, importance, metadata,
        created_at, updated_at, is_deleted, last_consolidated_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        memory.id,
        memory.content,
        memory.content_hash,
        memory.memory_type,       # NEW
        memory.source_type,
        memory.source_id,
        json.dumps(memory.entities),
        json.dumps(memory.topics),
        memory.importance,
        json.dumps(memory.metadata),
        memory.created_at,
        memory.updated_at,
        memory.is_deleted,
        memory.last_consolidated_at,
    ),
)
```

```python
# src/adclaw/memory_agent/store.py — update _row_to_memory()
# Column indices shift: memory_type is at index 3, pushing source_type to 4, etc.

@staticmethod
def _row_to_memory(row) -> Memory:
    return Memory(
        id=row[0],
        content=row[1],
        content_hash=row[2] or "",
        memory_type=row[3] or "user",   # NEW
        source_type=row[4],
        source_id=row[5] or "",
        entities=json.loads(row[6]) if row[6] else [],
        topics=json.loads(row[7]) if row[7] else [],
        importance=float(row[8]),
        metadata=json.loads(row[9]) if row[9] else {},
        created_at=row[10],
        updated_at=row[11],
        is_deleted=int(row[12]),
        last_consolidated_at=row[13],
    )
```

**Note:** If using `aiosqlite.Row` (dict-like access via `row["column_name"]`), index shifts are not an issue. However, the current codebase uses positional indexing (`row[0]`, `row[1]`, ...), so indices must be updated after adding the column to `_create_tables`.

Also update `_create_tables` to include the column in the `CREATE TABLE IF NOT EXISTS` statement for fresh databases:

```sql
-- Add after content_hash line:
memory_type      TEXT NOT NULL DEFAULT 'user',
```

### Step 7: REST API Filters

Add `memory_type` as a query parameter on existing endpoints:

```
GET /api/memory/search?q=email+tone&type=feedback
GET /api/memory/list?type=project&limit=20
POST /api/memory/ingest   body: { "content": "...", "memory_type": "feedback" }
```

The `type` parameter maps to `type_filter` in `QueryAgent.query()` and to SQL `WHERE memory_type = ?` in `MemoryStore` list operations.

### Step 8: Store-Level Type Filtering

```python
# src/adclaw/memory_agent/store.py — new methods

async def list_memories_by_type(
    self,
    memory_type: str,
    limit: int = 50,
    include_deleted: bool = False,
) -> List[Memory]:
    """List memories filtered by type."""
    assert self._db is not None
    where = "WHERE memory_type = ?"
    params: list = [memory_type]
    if not include_deleted:
        where += " AND is_deleted = 0"

    cursor = await self._db.execute(
        f"SELECT * FROM memories {where} ORDER BY importance DESC, created_at DESC LIMIT ?",
        params + [limit],
    )
    rows = await cursor.fetchall()
    return [self._row_to_memory(row) for row in rows]


async def count_by_type(self) -> dict[str, int]:
    """Return memory counts grouped by type."""
    assert self._db is not None
    cursor = await self._db.execute(
        "SELECT memory_type, COUNT(*) FROM memories WHERE is_deleted = 0 GROUP BY memory_type"
    )
    return {row[0]: row[1] for row in await cursor.fetchall()}
```

---

## Prompt Injection Format

When typed memories are injected into the agent's context window, they appear in grouped sections with clear delimiters. This replaces the current flat list.

### Template

```
<memory type="feedback" count="3">
## Behavioral Rules (MUST follow)
- [fb-a1b2] Don't use emojis in emails. Client considers them unprofessional.
- [fb-c3d4] Always convert currencies to USD in reports.
- [fb-e5f6] Never suggest TikTok for B2B clients.
</memory>

<memory type="user" count="2">
## User Context
- [us-1234] User is a digital marketing manager at a SaaS company.
- [us-5678] User prefers formal tone in client communications.
</memory>

<memory type="project" count="2">
## Active Projects
- [pj-abcd] Q2 campaign deadline: 2026-04-15. Budget: $5000. Status: in progress.
- [pj-efgh] Website redesign launching 2026-05-01. Stakeholder: VP Marketing.
</memory>

<memory type="reference" count="1">
## Reference Links
- [rf-9012] Brand guidelines: https://drive.google.com/file/d/abc123
</memory>
```

### Injection Rules

1. **Feedback first.** Always inject feedback memories at the top -- they are behavioral constraints.
2. **Truncate by type.** If context budget is tight, cut `reference` first, then `project`, then `user`. Never cut `feedback`.
3. **Short IDs.** Use `[fb-a1b2]` format (type prefix + first 4 chars of UUID) for citation in agent responses.
4. **Section headers.** The "Behavioral Rules (MUST follow)" header primes the LLM to treat feedback as constraints, not suggestions.

### Implementation

```python
# src/adclaw/memory_agent/prompt_builder.py

from typing import List
from .models import Memory, MemoryType

_TYPE_ORDER: list[MemoryType] = ["feedback", "user", "project", "reference"]

_TYPE_HEADERS: dict[MemoryType, str] = {
    "feedback": "Behavioral Rules (MUST follow)",
    "user": "User Context",
    "project": "Active Projects",
    "reference": "Reference Links",
}

_TYPE_PREFIXES: dict[MemoryType, str] = {
    "feedback": "fb",
    "user": "us",
    "project": "pj",
    "reference": "rf",
}


def build_memory_prompt(
    memories: List[Memory],
    max_tokens: int = 2000,
) -> str:
    """Build typed memory sections for agent context injection.

    Args:
        memories: All retrieved memories (already scored/ranked).
        max_tokens: Approximate token budget (chars / 4).

    Returns:
        Formatted memory prompt string.
    """
    grouped: dict[MemoryType, list[Memory]] = {t: [] for t in _TYPE_ORDER}
    for mem in memories:
        t = mem.memory_type
        if t in grouped:
            grouped[t].append(mem)

    sections = []
    budget = max_tokens * 4  # rough char estimate

    for memory_type in _TYPE_ORDER:
        type_mems = grouped[memory_type]
        if not type_mems:
            continue

        header = _TYPE_HEADERS[memory_type]
        prefix = _TYPE_PREFIXES[memory_type]
        lines = [f"## {header}"]

        for mem in type_mems:
            short_id = f"{prefix}-{mem.id[:4]}"
            line = f"- [{short_id}] {mem.content}"
            if len(line) > 300:
                line = line[:297] + "..."
            lines.append(line)

        section = "\n".join(lines)

        # Budget check -- never cut feedback
        if memory_type != "feedback" and len(section) > budget:
            break
        budget -= len(section)

        sections.append(
            f'<memory type="{memory_type}" count="{len(type_mems)}">\n'
            f"{section}\n"
            f"</memory>"
        )

    return "\n\n".join(sections)
```

---

## Testing Strategy

### Unit Tests

```python
# tests/memory_agent/test_type_classifier.py

import pytest
from adclaw.memory_agent.type_classifier import classify_keyword, classify_memory


class TestKeywordClassifier:
    def test_feedback_detection(self):
        assert classify_keyword("Don't use emojis in emails") == "feedback"
        assert classify_keyword("Never suggest TikTok for B2B") == "feedback"
        assert classify_keyword("Stop doing markdown in Slack messages") == "feedback"

    def test_reference_detection(self):
        assert classify_keyword("Brand guide at https://drive.google.com/abc") == "reference"
        assert classify_keyword("See document at /docs/brand.pdf") == "reference"

    def test_project_detection(self):
        assert classify_keyword("Campaign deadline is 2026-03-15, budget $5000") == "project"
        assert classify_keyword("Working on Q2 launch, milestone next week") == "project"

    def test_user_detection(self):
        assert classify_keyword("I prefer formal tone in all communications") == "user"
        assert classify_keyword("I always use dark mode, my style is minimal") == "user"

    def test_ambiguous_returns_none(self):
        assert classify_keyword("The meeting was productive") is None
        assert classify_keyword("Hello world") is None


class TestClassifyMemory:
    @pytest.mark.asyncio
    async def test_clear_feedback_no_llm_needed(self):
        result = await classify_memory("Don't ever use Comic Sans in presentations")
        assert result == "feedback"

    @pytest.mark.asyncio
    async def test_ambiguous_defaults_to_user(self):
        # No LLM provided, ambiguous content defaults to "user"
        result = await classify_memory("Something about the project")
        assert result == "user"

    @pytest.mark.asyncio
    async def test_llm_fallback(self):
        async def mock_llm(prompt: str) -> str:
            return "project"

        result = await classify_memory("The thing is due soon", llm_caller=mock_llm)
        assert result == "project"
```

### Integration Tests

```python
# tests/memory_agent/test_typed_ingest.py

import pytest
from adclaw.memory_agent.models import Memory


class TestTypedIngest:
    """Integration tests using real IngestAgent with mocked LLM."""

    @pytest.mark.asyncio
    async def test_ingest_assigns_type(self, ingest_agent):
        mem = await ingest_agent.ingest(
            "Don't use emojis in client emails",
            source_type="chat",
        )
        assert mem.memory_type == "feedback"

    @pytest.mark.asyncio
    async def test_explicit_type_override(self, ingest_agent):
        mem = await ingest_agent.ingest(
            "Some ambiguous content",
            memory_type="reference",
        )
        assert mem.memory_type == "reference"

    @pytest.mark.asyncio
    async def test_feedback_gets_structure(self, ingest_agent):
        mem = await ingest_agent.ingest(
            "Never use passive voice. It sounds weak. Rewrite to active voice.",
        )
        assert mem.memory_type == "feedback"
        assert "feedback_structure" in mem.metadata


class TestTypedRetrieval:
    @pytest.mark.asyncio
    async def test_type_filter(self, query_agent, populated_store):
        result = await query_agent.query(
            "email", type_filter="feedback", skip_synthesis=True
        )
        for citation in result.citations:
            assert citation.memory.memory_type == "feedback"

    @pytest.mark.asyncio
    async def test_feedback_boost(self, query_agent, populated_store):
        """Feedback memories should rank higher than same-score project memories."""
        result = await query_agent.query("email tone", skip_synthesis=True)
        # If both feedback and project mention "email", feedback should come first
        types = [c.memory.memory_type for c in result.citations]
        if "feedback" in types and "project" in types:
            assert types.index("feedback") < types.index("project")


class TestConsolidationRespectTypes:
    @pytest.mark.asyncio
    async def test_no_cross_type_merge(self, consolidation_engine, populated_store):
        results = await consolidation_engine.run_consolidation_cycle()
        # Each consolidation should only reference memories of one type
        for cons in results:
            mem_types = set()
            for mid in cons.memory_ids:
                mem = await populated_store.get_memory(mid)
                if mem:
                    mem_types.add(mem.memory_type)
            assert len(mem_types) <= 1, f"Cross-type consolidation: {mem_types}"

    @pytest.mark.asyncio
    async def test_feedback_never_consolidated(self, consolidation_engine, populated_store):
        results = await consolidation_engine.run_consolidation_cycle()
        for cons in results:
            for mid in cons.memory_ids:
                mem = await populated_store.get_memory(mid)
                if mem:
                    assert mem.memory_type != "feedback"
```

### Migration Test

```python
# tests/memory_agent/test_migration.py

import pytest
import aiosqlite
from adclaw.memory_agent.store import migrate_add_memory_type


@pytest.mark.asyncio
async def test_migration_adds_column(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(str(db_path)) as db:
        # Create table WITHOUT memory_type (simulates old schema)
        await db.execute("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_hash TEXT,
                source_type TEXT NOT NULL DEFAULT 'manual',
                source_id TEXT DEFAULT '',
                entities TEXT DEFAULT '[]',
                topics TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_deleted INTEGER DEFAULT 0,
                last_consolidated_at TEXT
            )
        """)
        # Insert a pre-existing memory
        await db.execute(
            "INSERT INTO memories (id, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("old-mem-1", "Legacy memory", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        await db.commit()

        # Run migration
        ran = await migrate_add_memory_type(db)
        assert ran is True

        # Verify column exists and default is 'user'
        cursor = await db.execute("SELECT memory_type FROM memories WHERE id = ?", ("old-mem-1",))
        row = await cursor.fetchone()
        assert row[0] == "user"

        # Idempotent — second run is no-op
        ran2 = await migrate_add_memory_type(db)
        assert ran2 is False


@pytest.mark.asyncio
async def test_migration_index_created(tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        await migrate_add_memory_type(db)

        cursor = await db.execute("PRAGMA index_list(memories)")
        indexes = [row[1] for row in await cursor.fetchall()]
        assert "idx_memories_type" in indexes
        assert "idx_memories_type_importance" in indexes
```

---

## File Manifest

| File | Status | Description |
|------|--------|-------------|
| `src/adclaw/memory_agent/models.py` | Modify | Add `memory_type` field to `Memory`, add `MemoryType` literal |
| `src/adclaw/memory_agent/type_classifier.py` | **New** | Keyword + LLM two-stage type classifier |
| `src/adclaw/memory_agent/ingest.py` | Modify | Add `memory_type` param, call classifier, extract feedback structure |
| `src/adclaw/memory_agent/query.py` | Modify | Add `type_filter` and `boost_feedback` params |
| `src/adclaw/memory_agent/consolidate.py` | Modify | Group by type before clustering, skip feedback |
| `src/adclaw/memory_agent/store.py` | Modify | Migration function, `list_memories_by_type()`, `count_by_type()` |
| `src/adclaw/memory_agent/prompt_builder.py` | **New** | Typed memory prompt injection builder |
| `tests/memory_agent/test_type_classifier.py` | **New** | Unit tests for keyword + LLM classifier |
| `tests/memory_agent/test_typed_ingest.py` | **New** | Integration tests for typed ingest + retrieval |
| `tests/memory_agent/test_migration.py` | **New** | Migration idempotency and backfill tests |

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM classifier adds latency to every ingest | Keyword heuristic handles ~70% of cases without LLM call |
| Misclassification corrupts retrieval | Explicit `memory_type` override in API; reclassification endpoint for corrections |
| Migration on large database blocks writes | SQLite `ALTER TABLE ADD COLUMN` with default is O(1) -- updates schema only, does not rewrite rows |
| Feedback memories accumulate without cleanup | Future: add `expires_at` field for project type; feedback stays forever by design |
