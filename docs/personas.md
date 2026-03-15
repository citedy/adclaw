# Multi-Agent Personas — Guide

## Overview

AdClaw supports **multi-agent personas**: each agent has its own identity
(SOUL.md), LLM configuration, skills, MCP clients, and optional cron schedule.
One agent is the **coordinator** — it receives untagged messages and can
delegate tasks to specialists.

```
+-------------------------------------------------------------------+
|                        AdClaw Instance                            |
|                                                                   |
|  +-------------+  +-------------+  +-------------+  +---------+  |
|  | Coordinator |  | Researcher  |  | Content     |  | Ads     |  |
|  | SOUL.md     |  | SOUL.md     |  | Writer      |  | Manager |  |
|  | LLM: default|  | LLM: grok   |  | SOUL.md     |  | SOUL.md |  |
|  | Skills: all |  | Skills: exa |  | LLM: qwen   |  | LLM: gpt|  |
|  | Cron: -     |  | Cron: 8,14  |  | Skills: seo |  | Cron: - |  |
|  +------+------+  +------+------+  +------+------+  +----+----+  |
|         |                |                |               |       |
|         +-------+--------+--------+-------+-------+------+       |
|                 |                         |                       |
|          +------v-------+         +-------v--------+              |
|          | Shared Memory|         | Dual Memory    |              |
|          | /shared/{id}/|         | ReMe per-agent |              |
|          | (read/write) |         | AOM shared DB  |              |
|          +--------------+         +----------------+              |
+-------------------------------------------------------------------+
```

---

## Concepts

### Persona

A persona is a named agent configuration stored in `config.json`:

```json
{
  "id": "researcher",
  "name": "Researcher",
  "soul_md": "## Role\nYou are a research specialist...",
  "model_provider": "aliyun-intl",
  "model_name": "qwen3.5-plus",
  "skills": ["exa_search", "trend_analysis"],
  "mcp_clients": ["brave_search"],
  "is_coordinator": false,
  "cron": {
    "enabled": true,
    "schedule": "0 8,14,20 * * *",
    "prompt": "Scan AI news. Write report to shared memory.",
    "output": "both"
  }
}
```

### Fields

```
+-------------------+----------+----------------------------------------------+
| Field             | Type     | Description                                  |
+-------------------+----------+----------------------------------------------+
| id                | string   | Unique slug, used as @tag (a-z, 0-9, -, _)  |
| name              | string   | Display name in UI                           |
| soul_md           | string   | SOUL.md content — agent personality/rules    |
| model_provider    | string   | LLM provider (empty = default)               |
| model_name        | string   | Model name (empty = default)                 |
| skills            | string[] | Subset of installed skills (empty = all)     |
| mcp_clients       | string[] | Subset of configured MCP clients (empty=all) |
| is_coordinator    | bool     | Only one agent can be coordinator            |
| cron.enabled      | bool     | Run this agent on a schedule                 |
| cron.schedule     | string   | Cron expression (e.g. "0 8 * * *")          |
| cron.prompt       | string   | What to execute on each run                  |
| cron.output       | string   | "chat" | "file" | "both"                    |
+-------------------+----------+----------------------------------------------+
```

### Coordinator

The agent with `is_coordinator: true`. Only one allowed per instance.

```
  User sends: "make a weekly report"
       |
       v  (no @tag detected)
  +----+----+
  |Coordinator|-----> delegate_to_agent("researcher", "find AI trends")
  +----+----+          |
       |               v
       |          +----+------+
       |          | Researcher |---> returns findings
       |          +-----------+
       |               |
       |<--------------+
       |
       +-----> delegate_to_agent("content-writer", "write blog from findings")
       |          |
       |          v
       |     +----+--------+
       |     |Content Writer|---> returns draft
       |     +-------------+
       |          |
       |<---------+
       |
       v
  Formats combined result --> sends to user
```

Delegation has a **max depth of 3** to prevent infinite loops.

---

## Routing

### Telegram

```
  Incoming message
       |
       v
  +----+----+
  | Parse   |
  | @tag at |
  | start   |
  +----+----+
       |
       +------ @researcher found? -----> Route to "researcher"
       |                                  (strip @tag from message)
       |
       +------ @content-writer? -------> Route to "content-writer"
       |
       +------ no @tag? ------+
       |                      |
       |   session has sticky  |
       |   persona from last   |
       |   message?            |
       |     |           |     |
       |    yes          no    |
       |     |           |     |
       |     v           v     |
       |   reuse     coordinator
       |   last      (or default
       |   persona    if none)
       |
       v
  Agent processes message with its SOUL.md, LLM, skills
```

