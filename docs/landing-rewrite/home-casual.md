# adclaw.app — CASUAL HOME (default)

**Audience:** solo founder, SMB marketer, agency lead. Knows what an SEO article is. Does NOT know what Docker is. Spends day in Telegram and browser.

**Page goal:** Get them to click "Launch your office — $10/month" or to add bot to their Telegram group.

**Tone:** Direct, concrete, outcome-first. No framework vocabulary.

---

## Section 1 — Nav

Keep current nav structure. Change links:

- Logo: `AdClaw`
- Links: `Pricing` · `For developers →` · `Login` · `Get started`

Drop from nav: `Docs`, `GitHub`, `Docker` (they go to footer or `/dev`).

---

## Section 2 — Hero

### Headline
**Your AI marketing team.<br>In a browser. And in your Telegram.**

### Sub-headline
A private office with your own AI specialists — Strategist, Researcher, SEO Writer, Ads Manager, Analyst by default. Add as many more as you want. They publish first-class SEO/GEO content straight to your blog and socials, monitor competitors, write ads, and answer your team in Telegram. From $10/month.

### Primary CTA
`Launch your office — $10/month →` (links to `/pricing`)

### Secondary CTA
`See how it looks →` (anchor link to "What it looks like" section)

### Trust strip (below CTAs, small text)
`90-second launch  ·  Cancel anytime  ·  Apache 2.0 — you can self-host  ·  Cloudflare-secured, global CDN`

### Implementation note
Remove the current "cloud-card" structure with $10/month inside a card. The price moves to the headline area, the card disappears. Remove DigitalOcean/Railway buttons from hero — they move to `/dev`.

**Important framing**: do NOT say "5 specialists" as if it's a cap. The 5 are defaults. Every plan supports unlimited custom personas. Competitors monetize the persona count — we don't.

---

## Section 3 — Pain points (NEW BLOCK)

### Title
**The math nobody wants to do.**

### Subtitle
A US marketer costs your company $8,000–13,000/month fully loaded. You pay another $400–660/month per employee for software they barely use, because the tools don't talk to each other.

### 4 pain cards (2x2 grid on desktop, stacked on mobile)

**Card 1 — Tool sprawl**
> "I have 8 tools, 4 dashboards, and still no time."
>
> SEO in one tab, content in another, analytics somewhere else. Context lost on every handoff.

**Card 2 — Hidden software bill**
> "$500/month per employee — and the tools don't talk to each other."
>
> ChatGPT Team. Claude Team. Gemini Enterprise. HubSpot. SEMrush. Jasper. Canva. Power users on Pro / Max / Ultra tariffs easily burn $200–500 each.

**Card 3 — Expensive humans doing janitor work**
> "I pay a marketer $9,000/month to copy-paste between ChatGPT and a Google Sheet."
>
> Fully loaded marketer in the US runs $8K–13K/month. If 1.5–2 hours of their day is moving data between disconnected tools, that's $2,000–2,500/month evaporating into the gap between subscriptions.

**Card 4 — AI tools that don't know your business**
> "Five subscriptions, five logins, zero memory of your brand, your competitors, or last week's content."
>
> Every prompt starts from zero. Every tool is a stranger.

### Bottom line (after the cards)
> $4,000+/month for AI subscriptions and software that doesn't talk to itself. $30,000+/month for a team that spends 40% of its time being the duct tape. We replace the duct tape.

### Implementation note
New section. Place between Hero and "How it works". Use the existing `.features-grid` CSS but 2x2 layout.

---

## Section 4 — How it works (NEW BLOCK, 3 steps)

### Title
**One office. Your team — as big as you want. Always working.**

### Step 1 — Subscribe
**$10. 90 seconds.** Your private workspace launches in the cloud. Backups, auto-sleep, Cloudflare-secured isolation — handled.

### Step 2 — Meet your team
Open your office in the browser. Five default specialists are already there: Strategist, Researcher, SEO Writer, Ads Manager, Analyst. Add as many more as you want — Brand Voice, PR, CRO, Email, Outreach — no cap, no per-persona pricing. Talk to them like real employees.

