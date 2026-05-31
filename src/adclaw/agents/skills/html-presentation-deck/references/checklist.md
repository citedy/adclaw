# Quality Checklist

Run this before handing off an HTML presentation deck.

## Content

- One idea per slide.
- Title and metadata placeholders are replaced.
- Every image has useful `alt` text.
- Data claims include source context in speaker notes or nearby captions.
- No visible draft notes, private instructions, or placeholder copy.

## Design

- One visual system is used throughout.
- One theme is used throughout.
- Dense slides are separated by simple statement or image slides.
- Screenshots are framed consistently.
- Mobile layout remains readable.

## Technical

- `python scripts/validate_html_deck.py deck/index.html` passes.
- Browser opens the file with no console-breaking script error.
- Arrow keys, touch swipe, and Escape index work.
- Local images load from `images/`.
- No external network dependency is required for the presentation to render.

## Language and Provenance

- The deck is English-only unless the user explicitly requests another language.
- No Chinese text, Chinese comments, Chinese font names, or Chinese placeholders appear.
- No upstream project name, author name, or repository name appears in generated output.
