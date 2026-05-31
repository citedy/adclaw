---
name: html-presentation-deck
description: "Use this skill when the user wants a browser-native HTML presentation, web deck, single-file slides, horizontal swipe deck, keynote-style web page, investor/demo-day HTML deck, or a shareable presentation that opens in a browser. Also use when the user asks for an editorial deck, clean grid deck, presentation microsite, slide landing page, or HTML slides. Do not use this for .pptx files; use the pptx skill for PowerPoint input or output."
---

# HTML Presentation Deck

Create polished, browser-native presentation decks as standalone HTML files. The output is a web presentation, not a PowerPoint file.

## When To Use

Use this skill for:

- Single-file HTML slide decks that open locally or can be hosted.
- Horizontal swipe or keyboard-driven presentations.
- Product launches, demo days, internal talks, sales narratives, research summaries, and strategy presentations.
- Screenshot-heavy decks where product UI needs to be framed cleanly.

Use the `pptx` skill instead when the user needs a `.pptx` file, PowerPoint template editing, or slide XML manipulation.

## Visual Systems

Choose one system per deck. Do not mix systems in the same presentation.

### Editorial

Use for narrative talks, opinionated strategy decks, customer stories, founder updates, and presentations that need a magazine-like rhythm.

Design traits:

- Warm paper backgrounds, serif display titles, restrained ink-like accents.
- Large opening and closing statements.
- Alternating hero slides, image pages, quote pages, and structured evidence pages.
- Best when the deck needs a memorable point of view.

Template: `assets/template-editorial.html`
References: `references/themes.md`, `references/layouts-editorial.md`, `references/screenshot-framing.md`

### Clean Grid

Use for data, product, engineering, roadmap, comparison, operating model, and board-style decks.

Design traits:

- Strict grid, left-aligned typography, high contrast, sharp rectangular modules.
- One accent color only.
- Strong hierarchy for numbers, timelines, tables, diagrams, and product screenshots.
- Best when the deck needs clarity, precision, and executive readability.

Template: `assets/template-clean-grid.html`
References: `references/themes.md`, `references/layouts-clean-grid.md`, `references/screenshot-framing.md`

## Workflow

1. Clarify the brief.
   - Audience and setting.
   - Target duration or slide count.
   - Required message, data, screenshots, and constraints.
   - Preferred visual system: Editorial or Clean Grid.

2. Create the project folder.
   - Put the deck at `deck/index.html`.
   - Put images at `deck/images/`.
   - Use short English filenames such as `01-cover.jpg` or `06-dashboard.png`.

3. Copy one template.
   - Editorial: copy `assets/template-editorial.html`.
   - Clean Grid: copy `assets/template-clean-grid.html`.
   - Replace the title placeholder immediately.
   - Replace the `<!-- SLIDES_HERE -->` marker with slide sections.

4. Build the outline before writing slides.
   - One idea per slide.
   - Use 8-12 slides for short product or strategy decks.
   - Use 15-25 slides for talks longer than 25 minutes.
   - Alternate dense slides with breathing-room slides.

5. Choose layouts from the matching reference file.
   - Editorial layouts are not interchangeable with Clean Grid layouts.
   - Do not invent many new classes; use the template classes first.
   - If a custom adjustment is unavoidable, prefer a small inline style on the slide section.

6. Handle screenshots deliberately.
   - Read `references/screenshot-framing.md` before placing product screenshots.
   - Preserve screenshot content when details matter.
   - Use generated background assets only as neutral framing surfaces.
   - Do not crop away important UI text, numbers, or controls.

7. Validate before presenting.
   - Run `python scripts/validate_html_deck.py deck/index.html`.
   - Open the deck in a browser.
   - Check keyboard navigation, slide index, mobile scaling, broken images, and text overflow.

## Output Requirements

- The deck must be English-only unless the user explicitly asks for another language.
- Never include Chinese text, Chinese comments, Chinese font names, or Chinese placeholders.
- Never mention the upstream inspiration, repository names, or author names in generated decks.
- Keep all visible deck text user-facing and presentation-ready.
- Keep source comments in English.
- Avoid external runtime dependencies when possible; templates must work offline.

## Related Skills

- **pptx**: PowerPoint input/output, template editing, and `.pptx` manipulation.
- **marketing-sales-enablement**: Pitch deck strategy, slide narrative, sales collateral.
- **marketing-image**: Image generation and visual asset planning.
- **marketing-video**: Video or animated presentation assets.