**Examples:**
- `@researcher find AI trends this week` -> Researcher agent
- `@content-writer write a LinkedIn post` -> Content Writer agent
- `make a weekly report` -> Coordinator (or default agent)
- (next message in same chat, no tag) -> same agent as previous (sticky routing)

### Web UI Chat

The Web UI has a dropdown to select which agent to talk to. Each agent gets
its own chat history (session ID: `{agent_id}::{session_id}`).

---

## Shared Memory

Agents collaborate through a shared file system:

```
  /app/working/shared/
  +-- researcher/
  |   +-- daily-intel-2026-03-09.md
  |   +-- weekly-report.md
  |
  +-- content-writer/
  |   +-- blog-draft-ai-trends.md
  |   +-- social-posts.md
  |
  +-- coordinator/
      +-- weekly-summary.md
```

### Rules

```
  +------------------------------------------+
  |              Access Matrix               |
  +------------------------------------------+
  | Agent          | Read        | Write     |
  +----------------+-------------+-----------+
  | researcher     | ALL dirs    | own dir   |
  | content-writer | ALL dirs    | own dir   |
  | coordinator    | ALL dirs    | own dir   |
  +----------------+-------------+-----------+
```

- Each agent can **read** files from ANY agent's shared directory
- Each agent can **write** only to its OWN shared directory
- Path traversal is blocked (e.g., `../../etc/passwd` is rejected)
- Agent IDs in paths are validated (no `../` in agent_id)

### Built-in Tools

Agents have three shared memory tools:

| Tool | Description |
|------|-------------|
| `write_shared_file(filename, content)` | Write to own shared dir |
| `read_shared_file(agent_id, filename)` | Read from any agent's dir |
| `list_shared_files(agent_id)` | List files in an agent's dir |

### Workflow Example

```
  1. Researcher writes intel:
     write_shared_file("trends.md", "# AI Trends\n- GPT-5 released...")

  2. Content Writer reads it:
     read_shared_file("researcher", "trends.md")
     --> "# AI Trends\n- GPT-5 released..."

  3. Content Writer creates draft:
     write_shared_file("blog-draft.md", "# This Week in AI...")

  4. Coordinator reads both and summarizes:
     read_shared_file("researcher", "trends.md")
     read_shared_file("content-writer", "blog-draft.md")
     write_shared_file("summary.md", "# Team Output Summary...")
```

---

## Dual Memory System

Each persona uses two memory systems:

```
  +-------------------+          +-------------------+
  |    ReMe           |          |    AOM            |
  |  (file-based)     |          |  (vector DB)      |
  +-------------------+          +-------------------+
  | Per-agent scope   |          | Shared across all |
  | Working dir:      |          | Single database   |
  |  /agents/{id}/    |          | Tagged by agent_id|
  | Contains:         |          | Semantic search   |
  |  - MEMORY.md      |          | Auto-capture from |
  |  - memory/ dir    |          |   conversations   |
  |  - session files  |          |                   |
  +-------------------+          +-------------------+
        |                              |
        |  Short-term context          |  Long-term knowledge
        |  Conversation compaction     |  Cross-agent discovery
        |  Per-agent isolation         |  Shared intelligence
        +------------------------------+
```

- **ReMe**: handles conversation flow, compaction, session memory. Each agent
  has its own working directory at `/app/working/agents/{agent_id}/`
- **AOM**: handles semantic search and long-term knowledge. Shared database,
  memories tagged with `agent_id` for filtering

---

## SOUL.md — Agent Identity

SOUL.md defines who the agent is. It replaces the default system prompt
when a persona is active.

### Structure

```markdown
## Role
You are a research specialist. Your job is to find, verify, and
summarize information.

## Style
- Facts only, no speculation
- Always cite sources
- Write structured reports with clear sections

## Boundaries
- Never fabricate data or sources
- Flag uncertainty explicitly
- Write reports to shared memory for other agents
```

### Tips

- Keep it focused: describe WHAT the agent does, HOW it communicates,
  and what it should NEVER do
- Max 10,000 characters (must fit in context window with tools)
- The team summary is auto-injected so each agent knows its teammates
- Reference shared memory explicitly ("write reports to shared memory")

