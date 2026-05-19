# adclaw.app/dev — HARDCORE HOME (developer landing)

**URL:** `adclaw.app/dev` (or `/self-host`, decide and commit)

**Audience:** experienced developer, technical founder, devops-savvy growth lead, indie hacker. Knows OpenClaw, n8n, Dify. Reads the comparison table. Wants Apache 2.0 and source code.

**Page goal:** Convert to `git clone` + star on GitHub + (eventually) sign up for hosted as a convenience.

**Tone:** Direct, technical, no marketing fluff. Trust comes from architecture details, not adjectives.

---

## Section 1 — Nav

Same as casual but reversed emphasis:

- Logo: `AdClaw`
- Links: `Docs` · `GitHub` · `Docker Hub` · `Comparison` · `For marketers →` · `Pricing`

---

## Section 2 — Hero

### Headline
**Open-source AI marketing agent team.<br>Self-host or run hosted.**

### Sub
Multi-agent personas. Dual-layer memory with contradiction detection. 23 LLM providers with auto-fallback. 208-pattern security scanner. 130+ marketing skills, 60+ Citedy MCP tools. Apache 2.0.

### Install (keep current install block, including Docker variant selector)

One-liner:
```bash
curl -fsSL https://get.adclaw.app | bash
```

Python:
```bash
pip install adclaw
adclaw init
adclaw app
```

Docker — pick a variant:
```bash
docker run -d -p 8088:8088 nttylock/adclaw:latest     # full,    4.2 GB
docker run -d -p 8088:8088 nttylock/adclaw:browser    # browser, 4.1 GB
docker run -d -p 8088:8088 nttylock/adclaw:core       # minimal, 2.7 GB
```

### Deploy buttons (current — keep)
- Deploy on DigitalOcean (VPS from $10) — partner
- Deploy on Railway (Hobby plan, ≥2GB RAM) — partner

### Secondary CTA
`Or run our hosted version — $10/mo →` (links to `/pricing`)

### Trust strip
`Apache 2.0  ·  v1.0.6  ·  113 skills shipped  ·  Active development`

### Implementation note
This is essentially the current home page hero, kept verbatim. The casual home page hero replaces the public-facing default.

---

## Section 3 — Architecture (NEW or expanded)

### Title
**What's actually inside.**

### Sub
You're going to grep the source anyway. Here's the map.

### 6 architecture cards

**1. Multi-persona runtime**
Each persona has its own SOUL.md (identity), LLM config, skill set, MCP tools, and cron schedule. Coordinator persona orchestrates: synthesis-driven, reads AOM, emits TaskStrategy with continue/pivot/abandon logic.

**2. Dual-layer memory (ReMe + AOM)**
ReMe: per-agent file-based memory. AOM (Always-On Memory): SQLite + sqlite-vec + FTS5, shared across personas. 4 typed categories (user/feedback/project/reference), feedback boosted 1.5x in retrieval. Smart consolidation with contradiction detection.

**3. R1-R5 memory optimization**
R1: rule-based markdown cleanup + N-gram codebook (lossless $XX codes, 8-15% token savings). R2: tiered context (L0/L1/L2 summaries by priority). R3: near-dedup with shingle-hash Jaccard. R4-R5: smart consolidation pipeline (orient→gather→consolidate→prune).

**4. 208-pattern security scanner**
Static analysis on every skill before install. Analysis-first LLM audit with 8 category-specific criteria (SEO, browser, data...). Critical findings short-circuit. 33-pattern memory sanitizer for prompt injection. Self-healing for broken YAML.

**5. 23 LLM providers, 100+ models**
OpenAI, Anthropic, Gemini, DeepSeek, Groq, OpenRouter, MiniMax, Cerebras, Together, Mistral, Baseten, Inception, Moonshot, xAI, Aliyun, DashScope, Ollama, llama.cpp, MLX, vLLM, LiteLLM, Azure OpenAI, Fireworks. Auto-fallback chain with timeout. OpenRouter routing: auto, nitro, free, floor.

**6. Citedy MCP server (the moat)**
60+ marketing automation tools you can't get elsewhere: SEO audits, content gap analysis, competitor deep-dives, lead magnet generation, AI video shorts, trend scouting, GA/GSC integration. Free key on signup. Pay-as-you-go credits for heavy operations.

---

## Section 4 — Channels

### Title
**7 chat channels. Built-in.**

| Channel | Status |
|---------|--------|
| Telegram | ✓ Primary |
| Discord | ✓ |
| Web Console | ✓ |
| iMessage | ✓ |
| DingTalk | ✓ |
| Feishu | ✓ |
| QQ | ✓ |

@tag routing across all channels. Coordinator-aware. Shared memory.

---

## Section 5 — Comparison (KEEP CURRENT TABLE)

Keep the full comparison table currently on home page. This is for developers comparing options.

Table columns: AdClaw, CoPaw, CrewAI, Dify, OpenClaw MC

Add rows you currently have plus:
- Hermes Agent (Nous Research)
- nanobot / NanoClaw / ClawWork (OpenClaw ecosystem)

Link to full comparison: `/docs/comparison.md`

---

## Section 6 — Clawsy AgentHub (KEEP, this audience cares)

Keep current "Clawsy AgentHub — collaborative task network" section. Karma economy, distributed tasks, agent leaderboard. This resonates with developers but bored marketers — perfect for `/dev`.

---

## Section 7 — Deployment options (NEW expanded block)

### Title
**Where do you want to run it?**

### 4-card grid

**Local (laptop / workstation)**
```bash
pip install adclaw
```
2.7 GB → 4.2 GB depending on variant. Bring your own LLM keys.

**Docker**
```bash
docker run -d -p 8088:8088 nttylock/adclaw:latest
```
Variants: `:latest` (full, 4.2GB) · `:browser` (4.1GB) · `:core` (2.7GB)

**DigitalOcean / Railway**
1-click deploy. $10 VPS minimum. Persistent volume + your domain.

**AdClaw Host (hosted)**
$10–79/mo. No infra. 90-second launch. Includes Citedy credits. → Pricing

---

## Section 8 — License / Open source

### Title
**Apache 2.0. Fork it.**

### Body
Fork it, embed it, sell it. We make money on hosting + Citedy credits, not on the framework. The framework is yours.

CTAs:
- `View on GitHub →`
- `Read the docs →`
- `Get hosted →`

---

## Section 9 — Footer

Same as casual but flipped emphasis:

```
[Logo] AdClaw — for developers

Self-host:    GitHub  ·  Docker  ·  pip  ·  Docs  ·  DigitalOcean  ·  Railway
Hosted:       Pricing  ·  AdClaw Host
Company:      Citedy  ·  Blog
Community:    Clawsy  ·  Discord  ·  Discussions

© 2026 Citedy  ·  Apache 2.0
```

---

## Implementation note

This page is **mostly the current home page** with minor refinements:
- Add architecture cards section (deeper than current "What you get")
- Add deployment options 4-card grid (currently scattered)
- Keep the comparison table as-is
- Keep Clawsy AgentHub section as-is
- Keep the Docker variant selector in the install block (do not strip it)

The casual home page is the **new work**. This dev page is **current home, repositioned**.
