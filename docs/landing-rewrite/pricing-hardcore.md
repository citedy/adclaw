# adclaw.app/pricing/self-host — HARDCORE PRICING

**URL:** `adclaw.app/pricing/self-host` (linked from `/pricing` and from `/dev`)

**Audience:** developer evaluating self-host vs hosted economics. Wants total cost of ownership numbers.

**Page goal:** Convert "I'll self-host" types to either (a) clean self-host with Citedy credits, or (b) hosted because it's cheaper than their time. Either outcome is fine. DigitalOcean and Railway are **partners** — we are not pitching against them, we are pitching with them.

**Tone:** Honest math. Show the real tradeoffs. Never disparage DO or Railway.

---

## Section 1 — Nav

Same.

---

## Section 2 — Hero

### Breadcrumb
`adclaw.app / pricing / self-host`

### Headline
**Self-host AdClaw.<br>Or let us host it.**

### Sub
AdClaw is Apache 2.0. Run it on your laptop, your VPS, our DigitalOcean and Railway partner deploys, or on AdClaw Host. Citedy MCP credits work the same way regardless of where the agent runs.

### Hero CTAs
`See total cost comparison ↓` · `Get hosted instead →`

---

## Section 3 — Self-host options

### Title
**Four ways to run AdClaw on your own infra.**

### 4-card grid

**Card 1 — Local (laptop / workstation)**
```bash
pip install adclaw
adclaw init
adclaw app
```
- Variants: full / browser / core (2.7–4.2 GB)
- Memory: 4–8 GB RAM recommended
- No cloud cost. No always-on. Manual launch.
- LLM cost: bring your own keys (~$5–50/mo depending on use)
- Citedy credits: optional, separate signup at citedy.com (free tier = 100 credits)

**Card 2 — Docker (any host)**
```bash
docker run -d -p 8088:8088 nttylock/adclaw:latest     # full,    4.2 GB
docker run -d -p 8088:8088 nttylock/adclaw:browser    # browser, 4.1 GB
docker run -d -p 8088:8088 nttylock/adclaw:core       # minimal, 2.7 GB
```
- VPS: $5–20/mo (Hetzner, your favorite host)
- Persistent volume for memory + skills
- Always-on (no sleep)
- LLM cost: bring your own keys
- Citedy credits: optional, separate signup

**Card 3 — DigitalOcean (partner)**
- 1-click marketplace deploy
- VPS from $10/mo
- Same install in ~5 minutes
- Auto-updates via image tag
- Citedy credits: optional, separate signup

**Card 4 — Railway (partner)**
- Hobby plan, ≥2 GB RAM (~$5–10/mo)
- 1-click deploy
- Auto-updates via image tag
- Citedy credits: optional, separate signup

### Implementation note
Cards 3 and 4 are partner-positive. Do NOT pitch hosted as "fast vs slow" against DO/Railway — both deploy in minutes. The hosted edge is **what's bundled**, not deployment speed.

---

## Section 4 — Hosted vs self-host TCO (KEY BLOCK)

### Title
**Total cost of ownership.**

### Sub
What it actually costs to run AdClaw for one solo marketer in real conditions. Self-host options (laptop, your VPS, DigitalOcean partner, Railway partner) are all fast to deploy and stable — we're just comparing what's **bundled**.

### Comparison table

| Cost item | **Self-host (own VPS or DO/Railway)** | **AdClaw Host (Pro)** |
|-----------|----------------------------------------|------------------------|
| Infrastructure | $5–10/mo VPS (Hetzner / DigitalOcean / Railway) | Included |
| Setup time | ~5 minutes (1-click on DO or Railway, longer on bare Hetzner) | 90 seconds |
| Monthly maintenance | ~1–2 hours (updates, debug, backup tuning) | 0 |
| Backups | Manual (you configure) | Included |
| SSL / domain config | Manual | Included |
| Citedy credits | Pay-as-you-go (~$30/mo for 500 credits if you buy through citedy.com) | 500 credits **bundled** in Pro |
| Bundled LLM messages | None — you pay your LLM provider direct | 2,000 messages **bundled** in Pro |
| LLM keys | BYO (~$10–30/mo) | BYO (same, on top of bundled messages) |
| **Total monthly $** | **~$45/mo + ~1–2 hrs labor** | **$29/mo, zero ops** |

