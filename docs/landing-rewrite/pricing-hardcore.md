# adclaw.app/pricing/self-host — HARDCORE PRICING

**URL:** `adclaw.app/pricing/self-host` (linked from `/pricing` and from `/dev`)

**Audience:** developer evaluating self-host vs hosted economics. Wants total cost of ownership numbers.

**Page goal:** Convert "I'll self-host" types to either (a) clean self-host with Citedy credits, or (b) hosted because it's cheaper than their time.

**Tone:** Honest math. Show the real tradeoffs.

---

## Section 1 — Nav

Same.

---

## Section 2 — Hero

### Breadcrumb
`adclaw.app / pricing / self-host`

### Headline
**Self-host AdClaw.<br>Or pay us to do it.**

### Sub
AdClaw is Apache 2.0. Run it on your laptop, your VPS, or our cloud. Citedy MCP credits work the same way regardless of where the agent runs.

### Hero CTAs
`See total cost comparison ↓` · `Get hosted instead →`

---

## Section 3 — Self-host options

### Title
**Three ways to run AdClaw on your own infra.**

### 3-card grid

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

**Card 2 — Docker on your VPS**
```bash
docker run -d -p 8088:8088 nttylock/adclaw:latest
```
- VPS: $5–20/mo (Hetzner, Digital Ocean, Hostinger)
- Persistent volume for memory + skills
- Always-on (no sleep)
- LLM cost: bring your own keys
- Citedy credits: optional, separate signup

**Card 3 — DigitalOcean / Railway 1-click**
- DigitalOcean: VPS from $10/mo, 1-click marketplace deploy
- Railway: Hobby plan, ≥2GB RAM (~$5–10/mo)
- Auto-updates via image tag
- Citedy credits: optional, separate signup

### Implementation note
This is current home page content, just lifted and given a dedicated section.

---

## Section 4 — Hosted vs self-host TCO (NEW BLOCK, KEY)

### Title
**Total cost of ownership.**

### Sub
What it actually costs to run AdClaw for one solo marketer in real conditions.

### Comparison table

| Cost item | **Self-host (DO VPS)** | **AdClaw Host (Pro)** |
|-----------|------------------------|------------------------|
| Infrastructure | $10/mo VPS | Included |
| Setup time (initial) | ~2–4 hours | 90 seconds |
| Monthly maintenance | ~1–2 hours (updates, debug) | 0 |
| Backups | Manual (cron + S3) ~$2/mo | Included |
| SSL / domain config | Manual | Included |
| Citedy credits | Pay-as-you-go (~$30/mo for 500 credits) | 500 credits included |
| LLM keys | BYO (~$10–30/mo) | BYO (same) |
| **Total monthly $** | **~$42/mo + 3hrs labor** | **$29/mo** |

### Verdict (callout)
> **At Pro ($29), hosted is cheaper than self-host for everyone whose time costs more than $0/hour.** Self-host wins only if you (a) already have a server doing other things, (b) want full source control, or (c) need on-prem for compliance.

### Implementation note
This is the honest pitch — hosted is cheaper, not because we're charging less than cost, but because Citedy credits are bundled. Show the math, don't hide it.

---

## Section 5 — When to self-host

### Title
**When self-host is the right call.**

### List

- **You have compliance constraints** — GDPR data residency, HIPAA, internal policy mandates on-prem.
- **You already run servers** — adding one more container has marginal cost.
- **You want to fork** — modifying the source, adding custom skills, embedding in your product.
- **You're a developer learning** — best way to understand the architecture is to run it.
- **You don't need 60+ Citedy MCP tools** — happy with the 130 built-in skills + your own MCP servers.

### When hosted wins
- You have a marketing job, not a devops job.
- You want Telegram bot working in 90 seconds.
- You want Citedy credits bundled at fair-market rates.
- Your time costs more than $20/hour.

---

## Section 6 — Citedy credits work the same way

