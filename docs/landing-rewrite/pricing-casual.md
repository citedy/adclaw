# adclaw.app/pricing — CASUAL PRICING (default)

**Audience:** the visitor who clicked "Launch your office — $10/month" on home. Now they want to know what they actually get.

**Page goal:** Convert to Starter or Pro signup. Kill the "what's a credit" confusion. Make clear that running out of credits does NOT brick the workspace — bring your own LLM key and AdClaw keeps working.

**Tone:** Plain. Outcomes. No "fair-use active min/mo" jargon. Honest about what credits do and don't gate.

---

## Section 1 — Nav

Same as casual home.

---

## Section 2 — Hero

### Breadcrumb
`adclaw.app / pricing`

### Headline
**Hire your AI marketing team.<br>From $10/month.**

### Sub
A private cloud office with your own specialists — defaults to 5 (Strategist, Researcher, SEO Writer, Ads Manager, Analyst), add as many more as you want on every plan. We host, back up, and launch in 90 seconds. You manage marketing. From content to ads to analytics — all in one chat.

### Hero CTAs
`Choose a plan` (anchor #plans) · `See how it looks (Telegram demo)` → home `#what-it-looks-like`

### Implementation note
Replace current "Open Host dashboard" secondary button. That goes inside the plans (each plan has its own CTA).

---

## Section 3 — Plans (REPLACE CURRENT BLOCK)

3-column. Same visual structure as current. Outcomes-first copy.

### Plan 1 — Starter

**Label:** Starter
**Name:** Solo Operator
**Price:** $10 / month
**Pill:** 150 Citedy credits + 300 LLM messages per month

**Description (1 sentence):**
For freelancers, side projects, and "I want to try this without commitment."

**What's bundled per month:**
- **150 Citedy credits** — for the first-class, SEO/GEO-optimized, auto-published-to-your-domain content pipeline (see menu below)
- **300 bundled LLM messages** — for chat with your team, drafting, and using the 100+ built-in skills
- **Unlimited custom specialists** — add whatever roles you want
- **3-member Telegram team bot**
- **Web office + Telegram**

**Included:**
- Private hosted AdClaw workspace, Cloudflare-secured
- 5 default specialist personas + unlimited custom personas you build
- Auto-launch, auto-sleep, backups
- Bring your own LLM key any time (OpenAI / Anthropic / Gemini / DeepSeek) — unlimited chat after the bundle
- 100+ built-in skills, 25+ MCP servers (Citedy included)
- Apache 2.0 self-host alternative

**CTA:** `Start Solo Operator — $10`

---

### Plan 2 — Pro (Recommended)

**Label:** Pro
**Name:** Growth Engine
**Price:** $29 / month
**Pill:** 500 Citedy credits + 1,500 LLM messages per month

**Description (1 sentence):**
For active solopreneurs and 2–5 person teams running real marketing.

**What's bundled per month:**
- **500 Citedy credits** — see menu below for what they buy
- **1,500 bundled LLM messages**
- **Unlimited custom specialists**
- **10-member Telegram team bot**
- **Multi-channel auto-publishing** to LinkedIn, X (article + thread), Reddit, Facebook, Instagram, Threads, YouTube Shorts

**Everything in Solo Operator, plus:**
- 3× workspace capacity
- Priority queue
- Custom persona builder (the same one Solo gets, but with priority response)

**CTA:** `Start Growth Engine — $29`

---

### Plan 3 — Business

**Label:** Business
**Name:** Agency Office
**Price:** $79 / month
**Pill:** 1,500 Citedy credits + 5,000 LLM messages per month

**Description (1 sentence):**
For agencies, 5+ person teams, and client-facing workflows.

**What's bundled per month:**
- **1,500 Citedy credits**
- **5,000 bundled LLM messages**
- **Unlimited custom specialists**
- **Unlimited team members in Telegram group**
- **Multi-client workflows** (your team works on multiple brands)
- **White-glove onboarding**

**Everything in Growth Engine, plus:**
- 5× workspace capacity
- Multi-brand support
- Commercial support path
- Priority response

**CTA:** `Start Agency Office — $79`

---

### Bottom note (replaces current auto-sleep callout)

> **Citedy credits power the "publish to your domain" pipeline** — articles auto-published to your blog, AI shorts to your socials, lead magnets hosted on unique URLs, competitor reports, content gap analyses. Real first-class SEO/GEO content, not draft text in a chat window. See the full action menu below.

> **Bundled LLM messages power chat with your team** — drafts, research, brainstorms, and the 100+ built-in skills + 25+ MCP servers. When you hit the bundled cap, plug in your own OpenAI / Anthropic / Gemini / DeepSeek key — AdClaw keeps working. Your workspace does not deactivate.

> **Auto-sleep saves you money.** Your workspace sleeps after 10 idle minutes — same way an office turns off the lights at night. Wake takes ~90 seconds. While you're working, no waiting.

### Implementation note
Replace the current `.plan` description text. Replace the bullet list (`+ Private hosted...` etc.) with the **"What's bundled per month"** outcome list. The "Included" / infrastructure list moves below in smaller text.

The current `200 / 1,000 / 5,000` active-min/mo field is dropped from the primary card — it lives in the FAQ if at all.

---

## Section 4 — What credits buy (NEW BLOCK — REWRITE WITH REAL CITEDY COSTS)

### Title
**Every credit, every action. 1 credit = $0.01.**

### Sub
Every plan includes monthly Citedy credits. Use them however you want. These are the real, published per-action costs (same numbers your agent sees over the API).

### Grid (clean table, group by category)

#### Articles (published to your blog + auto-distributed to your socials)

| Action | Credits |
|--------|---------|
| Turbo article (~800w, 5–15s) | 2 |
| Turbo+ article (~800w, with web search, 10–25s) | 4 |
| Mini article (~500w) | 15 |
| Standard article (~1000w) | 20 |
| Full article (~1500w) | 33 |
| Pillar article (~2500w) | 48 |
| + AI illustrations | +9 to +36 |
| + AI voice-over (55 languages) | +10 to +55 |

#### Video shorts (UGC-style, auto-published to Reels/TikTok/YouTube Shorts)

| Action | Credits |
|--------|---------|
| 1 hook script | 1 |
| 1 AI avatar | 3 |
| 1 video segment (5s) | 60 |
| 1 video segment (10s) | 130 |
| 1 video segment (15s) | 185 |
| Merge segments + subtitles | 5 |
| **Full 10s video, finished & ready to publish** | **~139 ($1.39)** |

#### Research & competitor intelligence

| Action | Credits |
|--------|---------|
| Trend scan (fast → ultra+) | 2 to 8 |
| Competitor discovery | 20 |
| Competitor deep scout | 25 to 50 |
| Content gap analysis | 40 |
| X intent scout | 35 to 70 |
| Reddit intent scout | 30 |
| LLM visibility check (per AI platform) | 3 |

#### Lead generation

| Action | Credits |
|--------|---------|
| Lead magnet (text PDF, ready to publish) | 30 |
| Lead magnet (with AI illustrations) | 100 |
| Upload product knowledge to memory | 1 |

#### Social & distribution

| Action | Credits |
|--------|---------|
| Adapt one article for one platform | ~5 |
| Publish to your blog or socials | 0 (free) |
| Schedule a post | 0 (free) |

#### Content ingestion (transcribe & analyze)

| Action | Credits |
|--------|---------|
| Web article → clean text | 1 |
| PDF → text | 2 |
| YouTube under 10 min | 5 |
| YouTube 10–30 min | 15 |
| YouTube 30–60 min | 30 |
| YouTube 60–120 min | 55 |
| Podcast under 10 min | 3 |
| Podcast 10–30 min | 8 |

### Real monthly outputs by plan (pick one column; mix & match within a plan however you want)

| Action | Starter (150 credits) | Pro (500) | Business (1,500) |
|--------|-----------------------|-----------|------------------|
| Turbo articles (~800w) | ~75 | ~250 | ~750 |
| Standard articles (~1000w) | ~7 | ~25 | ~75 |
| Pillar articles (~2500w) | ~3 | ~10 | ~31 |
| LLM visibility checks (across 9 AI platforms each) | ~5 | ~18 | ~55 |
| Competitor discoveries | ~7 | ~25 | ~75 |
| Content gap analyses | ~3 | ~12 | ~37 |
| AI video shorts (5s, finished) | ~2 | ~7 | ~22 |
| AI video shorts (10s, finished) | ~1 | ~3 | ~10 |
| Text lead magnets | ~5 | ~16 | ~50 |

### Important callout below the table
> Numbers above show what one plan's credits do if you spend them all on one action type. In practice you mix — say 10 articles, 2 video shorts, 1 competitor deep scout, and 5 lead magnets in the same month. Credits don't expire mid-month.

> **And on top of credits**, you have 300 / 1,500 / 5,000 bundled LLM messages for chatting with your team. Run out of those too? Plug in your own LLM key — chat, drafts, brainstorms, all 100+ built-in skills, and all 25+ MCP servers keep working **for free** (your own LLM cost only). The Citedy credits are specifically for the "first-class, SEO/GEO-optimized, auto-published-to-your-domain-and-socials" content pipeline. Everything else in AdClaw runs on your LLM key.

### Implementation note
This is the killer block for converting hesitant buyers. The "what's a credit" question dies here. Make the table visually clean. Source of truth: citedy.com/agents and citedy.com/skill.md — keep these numbers in sync if Citedy pricing changes.

---

## Section 5 — Comparison (REPLACE CURRENT TABLE)

Replace the current infrastructure table with an outcomes table.

### Title
**Compare plans**

| | **Starter** | **Pro** (Recommended) | **Business** |
|-|-|-|-|
| **Price** | $10/mo | $29/mo | $79/mo |
| **Citedy credits / month** | 150 | 500 | 1,500 |
| **Bundled LLM messages / month** | 300 | 1,500 | 5,000 |
| **Custom specialists** | Unlimited | Unlimited | Unlimited |
| **Telegram team members** | 3 | 10 | Unlimited |
| **Multi-client / multi-brand** | — | — | ✓ |
| **Auto-publish to blog & socials** | ✓ | ✓ | ✓ |
| **Bring your own LLM key** | ✓ | ✓ | ✓ |
| **All 100+ built-in skills + 25+ MCP servers** | ✓ | ✓ | ✓ |
| **Cloudflare-secured workspace** | ✓ | ✓ | ✓ |
| **Support** | Email | Priority | White-glove |
| **Self-host alternative** | Free, Apache 2.0 | Free, Apache 2.0 | Free, Apache 2.0 |

### Implementation note
Add small print below the table: "Need more? Contact us — agency-tier and white-label available." The persona-count row is intentionally omitted — every plan is unlimited.

---

## Section 6 — After checkout (KEEP CURRENT but simplify copy)

Keep the current 4-step flow but rewrite for marketer language.

1. **Pay** — Stripe checkout via Citedy. Card or invoice.
2. **Open your office** — your dashboard shows: Launch, Wake, Sleep, Open. Click Launch.
3. **Meet your team** — your specialists waiting. Web UI + Telegram setup wizard. Add more specialists any time, no per-persona fee.
4. **Get to work** — first article in ~10 minutes. Cancel anytime if it's not for you.

### Implementation note
Drop technical terms: `Stripe billing context`, `Host wrapper`, `LLM keys configured inside AdClaw`. Move those to FAQ.

---

## Section 7 — FAQ (REWRITE)

Replace current FAQ with marketer-focused FAQ. Order matters — most-asked first.

### Q: How fast can I have my first SEO article?
A: ~10 minutes from signup. Click Launch (90 seconds). Open Web UI. Tell the SEO Writer your topic. Article writes itself, you review, click publish (or it auto-publishes to your blog and adapts to all connected socials).

### Q: How many specialists can I have?
A: Unlimited, on every plan. The 5 defaults — Strategist, Researcher, SEO Writer, Ads Manager, Analyst — are starting points. Add Brand Voice, PR, CRO, Email, Outreach, an SEO Auditor, an Ads Optimizer, anything. We do not charge per persona. (Most competitors do — we don't think that's fair.)

### Q: What happens when I run out of Citedy credits?
A: Your AdClaw workspace keeps working. The Citedy-powered actions (auto-publishing to your domain, AI video shorts, scouts, gap analyses, lead magnets) pause until next month or until you top up. Everything else — chat with your team, drafting, brainstorming, all 100+ built-in skills, all 25+ MCP servers — keeps working on your bundled LLM messages or on your own LLM key.

### Q: What happens when I run out of bundled LLM messages?
A: Plug in your own LLM key (OpenAI / Anthropic / Gemini / DeepSeek). Unlimited chat from then on at your provider's rate. Workspace does not deactivate. Nothing is deleted.

### Q: Do I need my own LLM key at all?
A: No — bundled LLM messages and Citedy credits cover normal usage on every plan. But you can plug in your own key any time, and the keys live inside your workspace (we never see them). Most users do this for unlimited usage and provider choice.

### Q: Can my whole team use it via Telegram?
A: Yes. Drop the bot into your team's Telegram group. Anyone can @mention any persona. Starter: 3 members. Pro: 10. Business: unlimited.

### Q: What if I cancel?
A: Workspace pauses. You can export everything (memory, configs, generated content). Reactivate within 90 days to restore. After 90 days, deleted per retention policy.

### Q: I'm technical. Can I self-host instead?
A: Yes. AdClaw is Apache 2.0. `pip install adclaw` or `docker run`. See [/dev](https://adclaw.app/dev) for full guide.

### Q: Why does my workspace sleep?
A: To keep your monthly price at $10–79. Idle workspaces cost us compute. After 10 idle minutes, we sleep yours. Wake = ~90 seconds when you come back. Active work doesn't pause.

### Q: Is my data private?
A: Yes. Your workspace is Cloudflare-isolated. Your LLM keys never leave the workspace. Backups are encrypted. You can delete everything via the dashboard.

### Q: Do I own the content the AI generates?
A: 100%. Apache 2.0 framework, you own all outputs.

### Q: What's the difference between this and ChatGPT / Jasper?
A: ChatGPT is one model, one chat. Jasper writes one piece at a time and locks MCP behind a $59/mo plan. AdClaw is your team of specialists — defaults to 5, unlimited custom — working together with memory of your brand, your competitors, your past content. They auto-publish to your blog (your domain) and your socials, monitor competitors daily, answer your team in Telegram. Different category.

### Implementation note
Drop these from current FAQ: "What am I buying", "Why does my workspace sleep" (kept, but rephrased), "Can I keep it always on" (Keep Warm — move to power-user docs).

---

## Section 8 — Final CTA

### Title
**Start at $10. Cancel anytime.**

### CTAs
- `Start Solo Operator — $10` (Starter)
- `Start Growth Engine — $29` (Pro, highlighted)
- `Start Agency Office — $79` (Business)

### Below
`Prefer to self-host? See developer plans →` → `/pricing/self-host`

---

## Section 9 — Footer

Same as casual home.

---

## REMOVED from current pricing page

- "Autonomous office roles" / "Core roles" row (vague, replaced with concrete outcomes + "unlimited specialists" framing)
- "Fair-use workspace budget: 200/1000/5000 active min/mo" (moves to small print or removed)
- "Keep Warm: Eligible add-on path" (moves to power-user docs)
- Generic "Cloud workspaces cost money while running" callout (replaced with outcome-focused note)
- Any claim that runs in the form "this plan gives you N articles per month" without the "or any mix" caveat — replaced with the real Citedy menu so the visitor can do their own math
- Any implication that running out of credits kills the bot — corrected: workspace keeps working on user's LLM key