---

## Cron Schedules

Each persona can run on its own cron schedule:

```
  +-----+  0 8 * * *   +------------+
  | Cron +------------->| Researcher |---> runs prompt
  +-----+              +-----+------+      |
                              |             v
                              |      "Scan AI news..."
                              |             |
                              |    +--------v---------+
                              +--->| Output:           |
                                   |  "chat" -> Telegram|
                                   |  "file" -> /shared/|
                                   |  "both" -> both    |
                                   +-------------------+
```

### Configuration

```json
{
  "cron": {
    "enabled": true,
    "schedule": "0 8,14,20 * * *",
    "prompt": "Scan X, HN, and Google AI blog for trends. Write report.",
    "output": "both"
  }
}
```

| Output mode | Where results go |
|-------------|------------------|
| `chat` | Sends to Telegram/Discord chat |
| `file` | Writes to `/app/working/shared/{agent_id}/` |
| `both` | Both chat and file |

---

## REST API

Full CRUD for managing personas programmatically:

```
  GET    /api/agents/personas              List all personas
  POST   /api/agents/personas              Create a persona
  GET    /api/agents/personas/{id}         Get one persona
  PUT    /api/agents/personas/{id}         Update a persona
  DELETE /api/agents/personas/{id}         Delete a persona
```

### Create a Persona (curl)

```bash
curl -X POST http://localhost:8088/api/agents/personas \
  -H "Content-Type: application/json" \
  -d '{
    "id": "researcher",
    "name": "Researcher",
    "soul_md": "## Role\nYou are a research specialist.",
    "model_provider": "aliyun-intl",
    "model_name": "qwen3.5-plus",
    "skills": [],
    "mcp_clients": [],
    "is_coordinator": false,
    "cron": null
  }'
```

### List Personas

```bash
curl http://localhost:8088/api/agents/personas
```

### Delete a Persona

```bash
curl -X DELETE http://localhost:8088/api/agents/personas/researcher
```

### Constraints

- Persona `id` must match `^[a-z0-9_-]+$`
- Only **one** persona can have `is_coordinator: true`
- Duplicate IDs return `409 Conflict`

---

## Web UI

### Agents Page (`/agents`)

```
  +------------------------------------------------------------------+
  |  Agent Personas                    [From Template v] [Create Agent]|
  +------------------------------------------------------------------+
  |                                                                    |
  |  +-------------------+  +-------------------+  +----------------+ |
  |  | Coordinator       |  | Researcher        |  | Content Writer | |
  |  | [Coordinator]     |  |                   |  |                | |
  |  | ## Role           |  | ## Role           |  | ## Role        | |
  |  | You are the team  |  | You are a research|  | You create     | |
  |  | coordinator...    |  | specialist...     |  | engaging...    | |
  |  |                   |  |                   |  |                | |
  |  | [Default] 0 skills|  | [grok] 2 skills   |  | [qwen] 1 skill | |
  |  | 0 MCP             |  | 3 MCP [Cron: ON]  |  | 1 MCP          | |
  |  |                   |  |                   |  |                | |
  |  | [Edit]      [Del] |  | [Edit]      [Del] |  | [Edit]   [Del] | |
  |  +-------------------+  +-------------------+  +----------------+ |
  +------------------------------------------------------------------+
```

### Create / Edit Drawer

```
  +---------------------------------------+
  | Create Agent Persona                  |
  +---------------------------------------+
  | Name:     [____________________]      |
  | ID:       [____________________]      |
  |                                       |
  | SOUL.md:                              |
  | +-----------------------------------+ |
  | | ## Role                           | |
  | | You are a research specialist...  | |
  | |                                   | |
  | | ## Style                          | |
  | | - Facts only, no speculation      | |
  | +-----------------------------------+ |
  |                                       |
  | LLM Provider: [aliyun-intl     v]    |
  | LLM Model:    [qwen3.5-plus   v]    |
  |                                       |
  | Skills:       [x] exa_search          |
  |               [x] trend_analysis      |
  |               [ ] seo_audit           |
  |                                       |
  | MCP Clients:  [x] brave_search        |
  |               [x] xai_search          |
  |               [ ] citedy              |
  |                                       |
  | [x] Coordinator                       |
  |                                       |
  | Cron Schedule:                        |
  | [x] Enabled                           |
  | Schedule: [0 8,14,20 * * *_________]  |
  | Prompt:   [Scan AI news. Write report]|
  | Output:   [both                    v] |
  |                                       |
  |              [Cancel]  [Save]         |
  +---------------------------------------+
```

