# Layout Lock

This file is the canonical layout contract for the strict Product Grid system.
It exists to prevent "nice-looking but structurally random" slides.

## Required Contract

Every slide in a Product Grid deck must:

- Use `assets/template-product-grid.html`.
- Include `data-system="product-grid"`.
- Include one registered `data-layout="PGxx"` value.
- Use only classes defined in the copied template CSS.
- Put local images in a registered slot with `data-image-slot`.
- Keep text outside SVG. SVG is allowed only for geometry.
- Keep product screenshots legible; do not crop required UI labels.

Before writing HTML, create this planning table:

| Slide | Message | Layout | Density | Image slot | Risk |
|---|---|---|---|---|---|
| 01 | Launch thesis | PG01 | low | pg01-hero-16x9 | none |

If a slide cannot fit one registered layout, split it into two slides. Do not
invent a new structure inside the deck.

## Registered Product Grid Layouts

| ID | Name | Use | Required skeleton | Image slots |
|---|---|---|---|---|
| PG01 | Cover System | Opening title with strong accent scene | `.stage`, `.grid-12`, large title, optional metric block | `pg01-hero-16x9` optional |
| PG02 | Statement | One large claim or transition | `.statement` plus `.lead` | none |
| PG03 | Metric Wall | Three or four major numbers | `.grid-12` with `.panel` metric cards | none |
| PG04 | Screenshot Proof | Product screenshot plus analysis | `.span-7` frame + `.span-5` panel | `pg04-main-16x10` required |
| PG05 | Three Cards | Three equal product pillars | three `.span-4` panels | none |
| PG06 | Process Timeline | Four-step sequence | `.timeline` with four nodes | none |
| PG07 | Before After | Two-column comparison | `.compare` with `.divider` | none |
| PG08 | System Diagram | Three-layer architecture or workflow | `.diagram` with three HTML columns | none |
| PG09 | Evidence Grid | Mixed proof points with optional visuals | `.grid-12` with 2-4 panels | `pg09-evidence-16x9` optional |
| PG10 | Quote | Customer/founder quote or takeaway | `.quote` plus source `.meta` | none |
| PG11 | Ledger | Three-phase launch, rollout, or ordered proof | `.ledger` with `.ledger-row` | none |
| PG12 | Closing | Final decision and CTA | `.statement` plus one supporting panel | none |
| PG13 | Bar Evidence | Quantified comparison or ranked proof | `.bar-chart` with `.bar-row` | none |
| PG14 | Matrix Brief | Eight short evidence cells with one emphasis | `.matrix` with `.matrix-cell` | none |

## Layout Selection Rules

- Decks under 8 slides must use at least 5 distinct layouts.
- Decks with 8-14 slides must use at least 7 distinct layouts.
- Do not use the same layout more than twice in a row.
- Use PG02 or PG10 after two dense slides.
- Use PG04 only when screenshot details are large enough to read.
- Use PG08 only for real system structure; do not use it as decoration.
- Use PG03 only for real metrics, counts, durations, or named states.
- Use PG13 only with real or explicitly labeled illustrative values.
- Use PG14 for compact short evidence, not paragraphs.

## Typography Rules

- Do not add negative letter spacing.
- Do not scale text with viewport width. Use template classes and media queries.
- Keep one headline per slide.
- Rewrite or split any title that needs more than three lines.
- Do not reduce body text below the template body sizes to make content fit.
- Small labels use `.meta`, `.kicker`, `.label`, or `.tag`; do not create new mini text classes.
- Use `.stage`, not legacy `.canvas`.

## Image Slot Rules

- `pg01-hero-16x9`: 16:9 product, market, or campaign visual. Use `.frame.r-16x9`.
- `pg04-main-16x10`: 16:10 screenshot proof. Use `.frame.r-16x10.fit-contain` for raw screenshots.
- `pg09-evidence-16x9`: 16:9 evidence image. Use `.frame.r-16x9`.

For generated images, generate to the final slot ratio before inserting. For raw
screenshots, preserve visible details and use `fit-contain` when text matters.

## Banned Patterns

- Custom one-off classes in deck HTML.
- `text-align:center` on normal product-grid body slides.
- Inline `font-size` overrides.
- `height: Nvh` image boxes.
- Rounded nested card stacks.
- Decorative gradient blobs, bokeh, or purely atmospheric images.
- Multiple accent colors competing on one slide.
- SVG `<text>` labels.
- Images without `alt`.
- Blue text on yellow theme slides; yellow theme uses black text accents.
