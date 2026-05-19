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
A private office with 5 specialists — Strategist, Researcher, SEO Writer, Ads Manager, Analyst. They publish articles, monitor competitors, write ads, and answer your team in Telegram. From $10/month.

### Primary CTA
`Launch your office — $10/month →` (links to `/pricing`)

### Secondary CTA
`See how it looks →` (anchor link to "What it looks like" section)

### Trust strip (below CTAs, small text)
`90-second launch  ·  Cancel anytime  ·  Apache 2.0 — you can self-host`

### Implementation note
Remove the current "cloud-card" structure with $10/month inside a card. The price moves to the headline area, the card disappears. Remove DigitalOcean/Railway buttons from hero — they move to `/dev`.

---

## Section 3 — Pain points (NEW BLOCK)

### Title
**Marketing today is broken.**

### Subtitle
You're paying $4,000/month for tools that don't talk to each other and a team that can't keep up.

### 4 pain cards (2x2 grid on desktop, stacked on mobile)

**Card 1 — Tool sprawl**
> "I have 8 tools, 4 dashboards, and still no time."
>
> SEO in one tab, content in another, analytics somewhere else. Context lost on every handoff.

**Card 2 — Hiring cost**
> "A content writer costs $4,000/month. An SEO specialist another $5,000."
>
> And neither knows your competitors or your brand voice on day one.

**Card 3 — AI tools are scattered**
> "ChatGPT for ideas. Jasper for copy. Surfer for SEO. None of them know each other."
>
> Five subscriptions, five logins, zero integration.

**Card 4 — Team can't use AI**
> "Half my team doesn't know how to prompt. The other half drowns in tabs."
>
> AI is supposed to save time, not create a second job.

### Implementation note
New section. Place between Hero and "How it works". Use the existing `.features-grid` CSS but 2x2 layout.

---

## Section 4 — How it works (NEW BLOCK, 3 steps)

### Title
**One office. Five specialists. Always working.**

### Step 1 — Subscribe
**$10. 90 seconds.** Your private workspace launches in the cloud. Backups, auto-sleep, security — handled.

### Step 2 — Meet your team
Open your office in the browser. Five specialists are already there: Strategist, Researcher, SEO Writer, Ads Manager, Analyst. Talk to them like real employees.

### Step 3 — Or invite them to Telegram
Connect your bot, drop it into your team's Telegram group. Anyone on your team can ask `@researcher`, `@writer`, `@analyst` — they answer in the chat. Everyone sees the work.

### Implementation note
3-column horizontal flow. Similar to current "After checkout" flow on `/pricing` but on home page. Each step gets a simple icon + 2-line description.

---

## Section 5 — Telegram team block (NEW BLOCK — explicit user request)

### Title
**Your AI team. In the chat your team already uses.**

### Sub
Add the AdClaw bot to your company Telegram group. Five specialists. One shared context. Real work in messages your whole team can see.

### Example conversation (visual mockup — IMPORTANT TO IMPLEMENT AS CHAT BUBBLE UI)

Show a Telegram-style conversation:

```
[Alex, Marketing Lead, 10:42]
@researcher what's new with competitor SuperSaaS this week?

[@researcher, 10:42]
SuperSaaS launched a new pricing page Tuesday. 3 changes:
1. Removed free tier (now $19 min)
2. Added "Teams" plan at $99/mo
3. New testimonial section with 4 enterprise logos
Full report: [link]

[Maria, Content, 10:45]
@writer write 3 LinkedIn posts about our team plan being still free for 5 users

[@writer, 10:45]
Drafted 3 posts focused on "value for growing teams":
Post 1 (problem-first): ...
Post 2 (number-driven): ...
Post 3 (testimonial-style): ...
Want me to publish or edit?

[Sergey, Founder, 11:02]
@analyst what was traffic yesterday?

[@analyst, 11:02]
Yesterday: 4,231 visitors (+18% vs avg). Top page: /pricing (1,890 views).
Conversion to trial: 2.3% (above 1.7% baseline).
```

### Caption below mockup
**One bot. Whole team. Real data.** No external tools. No context switching. No more "wait, where's that report?"

### CTA
`Try the demo bot →` (link to `@adclaw_demo_bot` on Telegram if available, otherwise to pricing)

