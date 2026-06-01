# HTML Presentation Deck

Create polished, browser-native presentation decks as standalone HTML files. Use it when a deck should open locally, be hosted as a web page, or present product screenshots with clean keyboard and swipe navigation.

## Two installs, two locations

This skill ships in **AdClaw** (built-in) and **`@citedy/skills`** (npm). They are separate copies with different on-disk paths.

| Install | Where the skill lives |
|---------|------------------------|
| **AdClaw runtime** | `~/.adclaw/active_skills/html-presentation-deck` (or `$ADCLAW_WORKING_DIR/active_skills/...`) |
| **AdClaw repo dev** | `src/adclaw/agents/skills/html-presentation-deck/` (source; synced to `active_skills`) |
| **`npx @citedy/skills`** | `<your-project>/.codex/skills/html-presentation-deck` and/or `.claude/skills/html-presentation-deck` |

Default mode is **Product Grid v2** in both packages. Legacy **Editorial** and **Clean Grid** remain available.

## AdClaw

Built into the agent; no npm step. Custom edits can go in `~/.adclaw/customized_skills/html-presentation-deck/`.

## Claude / Codex (`@citedy/skills`)

```bash
npx @citedy/skills install html-deck
npx @citedy/skills install --target claude html-deck
npx @citedy/skills install --target codex html-deck
```

```text
/html-deck Build a 10-slide investor update for a B2B SaaS launch.
```

Creates `deck/index.html` under the **project where you ran install**, then validate from that project root:

```bash
python3 .codex/skills/html-presentation-deck/scripts/validate_html_deck.py deck/index.html
python3 .codex/skills/html-presentation-deck/scripts/validate_deck_quality.py deck/index.html
```

Use `.claude/skills/...` instead when you installed with `--target claude`.

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
