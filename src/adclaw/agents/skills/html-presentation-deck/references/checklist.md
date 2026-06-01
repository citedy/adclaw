# Quality Checklist

Run this before handing off an HTML presentation deck.

## Product Grid v2 Gate

- Every slide has `data-system="product-grid"` and registered `data-layout="PGxx"`.
- The slide map exists before HTML: slide, message, layout, density, image slot, risk.
- No custom one-off classes appear in deck HTML.
- No inline `font-size` overrides appear in slides.
- No negative letter spacing, gradients, shadows, decorative blobs, or nested cards appear.
- Every local image has `alt` and `data-image-slot`.
- Required image slots are present for screenshot layouts.
- Dense slides are followed by PG02 Statement or PG10 Quote.
- `python3 <skill-dir>/scripts/validate_deck_quality.py deck/index.html` passes.

## Content

- One idea per slide.
- Title and metadata placeholders are replaced.
- Every image has useful `alt` text.
- Data claims include source context in speaker notes or nearby captions.
- No visible draft notes, private instructions, or placeholder copy.

## Legacy Typography (Editorial / Clean Grid)

- Typography tokens follow `references/typography.md`.
- Contrast-safe `--accent-text` is used for small labels on light panels.
- `validate_html_deck.py` passes contrast checks for theme tokens.

## Design

- One visual system is used throughout.
- One theme is used throughout.
- Dense slides are separated by simple statement or image slides.
- Screenshots are framed consistently.
- Mobile layout remains readable.

## Technical

- From the project root, `python3 <skill-dir>/scripts/validate_html_deck.py deck/index.html` passes.
- Browser opens the file with no console-breaking script error.
- Arrow keys, touch swipe, and Escape index work.
- Local images load from `images/`.
- No external network dependency is required for the presentation to render.

## Language and Provenance

- The deck is English-only unless the user explicitly requests another language.
- When the deck is English-only, no non-English text, non-English comments, non-English font names, or non-English placeholders appear.
- No upstream project name, author name, or repository name appears in generated output.