### Implementation note
This is the most important new block. Make it visually distinct — Telegram-style chat bubbles with avatars. This is the killer differentiator. Mobile: full-width chat. Desktop: chat on left, copy on right OR centered chat with caption below.

---

## Section 6 — What it looks like (NEW BLOCK — explicit user request)

### Title
**See the office.**

### Two-tab toggle
- **Tab 1: Web dashboard** — screenshot of AdClaw web UI showing 5 persona cards with status, model, last activity
- **Tab 2: Telegram** — screenshot of bot in group chat

### Captions for each
**Web:** "Your dashboard. Each persona has its own chat tab, can be paused, configured, scheduled."

**Telegram:** "Same agents, in your team chat. @-mention to route. Group-wide visibility."

### Implementation note
Need actual screenshots. Placeholder needed. Tab switcher should be CSS-only (radio buttons) or simple JS toggle.

### TODO
- Take screenshot: AdClaw web UI with 5 personas, English UI only
- Take screenshot: real Telegram group chat with bot doing @-routing (could be staged)

---

## Section 7 — What's included (REPLACES current "What you get" feature grid)

### Title
**What your team can do.**

### Outcome-focused grid (2x3 on desktop)

**1. Publish SEO articles**
500–8,000 words in 55 languages. Auto-publishes to your blog. Includes citations, images, internal links.

**2. Track competitors daily**
Tell us 3 competitors. Get a daily report: new pages, new pricing, new features, new content.

**3. AI video shorts for socials**
30-second UGC-style videos for Instagram Reels, TikTok, YouTube Shorts. Auto-captions, voiceover, music.

**4. Lead magnets on demand**
Checklists, frameworks, swipe files. Branded, formatted, ready to download.

**5. Adapt one post for 5 platforms**
Write once. Get LinkedIn, X, Facebook, Reddit, Instagram versions — each tuned to the platform.

**6. Trend scouting**
Daily report from X/Twitter and Reddit. Trending topics in your niche, ready-to-write angles.

### Implementation note
Replace the current 12-card feature grid (Multi-agent personas, 23 LLM providers, etc.) with this 6-card outcome grid. Keep the same `.features-grid` CSS.

---

## Section 8 — Plans teaser (NEW BLOCK)

### Title
**Three plans. No hidden cost.**

### Mini-plans (compact 3-column)

| | **Starter $10** | **Pro $29** (Recommended) | **Business $79** |
|-|-|-|-|
| Best for | Solo / side project | Active solopreneur | Agency / team |
| Output / month | ~10 articles | ~30 articles + videos | ~100 articles + multi-client |
| Specialists | 5 personas | 5 personas + custom | 5 + unlimited custom |
| Telegram team | ✓ | ✓ | ✓ |

### CTA
`See full pricing →` → `/pricing`

### Implementation note
Mini-pricing on home page is a conversion booster — visitor doesn't need to navigate to see if they can afford it. Keep simple.

---

## Section 9 — Trust / FAQ teaser (small)

### Title
**No lock-in. Open source. You own your data.**

### 3 trust points (inline)

- **Apache 2.0** — fork it, run it on your laptop, never pay us. Same software.
- **Your LLM keys** — bring your own OpenAI/Anthropic/Gemini key. We don't store them.
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

Product:   Pricing  ·  Telegram bot  ·  Demo
For devs:  Self-host  ·  GitHub  ·  Docker Hub  ·  Docs
Company:   Citedy  ·  Blog  ·  Contact

© 2026 Citedy  ·  Apache 2.0  ·  Built by a solo founder
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
- "Security built-in 208-pattern scanner" card (replaced with "No lock-in" trust block)
- "Self-healing skills" card (gone)
- "7 chat channels" card (replaced with "Telegram team" block)
- Clawsy AgentHub section (moves to `/dev`)
- Full comparison table (CoPaw, CrewAI, Dify, OpenClaw MC) (moves to `/dev`)
- "Open source. Apache 2.0." final section with `View on GitHub` (replaced with marketing CTA)

---

## Implementation order

1. Write copy as above
2. Build pain-points block (new component)
3. Build "How it works" 3-step (new component)
4. **Build Telegram chat mockup block** (critical, custom CSS)
5. Build "What it looks like" tabs (needs screenshots)
6. Replace feature grid with outcome grid
7. Add mini-plans block
8. Add trust block
9. Final CTA
10. Footer update
11. Add `/dev` route serving `home-hardcore.md` content