---

## Preset Templates

Use **"From Template"** to quickly create agents with pre-filled SOUL.md:

```
  Template          Suggested MCP          SOUL Summary
  +-----------+     +-----------------+    +-------------------------------+
  | Researcher|---->| brave_search    |    | Facts only, structured reports|
  |           |     | xai_search, exa |    | Cites sources, no speculation |
  +-----------+     +-----------------+    +-------------------------------+

  +-----------+     +-----------------+    +-------------------------------+
  | Content   |---->| citedy          |    | Brand voice, compelling hooks |
  | Writer    |     |                 |    | Reads researcher's reports    |
  +-----------+     +-----------------+    +-------------------------------+

  +-----------+     +-----------------+    +-------------------------------+
  | SEO       |---->| citedy          |    | Data-driven, impact-ranked    |
  | Specialist|     |                 |    | No black-hat, explains WHY    |
  +-----------+     +-----------------+    +-------------------------------+

  +-----------+     +-----------------+    +-------------------------------+
  | Ads       |---->| (none)          |    | ROI-focused, A/B testing      |
  | Manager   |     |                 |    | Budget-aware, platform-native |
  +-----------+     +-----------------+    +-------------------------------+

  +-----------+     +-----------------+    +-------------------------------+
  | Social    |---->| xai_search      |    | Trend-aware, platform-native  |
  | Media     |     |                 |    | Draft only, flags controversy |
  +-----------+     +-----------------+    +-------------------------------+
```

Templates set `mcp_clients` to empty by default. The `suggested_mcp_clients`
field is a hint — add them after configuring the MCP client in Settings.

---

## Security

| Feature | Description |
|---------|-------------|
| Path traversal protection | Shared memory blocks `../` in filenames and agent IDs |
| Delegation depth limit | Max 3 levels to prevent infinite delegation loops |
| SOUL.md size limit | 10,000 characters max |
| Skill scanner | 208 patterns across 15 threat categories |
| Memory sanitizer | 33 patterns for prompt injection detection |
| Coordinator uniqueness | Only one coordinator per instance (enforced in API + config) |

---

## Backward Compatibility

- If no personas are configured, AdClaw works exactly as before (single agent, SOUL.md from working dir)
- Existing cron jobs, sessions, and configs are unaffected
- The persona system is **additive** — zero breaking changes

---

## Directory Layout

```
  /app/working/
  +-- config.json              <-- personas stored here (agents.personas[])
  +-- AGENTS.md                <-- shared rules (loaded for all agents)
  +-- SOUL.md                  <-- default SOUL (used when no persona active)
  +-- PROFILE.md               <-- user identity (shared)
  |
  +-- agents/                  <-- per-agent working directories
  |   +-- researcher/
  |   |   +-- memory/          <-- ReMe memory files
  |   |   +-- MEMORY.md
  |   +-- content-writer/
  |   |   +-- memory/
  |   +-- coordinator/
  |       +-- memory/
  |
  +-- shared/                  <-- cross-agent shared files
  |   +-- researcher/
  |   |   +-- daily-intel.md
  |   |   +-- weekly-report.md
  |   +-- content-writer/
  |   |   +-- blog-draft.md
  |   +-- coordinator/
  |       +-- summary.md
  |
  +-- skills/                  <-- installed skills (96 built-in)
  +-- sessions/                <-- chat sessions
```

---

## FAQ

**Q: How many agents can I create?**
A: No hard limit. Create as many as you need.

**Q: Can agents talk to each other directly?**
A: Not directly. The coordinator delegates tasks, and agents share files.
Direct agent-to-agent messaging is planned for a future release.

**Q: What happens if I delete a persona?**
A: The persona is removed from config. Its shared files and memory directory
remain on disk (not auto-deleted).

**Q: Can two agents use different LLMs?**
A: Yes. Each agent can have its own `model_provider` + `model_name`.
Leave empty to use the instance default.

**Q: How does the prompt work with personas?**
A: When a persona is active, its `soul_md` replaces the default SOUL.md file.
AGENTS.md and PROFILE.md are still loaded. A team summary listing all agents
is auto-appended.
