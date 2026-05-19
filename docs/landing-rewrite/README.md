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
| `pricing-casual.md` | Outcome-focused pricing using real Citedy per-action credit costs |
| `pricing-hardcore.md` | Self-host vs hosted comparison (DO/Railway treated as partners, not enemies) |
| `telegram-dialogs.md` | Dialog scenarios for fake Telegram screenshots — founder writes these to live bots, screenshots the result |

## Implementation principles

1. **Drop from casual pages:** `iMessage`, `DingTalk`, `Feishu`, `QQ` (keep only Telegram + Discord + Web on casual). They stay listed on `/dev` for completeness.
2. **Drop from casual pages:** Clawsy AgentHub / karma economy. It's confusing for marketers. Move to `/dev` as a power-user feature.
3. **Drop from casual pages:** "23 LLM providers, 100+ models, 130+ skills" feature-firehose. Marketer doesn't care. Replace with outcome metrics.
4. **Drop from casual pages:** R1-R5, AOM, 208-pattern scanner, prompt caching, self-healing — internal architecture vocabulary. Move to `/dev`.
5. **Keep on casual pages:** Apache 2.0 mention (trust signal: "you can leave anytime"), Citedy MCP value (the moat), Cloudflare Sandbox + CDN as plain-English security/speed.
6. **Specialists are infinite.** Defaults to 5 (Strategist, Researcher, SEO Writer, Ads Manager, Analyst), but the customer can add unlimited personas on every plan. Competitors monetize persona counts — we don't.
7. **DigitalOcean and Railway are partners.** Don't compare hosted vs DO/Railway as "fast vs slow" — both deploy in minutes. The hosted edge is bundled Citedy credits + bundled LLM messages + zero ops.
8. **LLM messages are bundled** in every hosted plan (Starter 300 / Pro 1,500 / Business 5,000). Users can also bring their own LLM key for unlimited usage.
9. **Credit numbers use real Citedy API costs** (per citedy.com/pricing and citedy.com/skill.md). No vague "10 articles/month" — use real per-action credit costs and let the menu tell the story.
10. **Even with zero credits, AdClaw keeps working.** User's own LLM key (or bundled LLM messages) powers chat + 100+ built-in skills + 25+ MCP servers. Citedy credits power the "first-class SEO/GEO content published to your domain + your socials" pipeline specifically — they are the value-add, not a kill switch.

## Brand hierarchy clarified

```
Citedy (company / platform)
├── AdClaw — multi-agent marketing office (Apache 2.0)
│   ├── AdClaw Host (hosted, default for casual)
│   └── adclaw (pip/Docker, dev path)
└── Citedy MCP — 60+ marketing tools (the moat, callable from any agent)
```

`/dev` audience sees: "AdClaw is open-source, Citedy MCP is the value-add."
Casual audience sees: "AdClaw is your AI marketing team. Citedy credits power the published content."

## Status

- [ ] `home-casual.md` — written, awaiting implementation
- [ ] `home-hardcore.md` — written, awaiting implementation
- [ ] `pricing-casual.md` — written, awaiting implementation
- [ ] `pricing-hardcore.md` — written, awaiting implementation
- [ ] `telegram-dialogs.md` — written, awaiting fake-screenshot capture
- [ ] Screenshots: AdClaw Web UI dashboard
- [ ] Screenshots: AdClaw bot in Telegram group (founder writes prompts from `telegram-dialogs.md` to live bots, captures the result)
- [ ] Decision: `/dev` vs `/self-host` for hardcore URL
