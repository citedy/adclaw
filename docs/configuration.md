# Configuration Guide

## Environment Variables

Set these in your `.env` file or pass with `-e` to `docker run`:

| Variable | Required | Description |
|----------|----------|-------------|
| `ADCLAW_ENABLED_CHANNELS` | No | Comma-separated list of channels. Default: `discord,dingtalk,feishu,qq,console,telegram` |
| `ADCLAW_PORT` | No | Web UI port. Default: `8088` |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token from @BotFather |
| `CITEDY_API_KEY` | No | Your Citedy agent API key (`citedy_agent_...`) |
| `AGENTHUB_API_KEY` | No | Clawsy AgentHub API key for distributed tasks |
| `GITHUB_TOKEN` | No | GitHub token — raises API rate limit when installing skills from GitHub (60 → 5000 req/hr) |
| `LOG_LEVEL` | No | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Default: `INFO` |

> **Skill-specific API keys** (Unosend, Google, Tavily, etc.) are configured per-skill in **Settings > Skills**. Each skill declares which env vars it needs.

## LLM Configuration

### Via Web UI
Navigate to `/models` in the web UI to:
- Select a provider and model
- Enter API keys
- Add custom providers

### Via Chat
Ask the bot directly:
- "Switch to Claude Sonnet 4"
- "Use GPT-5"
- "Add OpenRouter with key sk-or-..."
- "What models are available?"

### Via API
```bash
# List providers
curl http://localhost:8088/api/models

# Set active model
curl -X PUT http://localhost:8088/api/models/active \
  -H "Content-Type: application/json" \
  -d '{"provider_id": "openrouter", "model": "anthropic/claude-sonnet-4"}'

# Configure API key
curl -X PUT http://localhost:8088/api/models/openrouter/config \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-or-your-key"}'
```

## MCP Server Configuration

Citedy MCP server is pre-configured. To add additional MCP servers:

### Via Web UI
Navigate to `/mcp` to manage MCP server connections.

### Via API
```bash
curl -X POST http://localhost:8088/api/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "key": "my-server",
    "name": "My MCP Server",
    "enabled": true,
    "transport": "streamable_http",
    "url": "https://my-server.example.com/mcp",
    "headers": {"Authorization": "Bearer token"}
  }'
```

## Channel Configuration

### Telegram
Set `TELEGRAM_BOT_TOKEN` env var or configure via `/channels` in the web UI.

### Discord
Set the Discord bot token in the web UI under `/channels`.

### Web Console
Always available at `http://localhost:8088/chat`.

## Data Persistence

All data is stored in the `/app/working` volume:
- `config.json` — main configuration
- `customized_skills/` — installed skills
- `sessions/` — chat sessions
- `memory/` — agent memory

Mount a Docker volume to persist data across container restarts:
```bash
-v adclaw-data:/app/working
```

## Updating

```bash
docker pull nttylock/adclaw:latest
docker stop adclaw && docker rm adclaw
# Re-run your docker run command (data persists in the volume)
```
