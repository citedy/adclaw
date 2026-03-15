# Changelog

All notable changes to AdClaw are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.2] - 2026-03-15

### Added
- **14 LLM providers**: OpenAI (GPT-5.4, Codex Mini), Z.AI (GLM-4.7/4.6/4.5), Moonshot AI (Kimi K2.5, K2 Thinking), plus custom provider API
- **Dashboard page**: persona status cards with model, skills, cron preview
- **Per-persona chat tabs**: isolated sessions with shared AOM memory
- **@mention selector**: persona chip bar above chat input
- **Landing page** at website-landing/ (here.now-inspired design)
- Partner referral links for Aliyun and Z.AI in Welcome wizard
- 31 Mission Control tests + live E2E script

### Fixed
- PermissionError on `/app/logs` during MemoryManager start
- Dashboard white page (wrong API endpoints + missing array guards)
- Auto-retry narrowed to specific BadRequestError + user notification
- Sidebar popup menus: solid white background
- Diagnostics: human-readable formatting, newest errors first

## [0.1.1] - 2026-03-14

### Added
- **AgentHub integration**: built-in agenthub-worker skill, Tasks button in Telegram
- **here.now file publishing**: instant shareable links for any file
- **Telegram Markdown**: bold/italic formatting with plain text fallback
- Console cleanup: removed all Chinese text, deleted language switcher
- Standardized CSS (spacing variables, drawer widths, typography)
- Security cleanup: removed hardcoded IPs, translated all Chinese runtime strings
- CODE_OF_CONDUCT.md, dependabot.yml, docs/comparison.md

### Fixed
- Auto-retry with clean context when LLM rejects stale session
- Pinchtab crash loop (4 iterations of debugging)

---

## [0.1.0] - 2026-03-13

