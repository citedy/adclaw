# Deploy and Host AdClaw on Railway

AdClaw is an open-source multi-agent AI marketing platform that runs SEO, ads, content, social, and analytics workflows as a coordinated team of specialist agents — each with its own LLM, 130+ built-in skills, work schedule, and shared memory. Chat with the team from Telegram, Discord, or the built-in web console.

## About Hosting AdClaw

AdClaw runs as a single FastAPI server with a React console, packaged in one Docker image (`nttylock/adclaw:latest`). On Railway it builds from the public `Citedy/adclaw` GitHub repo using the included `deploy/Dockerfile`. The container listens on port 8088 with a `/api/diagnostics/health` endpoint that surfaces LLM, channel, MCP, and watchdog status. A persistent volume at `/app/working` keeps your config, sessions, sqlite memory, and skill cache across redeploys; provider API keys live alongside it. After the first deploy, open the public URL — a one-step wizard asks for any LLM provider key (OpenAI, Anthropic, Aliyun, Z.AI, etc.) and you're chatting with the agent team within seconds.

## Common Use Cases

- **In-house AI marketing team** — automate blog drafting, SEO research, ad copy generation, competitor monitoring, and scheduled social posting under one self-hosted agent platform.
- **Telegram-first AI assistant** — operate a multi-persona team (Growth Hacker, Social Strategist, Content Writer, Analytics Reporter) entirely from Telegram, with shared memory across personas.
- **Self-hosted alternative to point tools** — replace Surfer / Jasper / Buffer / Sprout with one coordinated agent stack you fully control, running on your own data.

## Dependencies for AdClaw Hosting

- Docker (Railway handles this automatically via the included Dockerfile)
- 2 GB RAM minimum, 25 GB disk
- At least one LLM provider API key — any of 23 supported (entered through the post-deploy wizard, not as an env var)

### Deployment Dependencies

- Public source repo — https://github.com/Citedy/adclaw
- Docker Hub image — https://hub.docker.com/r/nttylock/adclaw
- Railway-specific deployment guide — https://github.com/Citedy/adclaw/blob/main/docs/deploy/railway.md
- Live demo on Railway — https://adclaw-production.up.railway.app
- DigitalOcean Marketplace listing — https://marketplace.digitalocean.com/apps/adclaw
- Apache-2.0 license — built on top of [AgentScope-Runtime](https://github.com/agentscope-ai/agentscope-runtime)

### Implementation Details

To enable Telegram chat after deploy, set these in Railway → **Variables**:

```
ADCLAW_ENABLED_CHANNELS=console,telegram
TELEGRAM_BOT_TOKEN=<your bot token>
```

Then restart the service — the bot becomes addressable in Telegram immediately. The same pattern works for Discord (`DISCORD_TOKEN`), Feishu, DingTalk, and QQ. Health check is exposed at `/api/diagnostics/health` returning JSON with subsystem status.

## Why Deploy AdClaw on Railway?

<!-- Recommended: Keep this section as shown below -->
Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying AdClaw on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.
<!-- End recommended section -->
