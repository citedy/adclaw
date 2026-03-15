# API Reference

AdClaw exposes a REST API at `http://localhost:8088/api/`.

## Models

### List Providers
```
GET /api/models
```
Returns array of available LLM providers with their models.

### Get Active Model
```
GET /api/models/active
```
Returns `{ "active_llm": { "provider_id": "...", "model": "..." } }`.

### Set Active Model
```
PUT /api/models/active
Content-Type: application/json

{"provider_id": "openrouter", "model": "anthropic/claude-sonnet-4"}
```

### Configure Provider API Key
```
PUT /api/models/{provider_id}/config
Content-Type: application/json

{"api_key": "your-api-key"}
```

### Test Provider Connection
```
POST /api/models/{provider_id}/test
Content-Type: application/json

{"api_key": "optional-key", "base_url": "optional-url"}
```

### Add Custom Provider
```
POST /api/models/custom-providers
Content-Type: application/json

{
  "id": "provider-id",
  "name": "Provider Name",
  "default_base_url": "https://api.example.com/v1",
  "api_key_prefix": "sk-",
  "models": [{"id": "model-id", "name": "Model Name"}]
}
```

### Delete Custom Provider
```
DELETE /api/models/{provider_id}
```

### Add Model to Provider
```
POST /api/models/{provider_id}/models
Content-Type: application/json

{"id": "model-id", "name": "Model Name"}
```

## Citedy

### Get Citedy Status
```
GET /api/citedy/status
```
Returns `{ "configured": true, "balance": { "credits": 147558 }, "developer_url": "...", "billing_url": "..." }`.

### Save Citedy API Key
```
POST /api/citedy/save-api-key
Content-Type: application/json

{"api_key": "citedy_agent_..."}
```

## Skills

### List Skills
```
GET /api/skills
```

### Enable Skill
```
POST /api/skills/enable
Content-Type: application/json

{"skill_name": "citedy-seo-agent"}
```

### Disable Skill
```
POST /api/skills/disable
Content-Type: application/json

{"skill_name": "citedy-seo-agent"}
```

### Update Citedy Skills
```
POST /api/skills/hub/update-citedy
```

## MCP

### List MCP Clients
```
GET /api/mcp
```

### Add/Update MCP Client
```
POST /api/mcp
Content-Type: application/json

{
  "key": "client_key",
  "name": "Client Name",
  "enabled": true,
  "transport": "streamable_http",
  "url": "https://server.example.com/mcp",
  "headers": {"Authorization": "Bearer TOKEN"}
}
```

## Channels

### List Channels
```
GET /api/channels
```

### Update Channel Config
```
PUT /api/channels/{channel_id}
Content-Type: application/json

{"enabled": true, "bot_token": "..."}
```

## Chat

### Send Message
```
POST /api/chat/send
Content-Type: application/json

{"message": "Hello", "session_id": "optional-session-id"}
```

### List Sessions
```
GET /api/sessions
```
