# HTML Presentation Deck

Create polished, browser-native presentation decks as standalone HTML files. Use it when a deck should open locally, be hosted as a web page, or present product screenshots with clean keyboard and swipe navigation.

## In AdClaw

Skill path: `src/adclaw/agents/skills/html-presentation-deck/`

Default mode is **Product Grid v2** (strict layout registry + quality validator). Legacy **Editorial** and **Clean Grid** systems remain available.

## Install via npm (other agents)

```bash
npx @citedy/skills install html-deck
```

```bash
npx @citedy/skills install --target claude html-deck
npx @citedy/skills install --target codex html-deck
```

## Use

```text
/html-deck Build a 10-slide investor update for a B2B SaaS launch.
```

Creates `deck/index.html`, keeps images in `deck/images/`, then validates from the project root:

```bash
python3 <installed-skill-dir>/scripts/validate_html_deck.py deck/index.html
python3 <installed-skill-dir>/scripts/validate_deck_quality.py deck/index.html
```

After `npx @citedy/skills install`, `<installed-skill-dir>` is usually `.codex/skills/html-presentation-deck` or `.claude/skills/html-presentation-deck`.

## Visual Systems

- **Product Grid v2** (default) — product, launch, investor, and strategy decks.
- **Editorial** — founder updates, research stories, narrative strategy.
- **Clean Grid** — board updates, roadmaps, metrics, operating reviews.

## What You Get

- Offline-friendly HTML with keyboard and swipe navigation.
- Product Grid v2 with registered layouts `PG01`–`PG14`.
- Legacy Editorial and Clean Grid templates with typography presets.
- Contrast and placeholder validation before handoff.

## Files

- `SKILL.md` — agent workflow.
- `assets/template-product-grid.html` — default template.
- `assets/template-editorial.html`, `assets/template-clean-grid.html` — legacy.
- `references/` — layouts, themes, typography, screenshot framing.
- `scripts/validate_html_deck.py`, `scripts/validate_deck_quality.py` — validators.
