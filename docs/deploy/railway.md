# Deploying AdClaw on Railway

This guide walks through deploying AdClaw — an AI marketing agent team — on [Railway](https://railway.com/).

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/adclaw?referralCode=8K6-i5&utm_medium=integration&utm_source=template&utm_campaign=generic)

## What you get

- **130+ built-in skills** — SEO, ads, content, social, audio, music, graphics, video, browser automation
- **Multi-agent personas** — Growth Hacker, Social Media Strategist, Content Writer, Analytics Reporter, plus your own. Coordinated by a central Coordinator. Address with `@persona-name` in chat; untagged messages route to the Coordinator.
- **23 LLM providers** with 100+ models — OpenAI, Anthropic, Google Gemini, Aliyun (Qwen, GLM), Z.AI, xAI Grok, Mistral, DeepSeek, Groq, Together, OpenRouter, Cerebras, MiniMax, Baseten, Moonshot Kimi, Inception, ModelScope, DashScope, Ollama, llama.cpp, MLX, Azure OpenAI. Automatic failover between configured providers.
- **Multi-channel chat** — Telegram, Discord, Feishu, DingTalk, QQ, or the built-in web console.
- **Always-On Memory (AOM)** — vector + FTS5 dual-layer memory shared across personas and sessions.
- **Cron** — agents run scheduled jobs (publish, monitor, scrape) on their own work calendars.
- **Citedy MCP** (optional) — 52 SEO/marketing tools available out-of-the-box; users can also register their own MCP servers.

## Prerequisites

> ⚠️ **Plan: Hobby or higher (≥ 2 GB RAM, 25 GB disk).**
>
> AdClaw bundles a Python agent runtime + skill registry + Chromium, so
> Railway's Free plan is not enough. Use **Hobby or higher**. Hobby is
> **$5/month** and includes **$5 of monthly usage credits**.

| Plan | Works? | Notes |
|---|---|---|
| Free / 0.5 GB RAM | ❌ | Not enough RAM/volume for AdClaw |
| Hobby ($5/mo) | ✅ | Recommended starter |
| Pro and higher | ✅ | For multiple personas under load |

You'll also need:
- **One LLM provider API key** (any of the 23) — entered through the wizard after first deploy
- *(Optional)* Telegram bot token, Discord token, or other channel credentials

You do **not** need a Citedy account to use AdClaw — Citedy MCP is opt-in.

## One-click deploy (recommended)

1. Click **Deploy on Railway** above (or paste your template URL).
2. Choose **Hobby** plan when prompted.
3. The template provisions one service with:
   - Image source: `Citedy/adclaw` (GitHub repo, builds from `deploy/Dockerfile`)
   - Two persistent volumes (`/app/working` 25 GB and `/app/working.secret` 1 GB)
   - Environment variables (see below)
   - Health check on `/api/diagnostics/health` with 60 s timeout
4. Wait 8–12 minutes for the first build (Chromium + Python + skill registry). Subsequent deploys are cached.

## Manual deploy (without template)

If you prefer to wire it up yourself:

1. **New Project → Deploy from GitHub repo** → `Citedy/adclaw`. Or **Deploy from Docker Image** → `nttylock/adclaw:1.0.5`.
2. **Settings → Networking** → expose port `8088`, generate the public domain.
3. **Settings → Build** → confirm builder is **Dockerfile** with path `deploy/Dockerfile` (read from `railway.json` automatically).
4. **Settings → Deploy**:
   - Health check path: `/api/diagnostics/health`
   - Health check timeout: `60`
   - Restart policy: ON_FAILURE, max retries 10
5. **Settings → Volumes** — attach two volumes (see "Persistent volumes" below).
6. **Variables** — add the env vars from "Configuration" below.
7. **Settings → Resources** — bump RAM to **at least 2 GB**, vCPU 1, disk 25 GB.

## Configuration

Set these in **Variables**:

| Variable | Default | Notes |
|---|---|---|
| `ADCLAW_ENABLED_CHANNELS` | `console,telegram` | Comma-separated subset of `console,telegram,discord,dingtalk,feishu,qq` |
| `LOG_LEVEL` | `INFO` | `DEBUG` for troubleshooting cold starts |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Required if `telegram` is in `ADCLAW_ENABLED_CHANNELS` |
| `DISCORD_TOKEN` | *(empty)* | Required if `discord` enabled |

