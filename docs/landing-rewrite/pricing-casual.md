# adclaw.app/pricing — CASUAL PRICING (default)

**Audience:** the visitor who clicked "Launch your office — $10/month" on home. Now they want to know what they actually get.

**Page goal:** Convert to Starter or Pro signup. Reduce "what's a credit" confusion.

**Tone:** Plain. Outcomes. No "fair-use active min/mo" jargon.

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
A private cloud office with 5 specialists. We host, back up, and launch in 90 seconds. You manage marketing. From content to ads to analytics — all in one chat.

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
**Pill:** 150 monthly Citedy credits

**Description (1 sentence):**
For freelancers, side projects, and "I want to try this without commitment."

**What you can do per month (this is the new key list):**
- ~10 SEO articles published to your blog
- 1 competitor on daily watch
- Lead magnets on demand
- Telegram team bot (up to 3 group members active)
- Web office + Telegram

**Included:**
- Private hosted AdClaw workspace
- 5 specialist personas (Strategist, Researcher, SEO Writer, Ads Manager, Analyst)
- Auto-launch, auto-sleep, backups
- Apache 2.0 self-host alternative

**CTA:** `Start Solo Operator — $10`

---

### Plan 2 — Pro (Recommended)

**Label:** Pro
**Name:** Growth Engine
**Price:** $29 / month
**Pill:** 500 monthly Citedy credits

**Description (1 sentence):**
For active solopreneurs and 2–5 person teams running real marketing.

**What you can do per month:**
- ~30 SEO articles published to your blog
- ~10 AI video shorts (Reels/TikTok/Shorts)
- 3 competitors on daily watch
- Lead magnets + landing page copy
- Multi-channel social posting (LinkedIn, X, Reddit, Instagram)
- Telegram team bot (up to 10 active members)
- Custom personas (build your own specialists)

**Everything in Solo Operator, plus:**
- 3× workspace capacity
- Priority queue
- Custom persona builder

**CTA:** `Start Growth Engine — $29`

---

### Plan 3 — Business

**Label:** Business
**Name:** Agency Office
**Price:** $79 / month
**Pill:** 1,500 monthly Citedy credits

**Description (1 sentence):**
For agencies, 5+ person teams, and client-facing workflows.

**What you can do per month:**
- ~100 SEO articles across multiple sites
- ~30 AI video shorts
- 10 competitors on watch
- Multi-client workflows (your team works on multiple brands)
- Unlimited team members in Telegram group
- White-glove onboarding

**Everything in Growth Engine, plus:**
- 5× workspace capacity
- Multi-brand support
- Commercial support path
- Priority response

**CTA:** `Start Agency Office — $79`

---

### Bottom note (replaces current auto-sleep callout)

> **What's a Citedy credit?** A unit of marketing automation. Roughly: 1 SEO article = ~15 credits, 1 video short = ~30 credits, 1 competitor report = ~3 credits, 1 lead magnet = ~12 credits. Exact costs in the [credit guide](#credits).

> **Auto-sleep saves you money.** Your workspace sleeps after 10 idle minutes — same way an office turns off the lights at night. Wake takes ~90 seconds. While you're working, no waiting.

### Implementation note
Replace the current `.plan` description text. Replace the bullet list (`+ Private hosted...` etc.) with the **"What you can do per month"** outcome list. The "Included" / infrastructure list moves below in smaller text.

The credit-pill stays. Active min/mo (current `200 / 1,000 / 5,000`) moves to a tooltip or sub-line, not a primary visible field.

---

## Section 4 — What credits buy (NEW BLOCK)

### Title
**What can your AI team do? Here's the menu.**

### Sub
Every plan includes monthly Citedy credits. Use them however you want.

### Grid (4 columns or 2x4)

| Action | Credit cost | What you get |
|--------|-------------|--------------|
| **1 SEO article** | ~15 credits | 500–8000 words, in 55 languages, auto-published to your blog with images and citations |
| **1 AI video short** | ~30 credits | 30-second UGC-style video with voiceover, captions, music. Reels/TikTok-ready |
| **1 lead magnet** | ~12 credits | Branded checklist, framework, or swipe file. PDF, ready to download |
| **1 competitor report** | ~3 credits | Daily diff: new pages, pricing changes, content drops, social activity |
| **1 social post pack** | ~5 credits | One topic → 5 platform versions (LinkedIn, X, Facebook, Reddit, Instagram) |
| **1 trend scout report** | ~2 credits | Today's trending topics in your niche on X and Reddit, with angles |
| **1 SEO audit** | ~8 credits | Full audit of one page or one competitor's page, with action items |
| **1 ad copy pack** | ~6 credits | 5–10 ad copy variations for one campaign, tested hooks |

