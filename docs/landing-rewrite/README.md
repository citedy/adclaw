# Landing Page Rewrite — AdClaw

Two-audience strategy for adclaw.app landing and pricing pages.

## Audiences

| Path | Audience | Default? |
|------|----------|----------|
| `adclaw.app` | **Casual marketer** — wants results, not infra | ✅ Default |
| `adclaw.app/dev` (or `/self-host`) | **Hardcore developer** — wants self-host, pip, Docker, DO, Railway | Linked from main |
| `adclaw.app/pricing` | **Casual buyer** — paying for hosted office | ✅ Default |
| `adclaw.app/pricing/self-host` | **Hardcore buyer** — comparing hosted vs DIY | Linked from main pricing |

## Files in this directory

| File | Purpose |
|------|---------|
| `home-casual.md` | Default home page rewrite — pain-first, hosted-first, Telegram team block, "what it looks like" block |
| `home-hardcore.md` | Developer landing — current home page refined, repositioned as `/dev` |
| `pricing-casual.md` | Outcome-focused pricing (articles/month, not credits/min) |
| `pricing-hardcore.md` | Self-host vs hosted comparison |

## Implementation principles

1. **Drop from casual pages:** `iMessage`, `DingTalk`, `Feishu`, `QQ` (keep only Telegram + Discord + Web on casual). They stay listed on `/dev` for completeness.
2. **Drop from casual pages:** Clawsy AgentHub / karma economy. It's confusing for marketers. Move to `/dev` as a power-user feature.
3. **Drop from casual pages:** "23 LLM providers, 100+ models, 130+ skills" feature-firehose. Marketer doesn't care. Replace with outcome metrics.
4. **Drop from casual pages:** R1-R5, AOM, 208-pattern scanner, prompt caching, self-healing — internal architecture vocabulary. Move to `/dev`.
5. **Keep on casual pages:** Apache 2.0 mention (trust signal: "you can leave anytime"), Citedy MCP value (the moat), security as plain-English assurance.
6. **LLM model bundling** — NOT mentioned anywhere yet. Add after implementation.

## Brand hierarchy clarified

```
Citedy (company / platform)
├── AdClaw — multi-agent marketing office
│   ├── AdClaw Host (hosted, default for casual)
│   └── adclaw (pip/Docker, dev path)
└── Citedy MCP — 60+ marketing tools (invisible layer, the moat)
```

`/dev` audience sees: "AdClaw is open-source, Citedy MCP is the value-add."
Casual audience sees: "AdClaw is your AI marketing team. Citedy credits power it."

## Status

- [ ] `home-casual.md` — written, awaiting implementation
- [ ] `home-hardcore.md` — written, awaiting implementation
- [ ] `pricing-casual.md` — written, awaiting implementation
- [ ] `pricing-hardcore.md` — written, awaiting implementation
- [ ] Screenshots: AdClaw Web UI dashboard
- [ ] Screenshots: AdClaw bot in Telegram group (showing @-routing)
- [ ] Decision: `/dev` vs `/self-host` for hardcore URL