LLM provider API keys are entered through the **first-boot wizard at the public URL**, not as env vars. They land on the `/app/working.secret` volume so they survive redeploys.

## Persistent volumes

AdClaw needs two volumes — without them every redeploy resets the wizard and your provider keys disappear.

| Mount path | Size | Holds |
|---|---|---|
| `/app/working` | 25 GB | `config.json`, sessions, skills cache, sqlite database, agent memory |
| `/app/working.secret` | 1 GB | `providers.json` (LLM API keys), `envs.json` |

If you only attach one, pick `/app/working` and accept that LLM keys live inside it (less isolation but functional).

## Variants (Docker image tags)

| Tag | Image size | Idle RAM | Best for |
|---|---|---|---|
| `nttylock/adclaw:1.0.5` (default pin) | ~4.2 GB | 600–800 MB | Full feature set — Chromium for browser/scraping/social skills |
| `nttylock/adclaw:1.0.5-browser` | ~4.1 GB | similar | Browser-only, no Feishu/DingTalk channels |
| `nttylock/adclaw:1.0.5-core` | ~2.7 GB | 250–400 MB | Lightweight — no Chromium, no desktop tools |

Switch by editing **Settings → Source** to use a Docker Image source instead of GitHub repo, then set the image to `nttylock/adclaw:1.0.5-core`. Build is skipped — deploy is ~30 s.

If you need a reproducible release pin instead of the moving variant tags, use
the versioned aliases published by the release workflow, for example
`nttylock/adclaw:1.0.5-core` or `nttylock/adclaw:1.0.5-browser`.

## Post-deploy workflow

1. **Open the public URL** Railway gave you (e.g. `https://adclaw-production.up.railway.app`).
2. The **welcome wizard** appears:
   - Pick an LLM provider from the dropdown
   - Paste the API key
   - Click **Continue** — the agent loads with default personas
3. Start chatting in the web console, or
   - Add `TELEGRAM_BOT_TOKEN` to Variables, restart, message your bot in Telegram
4. **Customize** (optional):
   - **Personas** tab → add specialists (e.g. "TikTok Strategist" with custom soul.md)
   - **Skills** tab → enable/disable specific skills, scan custom ones
   - **Cron** tab → schedule recurring tasks per persona
   - **MCP** tab → connect external MCP servers (Citedy, your own)

## Health check

```bash
curl https://<your-railway-url>/api/diagnostics/health
# → 200 OK
# → {"status":"healthy","uptime_seconds":1234,"subsystems":{...}}
```

Returns the status of LLM, channels, memory, AOM, MCP, and watchdog. Safe to poll from external monitors.

## Pricing note

Railway Hobby currently costs **$5/month** and includes **$5 of monthly usage
credits**.

For AdClaw, the important practical rule is:

- **Free** is not enough for deployment
- **Hobby** is the minimum supported Railway plan
- if your usage goes beyond the included monthly credit, Railway charges the
  overage

Set [Railway Spending Limits](https://docs.railway.com/reference/usage-limits)
if you want a hard cap.

## Troubleshooting

**Build fails with "skipping Dockerfile"**
→ The `railway.json` must be at the **repo root** (not `deploy/`). Our public repo already has it correctly placed.

**Deploy succeeds but health check fails after 10 s**
→ Default Railway health timeout is 10 s; AdClaw cold-starts in 30–60 s. Set `healthcheckTimeout: 60` in `railway.json` (already set in our default).

**Service crashes with `SIGKILL`**
→ Out of memory. Either upgrade plan, switch to `core` variant, or reduce `ADCLAW_ENABLED_CHANNELS`.

**LLM keys disappear after redeploy**
→ Volume `/app/working.secret` not attached. Check **Settings → Volumes**.

**Telegram bot doesn't respond**
→ Confirm `TELEGRAM_BOT_TOKEN` is set, `telegram` is in `ADCLAW_ENABLED_CHANNELS`, and you've talked to the bot at least once (Telegram requires the user to send `/start` first).

## Source code & support

- **Public repo:** https://github.com/Citedy/adclaw
- **DigitalOcean Marketplace:** https://marketplace.digitalocean.com/apps/adclaw
- **Issues:** https://github.com/Citedy/adclaw/issues
- **License:** Apache-2.0