### Verdict (callout)
> **At Pro ($29), hosted is cheaper than self-host purely because Citedy credits and LLM messages are bundled at fair-market rates.** It is not a comment on DigitalOcean or Railway — both are solid partners. Self-host wins when (a) you already have a server doing other things, (b) you want full source control, or (c) you need on-prem for compliance.

### Implementation note
This is the honest pitch — hosted is cheaper, not because we're charging less than cost, but because Citedy credits and LLM messages are bundled. Show the math, don't hide it. Never say "self-host is slow / hard" — it isn't, and DO/Railway are partners.

---

## Section 5 — When to self-host

### Title
**When self-host is the right call.**

### List

- **You have compliance constraints** — GDPR data residency, HIPAA, internal policy mandates on-prem.
- **You already run servers** — adding one more container has marginal cost.
- **You want to fork** — modifying the source, adding custom skills, embedding in your product.
- **You're a developer learning** — best way to understand the architecture is to run it.
- **You don't need 60+ Citedy MCP tools** — happy with the 130+ built-in skills + your own MCP servers.

### When hosted wins
- You have a marketing job, not a devops job.
- You want bundled Citedy credits and bundled LLM messages at one fixed monthly price.
- You want Telegram bot working in 90 seconds with zero config.
- Your time costs more than $20/hour.

---

## Section 6 — Citedy credits work the same way

### Title
**Same credits. Same tools. Anywhere you run AdClaw.**

### Body
The Citedy MCP server is bundled inside AdClaw. Whether you run AdClaw on your laptop, your VPS, on DigitalOcean, on Railway, or on AdClaw Host — you can use Citedy credits the same way.

- **Free tier on signup:** 100 Citedy credits, no card.
- **Top-ups:** see citedy.com/pricing for top-up packs (Growth = 1,500 credits for $14.99 etc.).
- **Subscription bundles** (only in AdClaw Host plans): 150 / 500 / 1,500 credits + 500 / 2,000 / 6,000 LLM messages **included monthly**.

