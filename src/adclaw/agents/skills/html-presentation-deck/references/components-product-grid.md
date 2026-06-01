# Product Grid Components

Use these components only with `assets/template-product-grid.html`.

## Slide Shell

```html
<section class="slide" data-system="product-grid" data-layout="PG04">
  <div class="chrome"><span>Product Proof</span><span>04</span></div>
  <div class="stage">
    ...
  </div>
</section>
```

Theme variants:

- Default: light product page.
- `theme-dark`: dark statement or contrast slide.
- `theme-accent`: one strong decision slide.
- `theme-yellow`: yellow/highlight decision slide.

Every slide uses `.chrome` and `.stage`. Do not put content outside `.stage`
except intentionally fixed navigation provided by the template.

## Typography

| Class | Use | Notes |
|---|---|---|
| `.display` | cover title | one per deck opening |
| `.title` | normal slide title | max one per slide |
| `.statement` | big transition claim | PG02 or PG12 |
| `.lead` | large support copy | 1-2 sentences |
| `.body` | normal explanatory copy | keep under 45 words per block |
| `.body-sm` | compact captions and card notes | not for dense paragraphs |
| `.kicker` | section marker | uppercase metadata |
| `.meta` | source, date, small labels | uppercase metadata |

The template controls type sizes. Do not add inline `font-size`. If content does
not fit, edit the copy or choose a different layout.

## Grid

Use `.grid-12` plus spans:

- `.span-3`: quarter width.
- `.span-4`: third width.
- `.span-5` / `.span-7`: analysis plus screenshot.
- `.span-6`: equal halves.
- `.span-8` / `.span-4`: narrative plus side notes.
- `.span-12`: full row.

Do not nest cards inside cards. Use one panel layer.

## Panels

```html
<div class="panel span-4">
  <div class="kicker">Signal</div>
  <div class="metric">3.4x</div>
  <p class="label">Qualified intent</p>
</div>
```

Panel variants:

- `.panel`: default quiet panel.
- `.panel-2`: stronger neutral emphasis.
- `.panel-accent`: exactly one highlight panel per slide.
- `.panel-ink`: black emphasis block for strong contrast.

## Images

```html
<div class="frame r-16x10 fit-contain">
  <img src="images/04-dashboard.png" alt="Dashboard screenshot" data-image-slot="pg04-main-16x10">
</div>
```

Rules:

- Every local image needs `alt` and `data-image-slot`.
- Raw screenshots with important text use `.fit-contain`.
- Generated images should match the slot ratio and use cover behavior.
- Never add shadows, browser chrome, or extra rounded wrappers.

## Timeline

```html
<div class="timeline">
  <div><strong class="metric-sm">01</strong><p class="body">Collect source signals.</p></div>
  <div><strong class="metric-sm">02</strong><p class="body">Match against knowledge.</p></div>
  <div><strong class="metric-sm">03</strong><p class="body">Generate output.</p></div>
  <div><strong class="metric-sm">04</strong><p class="body">Publish with controls.</p></div>
</div>
```

Keep timeline nodes short. If a step needs more than two lines, move detail to
a separate slide.

## Comparison

Use `.compare` for before/after, old/new, manual/worker, or risk/control.

```html
<div class="compare">
  <div class="stack-lg">...</div>
  <div class="divider"></div>
  <div class="stack-lg">...</div>
</div>
```

Both sides must use matching hierarchy and roughly equal copy length.

## System Diagram

Use `.diagram` for three layers or stages. Labels are HTML, not SVG.

```html
<div class="diagram">
  <div><div class="kicker">Input</div><p class="body">Sources and signals.</p></div>
  <div><div class="kicker">Worker</div><p class="body">Plan, execute, and log.</p></div>
  <div><div class="kicker">Output</div><p class="body">Published assets and findings.</p></div>
</div>
```

## Bar Evidence

Use `.bar-chart` when a slide compares actual values. Do not use it for vague
concepts.

```html
<div class="bar-chart">
  <div class="bar-row"><span class="label">Manual</span><span class="bar-track"><span class="bar-fill" style="--w:38%"></span></span><span class="metric-sm">38</span></div>
  <div class="bar-row"><span class="label">Worker</span><span class="bar-track"><span class="bar-fill" style="--w:86%"></span></span><span class="metric-sm">86</span></div>
</div>
```

## Matrix Brief

Use `.matrix` for eight compact evidence cells. Keep each cell to one short
line plus metadata.

```html
<div class="matrix">
  <div class="matrix-cell"><p class="body">Signal scan</p><p class="label">Input</p></div>
  <div class="matrix-cell is-accent"><p class="body">Published output</p><p class="label">Receipt</p></div>
</div>
```

## Density Budget

- Low density: title + one support block.
- Medium density: title + 3 cards or one screenshot.
- High density: title + 4 cards or diagram. Follow with PG02 or PG10.

Never combine high-density text with a detailed screenshot on the same slide.

## Visual Rhythm

- Use `theme-accent` or `theme-yellow` only for cover, shift, or closing slides.
- A deck should use one accent family. If `theme-yellow` is used, local labels and headings on that slide stay black.
- Use `theme-dark` for statements and quotes.
- Use `.dot-field` only on large statement/cover pages where it has room to breathe.
- Use `.ledger` for roadmap or ordered proof instead of ad hoc tables.
- Use `.metric-xl` for one giant number; use `.metric` for card numbers.