### CTA below grid
**Pro plan = 500 credits = ~30 articles or ~15 videos or any mix you want.**

### Implementation note
This is the killer block for converting hesitant buyers. The "what's a credit" question dies here. Make the table visually clean.

---

## Section 5 — Comparison (REPLACE CURRENT TABLE)

Replace the current infrastructure table (Hosted workspace / Autonomous office roles / Citedy credits / Fair-use budget / Auto-sleep / Launch / Backups / Keep Warm) with an outcomes table.

### Title
**Compare plans**

| | **Starter** | **Pro** (Recommended) | **Business** |
|-|-|-|-|
| **Best for** | Solo / side project | Active solopreneur, small team | Agency / 5+ team |
| **SEO articles/mo** | ~10 | ~30 | ~100 |
| **AI video shorts/mo** | — | ~10 | ~30 |
| **Competitor watch** | 1 | 3 | 10 |
| **Team members in Telegram** | 3 | 10 | Unlimited |
| **Custom personas** | — | ✓ | Unlimited |
| **Multi-client / multi-brand** | — | — | ✓ |
| **Auto-publish to blog & socials** | ✓ | ✓ | ✓ |
| **Support** | Email | Priority | White-glove |
| **Self-host alternative** | Free, Apache 2.0 | Free, Apache 2.0 | Free, Apache 2.0 |

### Implementation note
Add small print below the table: "Need more? Contact us — agency-tier and white-label available."

---

## Section 6 — After checkout (KEEP CURRENT but simplify copy)

Keep the current 4-step flow but rewrite for marketer language.

1. **Pay** — Stripe checkout via Citedy. Card or invoice.
2. **Open your office** — your dashboard shows: Launch, Wake, Sleep, Open. Click Launch.
3. **Meet your team** — 5 specialists waiting. Web UI + Telegram setup wizard.
4. **Get to work** — first article in ~10 minutes. Cancel anytime if it's not for you.

### Implementation note
Drop technical terms: `Stripe billing context`, `Host wrapper`, `LLM keys configured inside AdClaw`. Move those to FAQ.

---

## Section 7 — FAQ (REWRITE)

Replace current FAQ with marketer-focused FAQ. Order matters — most-asked first.

### Q: How fast can I have my first SEO article?
A: ~10 minutes from signup. Click Launch (90 seconds). Open Web UI. Tell the SEO Writer your topic. Article writes itself, you review, click publish.

### Q: Do I need my own OpenAI / Claude API key?
A: Yes. Bring your OpenAI, Anthropic, Gemini, or DeepSeek key — we'll guide you on which is cheapest for your use case. We never store or see your keys; they live inside your AdClaw workspace.

### Q: What if I run out of credits?
A: You can top up at any time, or use AdClaw with your own LLM key for chat-only tasks (those don't burn credits — only Citedy marketing tools do).

### Q: Can my whole team use it via Telegram?
A: Yes. Drop the bot into your team's Telegram group. Anyone can @mention any persona. Starter: 3 members. Pro: 10. Business: unlimited.

### Q: What happens if I cancel?
A: Workspace pauses. You can export everything (memory, configs, generated content). Reactivate within 90 days to restore. After 90 days, deleted per retention policy.

### Q: I'm technical. Can I self-host instead?
A: Yes. AdClaw is Apache 2.0. `pip install adclaw` or `docker run`. See [/dev](https://adclaw.app/dev) for full guide.

### Q: Why does my workspace sleep?
A: To keep your monthly price at $10–79. Idle workspaces cost us compute. After 10 idle minutes, we sleep yours. Wake = 90 seconds when you come back. Active work doesn't pause.

### Q: Is my data private?
A: Yes. Your workspace is isolated. Your LLM keys never leave the workspace. Backups are encrypted. You can delete everything via the dashboard.

### Q: Do I own the content the AI generates?
A: 100%. Apache 2.0 framework, you own all outputs.

### Q: What's the difference between this and ChatGPT / Jasper?
A: ChatGPT is one model, one chat. Jasper writes one piece at a time. AdClaw is 5 specialists working together with memory of your brand, your competitors, your past content — auto-publishing to your blog and socials, monitoring competitors daily, answering your team in Telegram. Different category.

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

- "Autonomous office roles" / "Core roles" row (vague, replaced with concrete outcomes)
- "Fair-use workspace budget: 200/1000/5000 active min/mo" (moves to small print or removed)
- "Keep Warm: Eligible add-on path" (moves to power-user docs)
- "Self-host alternative" inline (moves to dedicated section + `/pricing/self-host` page)
- Generic "Cloud workspaces cost money while running" callout (replaced with outcome-focused note)
