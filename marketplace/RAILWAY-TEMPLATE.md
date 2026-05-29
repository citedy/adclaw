# Railway Template — AdClaw

Draft content used by `templatePublish` API call. Edit here, then push to template via API.

## Template metadata

- **Name:** AdClaw
- **Category:** `AI` (Railway uses this slug; falls back to "Featured" if unknown)
- **Tags:** AI, AI Agents, Marketing, SEO, Telegram, Discord
- **Image (logo URL):** https://raw.githubusercontent.com/Citedy/adclaw/main/console/public/favicon.svg
- **Demo URL (optional):** https://marketplace.digitalocean.com/apps/adclaw

## Description (short, shown on tile)

```
AI marketing agent team — 130+ skills, multi-agent personas, 24 LLM providers, multi-channel (Telegram/Discord/Web). Deploys in 60s. Requires Hobby plan or higher (≥ 2 GB RAM).
```

## Full README (rendered in template page)

```markdown
# AdClaw — AI Marketing Agent Team

Deploy an entire AI marketing department in 60 seconds. Each agent has a defined role, its own LLM, specialized skills, and a work schedule — sharing context and coordinating tasks automatically.

## What you get

- **130+ built-in skills** — SEO, ads, content, social, audio, music, graphics, video. All security-scanned and self-healing.
- **Multi-agent personas** — define teams of specialized agents that share memory and coordinate.
- **24 LLM providers, 150+ models** — OpenAI, Anthropic, Gemini, DashScope, Alibaba, Xiaomi, Z.AI, xAI, Mistral, DeepSeek, Groq, Together, OpenRouter, Cerebras, MiniMax, Baseten, Moonshot, Inception, ModelScope, Ollama, llama.cpp, MLX, Azure OpenAI — with automatic failover.
- **Multi-channel** — chat through Telegram, Discord, Feishu, DingTalk, QQ, or the built-in web console.
- **Always-On Memory (AOM)** — vector + FTS5 dual-layer memory with smart consolidation across sessions and personas.
- **Always-on cron** — agents run scheduled jobs (publish, monitor, scrape) on their own work calendar.

## ⚠️ Plan requirements

**Requires Hobby plan or higher (≥ 2 GB RAM).** AdClaw bundles a Python agent runtime + skill registry + optional Chromium that need ≥ 600 MB on startup; the trial 512 MB instance OOMs immediately. Disk: 25 GB recommended.

| Plan | Works? |
|---|---|
| Trial / 512 MB | ❌ OOM at startup |
| Hobby ($5/mo, 2 GB) | ✅ Recommended starter |
| Pro / Higher tier | ✅ For production / multiple personas |

## Variants

This template uses `nttylock/adclaw:latest` (full variant, ~4.2 GB image) which includes Chromium for browser-based skills (web research, scraping, screenshot, social posting).

If you don't need browser automation and want a lighter image, change the Docker image in service settings:

- `nttylock/adclaw:latest-core` — no Chromium, ~2.7 GB image, ~250 MB idle RAM
- `nttylock/adclaw:latest-browser` — browser-only, no desktop skills, ~4.1 GB image
- `nttylock/adclaw:latest` — everything (default)

## After deploy

1. Open the public URL Railway gave you
2. The wizard asks for **one LLM provider API key** — pick the one you have (OpenAI, Anthropic, Aliyun, Z.AI, etc.)
3. Optionally add `TELEGRAM_BOT_TOKEN` in Variables → restart → start chatting in Telegram

Provider API keys are stored on the persistent volume at `/app/working.secret/providers.json` — they survive redeploys.

## Configuration

Environment variables (set in Railway → Variables):

```
ADCLAW_ENABLED_CHANNELS=console,telegram   # subset: console,telegram,discord,dingtalk,feishu,qq
LOG_LEVEL=INFO                             # DEBUG for troubleshooting
TELEGRAM_BOT_TOKEN=...                     # if telegram channel enabled
```

LLM keys go through the wizard, not env vars.

## Persistent volumes (configured by template)

- `/app/working` (25 GB) — config, sessions, skills cache, sqlite
- `/app/working.secret` (1 GB) — provider API keys

Both are auto-attached. Removing them means re-running the wizard on every redeploy.

## Health check

`GET /api/diagnostics/health` → 200 + JSON. Cold start 20–40s, so the template sets `healthcheckTimeout: 60`.

## Source code

- Public repo: https://github.com/Citedy/adclaw
- DO Marketplace listing: https://marketplace.digitalocean.com/apps/adclaw
- Issues / questions: https://github.com/Citedy/adclaw/issues

## Authors

Citedy team. License: Apache-2.0.
```

## API call (run after Hobby is active and deploy is SUCCESS)

```bash
TOKEN=<railway project token>
PROJ=a08d221b-61ae-451c-8b2c-04c3620ad919
ENV=ccb97ac8-e1ef-4562-8362-645d955f0689

# 1. Generate template draft from current project state
TPL=$(rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { templateGenerate(input: {projectId: \\\"$PROJ\\\", environmentId: \\\"$ENV\\\"}) { id } }\"}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['templateGenerate']['id'])")

# 2. Publish with description and README (read from this file)
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  --data @<(jq -Rsn --rawfile readme RAILWAY-TEMPLATE.md '
    {query: "mutation($id: String!, $input: TemplatePublishInput!) { templatePublish(id: $id, input: $input) { id } }",
     variables: {
       id: env.TPL,
       input: {
         category: "AI",
         description: "AI marketing agent team — 130+ skills, 24 LLM providers, multi-channel. Requires Hobby plan or higher (≥ 2 GB RAM).",
         readme: $readme,
         image: "https://raw.githubusercontent.com/Citedy/adclaw/main/console/public/favicon.svg"
       }
     }
    }')
```