First public release. Fork of [CoPaw](https://github.com/agentscope-ai/CoPaw) with significant additions for AI marketing teams.

### Added

#### Multi-Agent System
- **Multi-agent personas** — create specialized agents (researcher, writer, SEO, ads) with SOUL.md identity, own LLM, skills, and cron schedule
- **@tag routing** in Telegram — `@researcher find AI trends` sends to the right agent
- **Coordinator delegation** — one agent orchestrates the rest, delegating tasks automatically
- **Shared memory** across personas (file-based + vector store)
- **5 persona templates** — Researcher, Content Writer, SEO Specialist, Ads Manager, Social Media

#### Skills & Tools
- **96+ built-in skills** — SEO (12), Ads (12), Marketing (30+), Social (5), Analytics, Browser (8), Office (4)
- **10 agency-agent skills** — growth-hacker, social-media-strategist, tiktok-strategist, instagram-curator, analytics-reporter, app-store-optimizer, reddit-community-builder, trend-researcher, feedback-synthesizer, twitter-engager
- **6 Citedy skills** — instagram-scraper, tiktok-scraper, youtube-video-extractor, social-extractor, domain-hunter, skill-quality-eval
- **52 Citedy MCP tools** for SEO and marketing automation
- **4 MCP servers** — citedy, agent_browser, xai_search, exa
- **Self-healing skills** — broken YAML auto-fixed by LLM (3 attempts/session max)
- **Skill quality evaluation** — `GET /api/skills/{name}/quality`

#### Memory System
- **Always-On Memory (AOM)** — SQLite + sqlite-vec + FTS5, hybrid search (vector + keyword + RRF ranking), auto-consolidation (60-min cycle)
- **Multimodal memory** — ingest images, audio, PDF via Gemini Flash integration
- **File inbox** — watch a directory for new files, auto-ingest into AOM
- **Memory optimization (R1-R4)** — zero-LLM-cost deterministic layers:
  - R1: Pre-compression (rule cleanup + N-gram codebook, 8-15% token savings)
  - R2: Tiered context loading (L0/L1/L2 progressive summaries)
  - R3: Near-duplicate detection (hybrid shingle-hash + word-overlap, 90% rate)
  - R4: Temporal pruning (green >7d delete, yellow >30d condense, red keep)
- **AOM REST API** — 12 endpoints: stats, CRUD, semantic query, file upload, consolidation, config
- **Frozen memory snapshots** — hash-based prompt caching (HIT/REBUILT logging)

#### Security
- **Security scanner** — 208 patterns, 15 categories for skill code analysis
- **Memory sanitizer** — 33 threat patterns, 7 categories for prompt injection defense
- **LLM audit** for skills — async security review via `POST /api/skills/{name}/llm-audit`
- **Security badges** in UI — visual pattern scan + LLM audit status per skill

#### Channels (7 supported)
- **Telegram** — interactive menu (/personas, /model, /skills, /status, /new), paginated commands, continuous typing indicator, persistent reply keyboard, message streaming (Bot API 9.5)
- **Discord** — full messaging support
- **DingTalk** — audio files, rich text images, duplicate message prevention
- **Feishu (Lark)** — audio and file support
- **QQ** — messaging channel
- **Console** — local terminal chat
- **iMessage** — Apple Messages integration

#### LLM Providers (12 built-in)
- openai, anthropic, aliyun-intl, aliyun-codingplan, azure-openai, openrouter, xai, ollama, llamacpp, mlx, modelscope, dashscope
- Custom provider support with API key management
- Model connection testing in Web UI

#### Web Console
- **Glassmorphism design** — gradient backgrounds, dark pill sidebar, pill buttons, Slate palette
- **Pages**: Workspace, Skills, MCP, Personas, Models, Channels, Diagnostics, Sessions, Cron Jobs, Heartbeat, Environments, Chat
- **Citedy Design System** — 4-phase redesign with `citedy-overrides.less` for Ant Design
- API Keys Reference table + bulk ENV import

#### Infrastructure
- **Agent watchdog** — auto-restart on crash with health check
- **Diagnostics page + API** — health status, error log, restart button
- **Heartbeat monitoring** — file-based health pulse tracking
- **LLM output filtering** — strip `<think>` tags from Qwen/DeepSeek, filter tool calls from user channels
- **Atomic session saves** — tmp+rename pattern, corrupted sessions auto-backed up and recovered
- **Browser automation** — Playwright + Chromium + Xvfb in Docker, PinchTab for token-efficient browser control

#### CLI (13 commands)
- `adclaw init` — initialize working directory
- `adclaw app` — start web server
- `adclaw channels` — configure messaging channels
- `adclaw chats` — manage chat sessions
- `adclaw clean` — cleanup temp data
- `adclaw cron` — manage scheduled tasks
- `adclaw env` — environment variable management
- `adclaw providers` — LLM provider configuration
- `adclaw skills` — skill management
- `adclaw uninstall` — remove AdClaw data

#### Docker & Deployment
- **Multi-stage Dockerfile** — frontend build + runtime with Chromium, Xvfb, Supervisor
- **Multi-architecture** — amd64, arm64
- **Non-root execution** — app runs as `adclaw` user, system services as root
- **Smart entrypoint** — auto-config Citedy MCP, Exa, Telegram from env vars; skill sync on start; config migration for new defaults
- **docker-compose.yml** — data + secret volumes, all env vars documented

#### Testing
- **36+ test files** covering memory (8), security (5), personas (5), agents (3), delegation, diagnostics, watchdog, MCP resilience
- **23 memory optimization tests** (R1-R4)
- **Live stress-test script** — 120 memories, dedup verification, consolidation

### Security

- Removed hardcoded API keys and internal IPs from test files
- All secrets loaded from environment variables or mounted volumes
- `.gitignore` covers config.json, providers.json, envs.json, .env files

---

## [Unreleased]

### Planned

- Landing page (clawsy.app or GitHub Pages)
- WhatsApp channel support
- WASM sandbox for skill execution isolation
- Docker image size optimization (multi-stage improvements)
