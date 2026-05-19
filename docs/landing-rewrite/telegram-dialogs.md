# Telegram Dialog Scenarios — for fake screenshot capture

**Purpose:** the home page Telegram block uses real screenshots, not synthesized chat UI. Founder runs the prompts below in a staged Telegram group with the live AdClaw bot, screenshots the result, and we embed those screenshots on `adclaw.app`.

**How to use:**
1. Create a private Telegram group ("AdClaw Demo Team" or similar) with 2–3 personal accounts + the AdClaw bot.
2. From each personal account, send the prompt as written (you can vary names — see the "people" key at the top of each scenario).
3. Screenshot the resulting thread (full screen on phone, or scrolled view on desktop Telegram).
4. Drop the screenshot into `home-casual.md` Section 5 placeholder.

**Personas used in scenarios** — all are defaults in a fresh AdClaw workspace, no setup needed:
- `@strategist` — Strategist
- `@researcher` — Researcher
- `@writer` — SEO Writer
- `@ads` — Ads Manager
- `@analyst` — Analyst

If you've added custom personas (e.g. `@brand`, `@cro`, `@outreach`), feel free to swap one scenario to feature them — that reinforces the "unlimited specialists" message.

---

## Scenario A — Competitor + Content + Analytics in one thread (PRIMARY)

**Goal:** show three different specialists answering three different people in one group, in under 2 minutes of real time. This is the killer screenshot.

**People (3):** Alex (Marketing Lead), Maria (Content), Sergey (Founder)

**Pre-condition:** the bot has been told "our main competitor is SuperSaaS" and is connected to Google Analytics. If not, the analytics reply will say "GA not connected — connect via dashboard" — equally believable. Either is fine for the screenshot.

```
[Alex, Marketing Lead, 10:42]
@researcher what's new with competitor SuperSaaS this week?

[@researcher → Alex, 10:42]
SuperSaaS shipped 3 changes since Monday:
1. Pricing page — removed free tier, new floor at $19/mo
2. New "Teams" plan at $99/mo with 5 seats included
3. Testimonial section added with 4 enterprise logos (Stripe, Notion, Linear, Vercel)
Source pages diffed: /pricing, /teams, /customers
Full report → [link]

[Maria, Content, 10:45]
@writer write 3 LinkedIn posts about our team plan still being free for 5 users

[@writer → Maria, 10:45]
Drafted 3 angles:
1. Problem-first — "Your team is 5 people. Your competitor wants $99/mo. We're $0."
2. Number-driven — "5 seats. $0. Forever." (with screenshot of pricing page)
3. Testimonial-style — quote from existing customer about why $0 mattered when they started
Want me to publish, schedule, or send drafts for review?

[Sergey, Founder, 11:02]
@analyst what was traffic yesterday?

[@analyst → Sergey, 11:02]
Yesterday (May 18): 4,231 visitors, +18% vs 30-day avg.
Top page: /pricing — 1,890 views (45%)
Conversion to trial signup: 2.3% (above 1.7% baseline)
Trigger: LinkedIn post from Tuesday is still driving 60% of /pricing traffic.
```

**Founder notes for the staging:**
- Have one person send each message sequentially, ~2 minutes apart so timestamps are believable
- Don't edit the bot's replies after the fact — if a reply is too long, screenshot the relevant top portion
- Phone screenshot preferred for the marketing block (mobile-feel is the point)

---

## Scenario B — Trend scout into draft (single-person, shows speed)

**Goal:** show one founder running the whole "spot a trend, write a post about it" loop in one chat.

**People (1):** Founder

```
[Founder, 09:14]
@researcher what's trending on X about AI marketing today?

[@researcher, 09:14]
Top 5 trends in your niche (last 24h, ranked by engagement × intent):
1. "Jasper alternatives" — 12 posts, 2.4K engagement, 3 frustrated power users
2. AI video shorts replacing reels writers
3. Cold email + AI — Gmail flagging issues
4. Multi-agent vs single-LLM workflows
5. SEO + LLM visibility (GEO) — Google AI Overview ranking drops

[Founder, 09:15]
@writer take #1 — write a standard SEO article positioning us as the alternative

[@writer, 09:17]
Article ready: "Jasper Alternatives in 2026: 7 Tools That Don't Lock MCP Behind a $59 Paywall"
1,047 words · 4 outbound citations · 6 internal links · OG image generated
Status: draft, on your blog at /blog/jasper-alternatives-2026
Auto-adapted to LinkedIn, X (thread), Reddit — ready to publish.
Click publish? [Yes] [Review first]
```

**Founder notes:**
- This one's a clean "speed" demo — works as a side-by-side with Scenario A
- If actual draft has a different title, that's fine — show what the bot actually produces

---

## Scenario C — Lead magnet on demand (shows lead-gen path)

**Goal:** show that lead magnets aren't a separate tool — same chat, same team.

**People (1):** Founder

