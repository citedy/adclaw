---
name: self-setup
description: Configure LLM providers and models through conversation — add API keys, switch models, list available options.
metadata: { "adclaw": { "emoji": "⚙️" } }
---

# Self-Setup — Provider & Model Configuration

This skill lets you configure LLM providers and models through conversation.
You have access to your own management API at `http://localhost:8088/api/`.

---

## When to Use

- User asks to add, change, or configure an LLM provider
- User asks to switch models
- User provides an API key for a provider
- User asks "what models are available?"
- User says something like "use GPT-5" or "switch to Claude"

---

## API Reference

All commands use `curl` via your shell tool. Base URL: `http://localhost:8088/api`

### List All Providers

```bash
curl -s http://localhost:8088/api/models | python3 -m json.tool
```

### Get Active Model

```bash
curl -s http://localhost:8088/api/models/active | python3 -m json.tool
```

### Set Active Model

```bash
curl -s -X PUT http://localhost:8088/api/models/active \
  -H "Content-Type: application/json" \
  -d '{"provider_id": "PROVIDER_ID", "model": "MODEL_ID"}'
```

### Configure Provider API Key

```bash
curl -s -X PUT http://localhost:8088/api/models/PROVIDER_ID/config \
  -H "Content-Type: application/json" \
  -d '{"api_key": "USER_API_KEY"}'
```

### Add Custom Provider

For providers not in the built-in list (Together AI, Groq, Fireworks, DeepInfra, etc.):

```bash
curl -s -X POST http://localhost:8088/api/models/custom-providers \
  -H "Content-Type: application/json" \
  -d '{
    "id": "provider-id",
    "name": "Provider Name",
    "default_base_url": "https://api.example.com/v1",
    "api_key_prefix": "sk-",
    "models": [
      {"id": "model-id", "name": "Model Display Name"}
    ]
  }'
```

### Test Provider Connection

```bash
curl -s -X POST http://localhost:8088/api/models/PROVIDER_ID/test \
  -H "Content-Type: application/json" \
  -d '{"api_key": "OPTIONAL_KEY", "base_url": "OPTIONAL_URL"}'
```

### Delete Custom Provider

```bash
curl -s -X DELETE http://localhost:8088/api/models/PROVIDER_ID
```

### Add Model to Existing Provider

```bash
curl -s -X POST http://localhost:8088/api/models/PROVIDER_ID/models \
  -H "Content-Type: application/json" \
  -d '{"id": "model-id", "name": "Model Name"}'
```

---

## Built-in Providers

| ID | Name | Base URL | Key prefix |
|----|------|----------|------------|
| openrouter | OpenRouter | openrouter.ai/api/v1 | sk-or- |
| openai | OpenAI | api.openai.com/v1 | sk- |
| anthropic | Anthropic | api.anthropic.com/v1 | sk-ant- |
| aliyun-intl | Aliyun Coding (Intl) | coding-intl.dashscope.aliyuncs.com/v1 | sk-sp |
| ollama | Ollama (local) | localhost:11434/v1 | (none) |

---

## Common Custom Providers

| Name | Base URL | Key prefix |
|------|----------|------------|
| Together AI | https://api.together.xyz/v1 | (none) |
| Groq | https://api.groq.com/openai/v1 | gsk_ |
| Fireworks AI | https://api.fireworks.ai/inference/v1 | fw_ |
| DeepInfra | https://api.deepinfra.com/v1/openai | (none) |
| Mistral AI | https://api.mistral.ai/v1 | (none) |

---

## Behavior Guidelines

1. **Always list current providers first** before making changes
2. **Confirm with the user** before switching models or adding providers
3. **Never expose full API keys** in responses — show only prefix
4. **Test connection** after configuring a new provider
5. If user says "use Claude" → suggest OpenRouter (one key for all) or Anthropic (direct)
6. If user says "use a free model" → suggest Ollama (local) or Aliyun-Intl (free trial)

---

## Citedy MCP Configuration

To check or update the Citedy MCP tools integration:

```bash
# Check status
curl -s http://localhost:8088/api/citedy/status | python3 -m json.tool

# Save Citedy API key
curl -s -X POST http://localhost:8088/api/citedy/save-api-key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "citedy_agent_..."}'
```

---

## Channel Configuration

```bash
# List MCP clients
curl -s http://localhost:8088/api/mcp | python3 -m json.tool

# Add/update MCP client
curl -s -X POST http://localhost:8088/api/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "key": "client_key",
    "name": "Client Name",
    "enabled": true,
    "transport": "streamable_http",
    "url": "https://server.example.com/mcp",
    "headers": {"Authorization": "Bearer TOKEN"}
  }'
```