### Title
**Same credits. Same tools. Anywhere you run AdClaw.**

### Body
The Citedy MCP server is bundled inside AdClaw. Whether you run AdClaw on your laptop, your VPS, or our hosted cloud — you can use Citedy credits the same way.

- **Free tier on signup:** 100 Citedy credits, no card.
- **Top-ups:** $1 = 25 credits (better rates on bigger packs).
- **Subscription bundles** (only in AdClaw Host plans): 150 / 500 / 1500 credits included monthly.

### Credit costs (link to /pricing for the full menu)
- 1 SEO article ≈ 15 credits
- 1 AI video short ≈ 30 credits
- 1 lead magnet ≈ 12 credits
- Full menu: [pricing → what credits buy](/pricing#credits)

### Implementation note
Important: self-hosters get a credit balance separately at citedy.com. Hosted users get credits bundled into their AdClaw Host plan. Same credits, different billing path. Be explicit so devs don't think they need to host to get marketing tools.

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

### Compact table — only relevant alternatives

| | **AdClaw Host** | **OpenClaw self-host** | **Botpress** | **n8n Cloud** |
|-|-|-|-|-|
| Price entry | $10/mo | Free (your infra) | $89/mo | $24/mo |
| Multi-agent marketing personas | ✓ | Generic | ✗ | Generic |
| Marketing-specific tools | 60+ (Citedy) | ✗ | ✗ | ✗ |
| Telegram team @-routing | ✓ | DIY | Multi-channel | ✓ (configured) |
| Auto-publish to blogs / socials | ✓ | DIY | ✗ | DIY |
| Setup time | 90s | hours | hours | hours |
| Open source self-host alt | ✓ Apache 2.0 | ✓ MIT | ✓ AGPL | ✓ fair-code |

---

## Section 9 — Hosted plan recap (link out)

### Title
**Hosted plans recap**

### Mini-pricing
Starter $10 / Pro $29 / Business $79 — full details on [/pricing](/pricing).

### CTA
`Get hosted →`

### Or
`Stay on self-host: install →` (`pip install adclaw`)

---

## Section 10 — FAQ (developer-flavored)

### Q: Will Citedy credits work without AdClaw?
A: Yes. Citedy has its own API. You can use Citedy MCP from any agent — Claude Desktop, Cursor, your custom code. AdClaw just bundles it.

### Q: Is the hosted version the exact same code?
A: Yes. AdClaw Host runs the same Docker image as `nttylock/adclaw:latest`. No proprietary fork.

### Q: Can I run hosted + self-host at the same time?
A: Yes, but they have separate workspaces. Use the Citedy account from the same email and credits pool across both.

### Q: What about Keep Warm / always-on?
A: Add-on path on Pro / Business. Pricing not self-serve yet (we want fresh cost validation). Email support to discuss.

### Q: Multi-tenant for agencies?
A: Business plan supports multi-brand workflows but is single-workspace. True multi-tenant (separate isolated workspaces per client) is on roadmap — talk to us.

### Q: How do you make money if AdClaw is Apache 2.0?
A: Hosting + Citedy MCP credits. The framework is free. We sell the operational reliability and the marketing-specific tool layer.

### Q: Source code commits / release cadence?
A: Active development. Release notes: github.com/Citedy/adclaw/releases. Current: v1.0.6.

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
- Self-host options (Card 1/2/3) — lifted from current home install block
- Comparison table to alternatives — extends current `/docs/comparison.md`
- TCO math — new, key honest-pitch block
- Credits-anywhere section — clarifies a question developers will have
- Migration commands — assumes `adclaw export/import` CLI exists (verify before publishing)

### TODO before publishing
- [ ] Verify `adclaw export` / `adclaw import` CLI commands exist with these names
- [ ] Verify Citedy credit signup flow at citedy.com gives 100 free credits without AdClaw
- [ ] Confirm `nttylock/adclaw:latest` is identical to hosted version (architecturally yes, but document it)