```
[Founder, 14:08]
@strategist we need a lead magnet for the "AI marketing for solo founders" landing. 30-min framework.

[@strategist, 14:08]
Recommend: "The 7-Day AI Marketing Sprint" — checklist + 30-min daily template
Format: branded PDF, ~10 pages, includes weekly review questions
Audience match: solo founders building in public
Should I have @writer build it?

[Founder, 14:09]
Yes, with illustrations

[@writer, 14:13]
Lead magnet ready: "The 7-Day AI Marketing Sprint"
PDF: 11 pages, 8 AI illustrations, your brand colors
Hosted at: yourdomain.com/lead/7-day-ai-marketing-sprint
Email-gated download form is live.
Want a LinkedIn promo post + X thread? (~5 credits each)
```

**Founder notes:**
- Showcases the "leads come back to you, not to us" angle
- If you don't want to spend the credits to actually generate, screenshot the bot just up to the "Want a LinkedIn promo post..." question

---

## Scenario D — Ads quick-fire (shows breadth beyond content)

**Goal:** reinforce that AdClaw isn't only an SEO bot — ads, analytics, customer success angles all live in the same team.

**People (2):** Marketing Lead, Founder

```
[Marketing Lead, 11:30]
@ads we're spending $400/day on Meta. CPA crept from $14 to $22 this week. What's off?

[@ads, 11:31]
Pulled last 7 days from your ad account:
- Spend: $2,800 (steady)
- Conversions: 127 → 89 (-30%)
- CTR: dropped from 2.1% to 1.4% on the "founder testimonial" set
- Best performer: "before/after" carousel — CPA $11
Recommend: pause 2 creatives in "founder testimonial" set, scale "before/after" budget +50%. Draft fresh creative for the paused angle?

[Founder, 11:33]
Yes, 5 variants. Same angle, new hooks.

[@ads, 11:36]
5 ad copy variants drafted, each with 3 hooks:
1. Pain-first ("Your competitor just doubled their content output...")
2. Number-first ("$10/mo. 5 specialists. Zero context switching.")
3. Social proof (uses Maria's LinkedIn quote from Tuesday)
4. Question-first ("Why is your marketer copy-pasting between 8 tools?")
5. Contrarian ("Stop hiring more humans for AI work.")
Ready for review or I can push 2 directly to A/B?
```

**Founder notes:**
- Best scenario to feature on the "/pricing" page lower down, not the home page hero
- Replace "Meta" with "Google" or "TikTok Ads" if you don't have Meta integrated yet

---

## Scenario E — Memory + context (shows the moat)

**Goal:** illustrate that the bot remembers what the team agreed on yesterday. This is what makes it different from ChatGPT.

**People (2):** Founder, Marketing Lead

**Pre-condition:** the team had a discussion the day before about brand voice ("we're casual, anti-corporate, no buzzwords"). The bot remembered it via AOM.

```
[Founder, 09:00 — next morning]
@writer draft our weekly newsletter intro. 4 sentences.

[@writer, 09:00]
Drafted with your "casual, anti-corporate, no buzzwords" voice (per yesterday's call with Maria):
"Hey — quick week. We shipped the unlimited-specialists thing nobody else does. Three people on the team said it sounds too good to be true. Then they tried it. Here's what they built."
Word count: 38. Want me to adapt for LinkedIn (~5 credits)?

[Marketing Lead, 09:02]
Wait, you actually remembered the voice rules from yesterday's call?

[@writer, 09:02]
Yes — saved to brand memory after the discussion ended yesterday at 16:47. Tagged: brand-voice, anti-corporate, no-buzzwords. Override any time by saying "forget brand voice" or "update brand voice".
```

**Founder notes:**
- Strongest screenshot for the "this is not ChatGPT" message
- Use it in Section 7 (What's included) or as a secondary screenshot in Section 5

---

## Choosing which scenarios go where

| Scenario | Where it should appear | Why |
|----------|------------------------|-----|
| A | Home Section 5 (Telegram block) — primary screenshot | Multiple people, multiple specialists, mobile-friendly |
| B | Home Section 7 (What's included) inline near "Trend scouting" card | Shows the full loop in one chat |
| C | `/pricing` page near "Lead magnets" mention | Connects lead magnets to the team workflow |
| D | `/pricing` Section 4 (What credits buy) | Reinforces breadth beyond SEO |
| E | Home Section 7 or Section 9 (Trust) | Memory/context = the moat |

---

## Capture checklist

- [ ] Telegram group created with realistic name
- [ ] Bot is in the group with the 5 default personas active
- [ ] At least 2 personal accounts logged in for multi-person scenarios (A, D)
- [ ] Avatars set on each personal account (no default-generated names like "User12345")
- [ ] AdClaw bot avatar set (use the AdClaw logo)
- [ ] Each scenario captured at least once, full thread visible
- [ ] No real customer data, no real competitor data that isn't already public — use SuperSaaS / Notion / Linear as harmless examples
- [ ] PNG export, mobile width preferred (393px or 414px wide) for home-page block