### Step 3 — Or invite them to Telegram
Connect your bot, drop it into your team's Telegram group. Anyone on your team can ask `@researcher`, `@writer`, `@analyst` — or any persona you've added — they answer in the chat. Everyone sees the work.

### Implementation note
3-column horizontal flow. Similar to current "After checkout" flow on `/pricing` but on home page. Each step gets a simple icon + 2-line description. **Critical:** Step 2 must explicitly state the team is unlimited — this is a competitive moat (Jasper/Copy.ai/most n8n templates monetize per persona).

---

## Section 5 — Telegram team block (NEW BLOCK — explicit user request)

### Title
**Your AI team. In the chat your team already uses.**

### Sub
Add the AdClaw bot to your company Telegram group. Your specialists. One shared context. Real work in messages your whole team can see.

### Example conversation (visual mockup)

Use one of the dialog scenarios from `telegram-dialogs.md`. Founder writes those prompts to live bots, screenshots the result, and we drop the real screenshots into this section. So this is NOT synthesized chat UI — it's actual product output.

Start with the "Competitor + Content + Analytics in one thread" scenario (Scenario A in `telegram-dialogs.md`). Three people in the group, three different specialists answering. Fits one phone screen.

### Caption below mockup
**One bot. Whole team. Real data.** No external tools. No context switching. No more "wait, where's that report?"

### CTA
`See the full pricing →` → `/pricing`

(Do NOT link to a live demo bot. Public demo bots get griefed by spammers.)

### Implementation note
This is the most important new block. Make it visually distinct — Telegram-style chat bubbles with avatars, but the bubbles contain real screenshot data from the founder's staged sessions. Mobile: full-width chat. Desktop: chat on left, copy on right OR centered chat with caption below.

---

## Section 6 — What it looks like (NEW BLOCK — explicit user request)

### Title
**See the office.**

### Two-tab toggle
- **Tab 1: Web dashboard** — screenshot of AdClaw web UI showing persona cards with status, model, last activity
- **Tab 2: Telegram** — screenshot of bot in group chat

### Captions for each
**Web:** "Your dashboard. Each persona has its own chat tab, can be paused, configured, scheduled. Add more specialists in two clicks."

**Telegram:** "Same agents, in your team chat. @-mention to route. Group-wide visibility."

### Implementation note
Need actual screenshots. Placeholder needed. Tab switcher should be CSS-only (radio buttons) or simple JS toggle.

### TODO
- Take screenshot: AdClaw web UI with 5+ personas, English UI only
- Take screenshot: real Telegram group chat with bot doing @-routing (founder writes prompts from `telegram-dialogs.md`, screenshots the actual replies)

---

## Section 7 — What's included (REPLACES current "What you get" feature grid)

### Title
**What your team can do.**

### Outcome-focused grid (2x3 on desktop)

**1. Publish SEO/GEO articles to your blog**
500–8,000 words in 55 languages. AI-generated illustrations, voice-over, internal links. Auto-publishes to your blog (your domain) and to your connected social accounts. First-class SEO/GEO optimization — not draft text in a chat window.

**2. Track competitors daily**
Tell us 3–10 competitors. Get daily diff reports: new pages, new pricing, new features, new content drops, social activity.

**3. AI video shorts for socials**
5–15 second UGC-style videos for Instagram Reels, TikTok, YouTube Shorts. Auto-captions, AI voiceover, AI avatar, lip-sync.

**4. Lead magnets on demand**
Checklists, frameworks, swipe files. Branded, formatted, hosted as a downloadable PDF on a unique URL.

**5. Adapt one post for 7 platforms**
Write once. Get LinkedIn, X (article + thread), Facebook, Reddit, Threads, Instagram, YouTube Shorts versions — each tuned to the platform — and auto-publish.

**6. Trend scouting + buyer intent**
Daily report from X/Twitter and Reddit. Trending topics in your niche, real buyer-intent signals ("looking for Jasper alternatives"), ready-to-write angles.

### Below the grid (small text)
> All six above are powered by your monthly **Citedy credits** — the marketing pipeline that publishes to your domain. On top of that, your bundled LLM messages let you chat freely with your team for everyday drafting, research, and the 100+ built-in skills + 25+ MCP servers. Run out of credits or messages? Plug in your own OpenAI / Anthropic / Gemini / DeepSeek key — AdClaw keeps working.