### Real action costs (link to /pricing#credits for the full menu)
- 1 standard SEO article ≈ 20 credits
- 1 turbo article ≈ 2 credits
- 1 pillar article ≈ 48 credits
- 1 finished 10s AI video short ≈ 139 credits
- 1 text lead magnet (PDF) ≈ 30 credits
- 1 content gap analysis ≈ 40 credits
- 1 competitor discovery ≈ 20 credits
- 1 LLM visibility check ≈ 3 credits/platform
- Publishing to your blog or socials: **free**
- Full menu: [pricing → what credits buy](/pricing#credits)

### Implementation note
Important: self-hosters get a credit balance separately at citedy.com. AdClaw Host users get credits + LLM messages bundled into their plan. Same credits, different billing path. Be explicit so developers don't think they need to host us to get Citedy.

---

## Section 7 — Migrating between hosted and self-host

### Title
**Move your workspace anywhere.**

### Two-direction body

**Self-host → Hosted**
```bash
adclaw export --output workspace.tar.gz
```
Upload via Host dashboard → workspace restored as-is. Personas, memory, skills, configs.

**Hosted → Self-host**
Dashboard → Export → download tarball → `adclaw import workspace.tar.gz` on your machine.

### Why this matters
Apache 2.0 means you can always leave. No data lock-in, no proprietary format.

---

## Section 8 — Comparison: AdClaw Host vs alternatives

### Title
**Hosted compared.**

### Compact table — only relevant alternatives (NOT our partners)

| | **AdClaw Host** | **OpenClaw self-host** | **Botpress** | **n8n Cloud** |
|-|-|-|-|-|
| Price entry | $10/mo | Free (your infra) | $89/mo | $24/mo |
| Multi-agent marketing personas | ✓ (unlimited custom) | Generic | ✗ | Generic |
| Marketing-specific tools | 60+ (Citedy) | ✗ | ✗ | ✗ |
| Bundled Citedy credits | 150 / 500 / 1,500 | ✗ | ✗ | ✗ |
| Bundled LLM messages | 500 / 2,000 / 6,000 | ✗ | ✗ | ✗ |
| Telegram team @-routing | ✓ | DIY | Multi-channel | ✓ (configured) |
| Auto-publish to blogs / socials | ✓ | DIY | ✗ | DIY |
| Setup time | 90s | minutes | minutes | minutes |
| Open source self-host alt | ✓ Apache 2.0 | ✓ MIT | ✓ AGPL | ✓ fair-code |

### Implementation note
DO and Railway are intentionally NOT in this table — they are partners that host AdClaw, not competitors to AdClaw Host. The comparison is against other agent/automation platforms.

---

## Section 9 — Hosted plan recap (link out)

### Title
**Hosted plans recap**

### Mini-pricing
Starter $10 (150 credits + 500 LLM messages) / Pro $29 (500 + 2,000) / Business $79 (1,500 + 6,000) — full details on [/pricing](/pricing).

### CTA
`Get hosted →`

### Or
`Stay on self-host: install →` (`pip install adclaw`)

### Or
`Deploy on DigitalOcean →` · `Deploy on Railway →` (partner links)

---

## Section 10 — FAQ (developer-flavored)

### Q: Will Citedy credits work without AdClaw?
A: Yes. Citedy has its own API. You can use Citedy MCP from any agent — Claude Desktop, Cursor, your custom code. AdClaw just bundles it.

### Q: Is the hosted version the exact same code?
A: Yes. AdClaw Host runs the same Docker image as `nttylock/adclaw:latest`. No proprietary fork.

### Q: Can I run hosted + self-host at the same time?
A: Yes, but they have separate workspaces. Use the Citedy account from the same email and the credits pool across both.

### Q: What about Keep Warm / always-on?
A: Add-on path on Pro / Business. Pricing not self-serve yet (we want fresh cost validation). Email support to discuss.

### Q: Multi-tenant for agencies?
A: Business plan supports multi-brand workflows but is single-workspace. True multi-tenant (separate isolated workspaces per client) is on roadmap — talk to us.

### Q: How do you make money if AdClaw is Apache 2.0?
A: Hosting + Citedy MCP credits + bundled LLM messages. The framework is free. We sell the operational reliability and the bundled marketing/LLM economics.

### Q: Source code commits / release cadence?
A: Active development. Release notes: github.com/Citedy/adclaw/releases.

---

## Section 11 — Final CTA

### Title
**Two paths. Same software.**

### CTAs side-by-side
- `Install free → pip install adclaw`
- `Hosted → $10/mo →`

---

## Section 12 — Footer

Same as hardcore home.

---

## Implementation summary

This page is mostly NEW content but built from existing materials:
- Self-host options (Card 1/2/3/4) — lifted from current home install block, added 4th card so DO and Railway each get their own card
- Comparison table to alternatives — extends current `/docs/comparison.md`, partners excluded
- TCO math — new, key honest-pitch block, partner-respectful
- Credits-anywhere section — clarifies a question developers will have
- Migration commands — assumes `adclaw export/import` CLI exists (verify before publishing)

### TODO before publishing
- [ ] Verify `adclaw export` / `adclaw import` CLI commands exist with these names
- [ ] Verify Citedy credit signup flow at citedy.com gives 100 free credits without AdClaw
- [ ] Confirm `nttylock/adclaw:latest` is identical to hosted version (architecturally yes, but document it)
- [ ] Check partner deal pages on DigitalOcean Marketplace and Railway template gallery for correct linkbacks
