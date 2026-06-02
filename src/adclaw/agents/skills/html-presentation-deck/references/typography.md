# Typography

Typography is selected through semantic tokens, not ad hoc class edits. Keep one typography preset per deck.

## Default Rule

Use the template defaults unless the brief explicitly needs a stronger typographic voice.

- Editorial defaults to a system-safe serif display stack with system sans body text.
- Clean Grid defaults to a system-safe sans stack with system mono labels.
- Generated decks must render offline unless the user explicitly approves external fonts.

## Font Tokens

Set these tokens in `:root` when changing typography:

```css
:root {
  --display-font: var(--serif);
  --text-font: var(--sans);
  --label-font: var(--mono);
  --hero-tracking: -.06em;
  --headline-tracking: -.045em;
  --statement-tracking: -.05em;
  --display-tracking: -.075em;
  --title-tracking: -.065em;
  --metric-tracking: -.07em;
  --label-tracking: .14em;
}
```

Do not edit every heading class to change fonts. Update tokens once.

## Presets

### System Safe

Best for offline decks, private handoffs, and unknown environments.

```css
:root {
  --serif: Georgia, "Times New Roman", serif;
  --sans: "Aptos", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}
```

### Modern Product

Best for SaaS, product launches, UI-heavy demos, and clean executive decks.

Use when external or self-hosted fonts are approved:

```css
:root {
  --sans: "Inter", "Aptos", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
  --display-font: var(--sans);
  --text-font: var(--sans);
  --label-font: var(--mono);
}
```

### Executive Grid

Best for board updates, technical operating reviews, data rooms, and information-heavy decks.

Use when external or self-hosted fonts are approved:

```css
:root {
  --sans: "IBM Plex Sans", "Aptos", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  --display-font: var(--sans);
  --text-font: var(--sans);
  --label-font: var(--mono);
}
```

### Editorial Serif

Best for research, founder updates, customer stories, and narrative strategy.

Use when external or self-hosted fonts are approved:

```css
:root {
  --serif: "Source Serif 4", Georgia, "Times New Roman", serif;
  --sans: "Inter", "Aptos", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
  --display-font: var(--serif);
  --text-font: var(--sans);
  --label-font: var(--mono);
}
```

### Editorial Display

Best for high-impact title slides, conference talks, and brand-led storytelling. Use sparingly: long body text should still use a readable sans or text serif.

Use when external or self-hosted fonts are approved:

```css
:root {
  --serif: "Fraunces", Georgia, "Times New Roman", serif;
  --sans: "Source Sans 3", "Aptos", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "Roboto Mono", "SFMono-Regular", Consolas, monospace;
  --display-font: var(--serif);
  --text-font: var(--sans);
  --label-font: var(--mono);
}
```

### Coverage First

Best for non-English decks, mixed scripts, international teams, and localization work.

Use when external or self-hosted fonts are approved:

```css
:root {
  --serif: "Noto Serif", Georgia, "Times New Roman", serif;
  --sans: "Noto Sans", "Aptos", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "Noto Sans Mono", "SFMono-Regular", Consolas, monospace;
  --display-font: var(--serif);
  --text-font: var(--sans);
  --label-font: var(--mono);
}
```

## External Font Policy

The default deck must not depend on a network request. If the user approves non-offline fonts, choose one of these delivery modes:

- Self-hosted: put font files in `deck/fonts/` and define `@font-face`.
- Google Fonts: use only when a hosted dependency is acceptable for the use case.

When adding `@font-face`, use `font-display: swap` and keep weights narrow. Do not load a full family when the deck only needs regular, semibold, and bold.

## Readability Rules

- Body text should use `--text-font`, not the display font.
- Labels and navigation should use `--label-font`.
- Display tracking may be tight; label tracking may be wide; body copy should keep normal letter spacing.
- Avoid ultra-thin weights on dark or image-backed slides.
- Do not use bright accent fills as text on light panels. Use `--accent-text` for small labels, metrics, and annotations.
- Validate contrast after changing any theme or typography token.