### Implementation note
Replace the current 12-card feature grid (Multi-agent personas, 23 LLM providers, etc.) with this 6-card outcome grid. Keep the same `.features-grid` CSS.

---

## Section 8 — Plans teaser (NEW BLOCK)

### Title
**Three plans. Unlimited specialists on every plan.**

### Mini-plans (compact 3-column)

| | **Starter $10** | **Pro $29** (Recommended) | **Business $79** |
|-|-|-|-|
| Citedy credits / month | 150 | 500 | 1,500 |
| LLM messages / month | 300 | 1,500 | 5,000 |
| Custom specialists | Unlimited | Unlimited | Unlimited |
| Telegram team members | 3 | 10 | Unlimited |
| Best for | Solo / side project | Active solopreneur | Agency / team |

### Below the table (small text)
> Bring your own LLM key (OpenAI / Anthropic / Gemini / DeepSeek) for unlimited chat on top of bundled messages.

### CTA
`See full pricing →` → `/pricing`

### Implementation note
Mini-pricing on home page is a conversion booster — visitor doesn't need to navigate to see if they can afford it. "Unlimited specialists on every plan" is the differentiator — keep it visible.

---

## Section 9 — Trust / FAQ teaser (small)

### Title
**No lock-in. Open source. Secured at the edge.**

### 4 trust points (inline)

- **Apache 2.0** — fork it, run it on your laptop, never pay us. Same software.
- **Your LLM keys, your data** — bring your own OpenAI/Anthropic/Gemini/DeepSeek key. We don't store them.
- **Cloudflare Sandbox + global CDN** — workspace isolation, DDoS protection, fast wake from anywhere in the world.
- **Cancel anytime** — your work exports. No retention games.

### Link
`See developer self-host options →` → `/dev`

---

## Section 10 — Final CTA

### Title
**Hire your AI marketing team. Today.**

### Sub
$10. 90 seconds. Cancel whenever.

### CTA
`Launch your office →` → `/pricing`

### Secondary
`I'm a developer — show me self-host →` → `/dev`

---

## Section 11 — Footer

Keep current footer. Add link to `/dev`. Drop Docker/GitHub icons to a smaller "For developers" subline.

```
[Logo] AdClaw

Product:   Pricing  ·  Telegram bot  ·  How it looks
For devs:  Self-host  ·  GitHub  ·  Docker Hub  ·  Docs
Company:   Citedy  ·  Blog  ·  Contact

© 2026 Citedy  ·  Apache 2.0  ·  Cloudflare-secured  ·  Built by a solo founder
```

---

## REMOVED from current home page

These move to `/dev` or disappear:

- `pip install adclaw` install block in hero (moves to `/dev`)
- Docker variant selector (moves to `/dev`)
- DigitalOcean + Railway deploy buttons (moves to `/dev`)
- "23 LLM providers, 100+ models" feature card (replaced with outcomes)
- "Shared memory (AOM)" card (gone, too technical)
- "LLM auto-fallback" card (gone, too technical)
- "Security built-in 208-pattern scanner" card (replaced with "Cloudflare Sandbox" trust block)
- "Self-healing skills" card (gone)
- "7 chat channels" card (replaced with "Telegram team" block)
- Clawsy AgentHub section (moves to `/dev`)
- Full comparison table (CoPaw, CrewAI, Dify, OpenClaw MC) (moves to `/dev`)
- "Open source. Apache 2.0." final section with `View on GitHub` (replaced with marketing CTA)

---

## Implementation order

1. Write copy as above
2. Build pain-points block (new component) — use the $8K–13K + $500/employee + $4K/$30K numbers
3. Build "How it works" 3-step (new component) — explicitly state unlimited specialists in Step 2
4. **Build Telegram chat mockup block** (critical, custom CSS) — use real screenshots from `telegram-dialogs.md` scenarios
5. Build "What it looks like" tabs (needs screenshots)
6. Replace feature grid with outcome grid
7. Add mini-plans block with the new "unlimited specialists" row
8. Add trust block with Cloudflare line
9. Final CTA
10. Footer update
11. Add `/dev` route serving `home-hardcore.md` content
