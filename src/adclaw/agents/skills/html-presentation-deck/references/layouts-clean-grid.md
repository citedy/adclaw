# Clean Grid Layouts

Use these section skeletons inside `assets/template-clean-grid.html`.

## Cover

```html
<section class="slide">
  <div class="chrome"><span>Operating Review</span><span>Q3 / 2026</span></div>
  <h1 class="display">Growth needs a tighter feedback loop.</h1>
  <p class="lead">A clean view of the decisions, signals, and assets that move the next quarter.</p>
</section>
```

## Metric Wall

```html
<section class="slide">
  <div class="chrome"><span>Signals</span><span>01</span></div>
  <div class="grid-12">
    <div class="panel span-4">
      <div class="eyebrow">Pipeline</div>
      <div class="metric">2.8x</div>
      <p class="label">Qualified demand</p>
    </div>
    <div class="panel span-4">
      <div class="eyebrow">Content</div>
      <div class="metric">64%</div>
      <p class="label">Assisted conversions</p>
    </div>
    <div class="panel span-4 accent">
      <div class="eyebrow">Decision</div>
      <div class="metric">14d</div>
      <p class="label">Planning cycle</p>
    </div>
  </div>
</section>
```

## Screenshot + Analysis

```html
<section class="slide">
  <div class="chrome"><span>Product Proof</span><span>02</span></div>
  <div class="grid-12">
    <div class="span-7">
      <div class="frame r-16x10 fit-contain">
        <img src="images/04-dashboard.png" alt="Dashboard screenshot" data-image-slot="main-16x10">
      </div>
    </div>
    <div class="panel span-5">
      <div class="eyebrow">Readout</div>
      <h2 class="title">The interface already contains the sales story.</h2>
      <p class="body">Use annotations only where they clarify a decision. Do not decorate screenshots just to fill space.</p>
    </div>
  </div>
</section>
```

`data-image-slot` is optional metadata for downstream validation or export tooling. It labels the intended image slot and aspect ratio; see `references/image-prompts.md` and `references/screenshot-framing.md` for the matching ratio guidance.

## Timeline

```html
<section class="slide">
  <div class="chrome"><span>Plan</span><span>03</span></div>
  <h2 class="title">Four moves over six weeks.</h2>
  <div class="rule"></div>
  <div class="timeline">
    <div><strong>01</strong><p>Collect signal sources.</p></div>
    <div><strong>02</strong><p>Build proof assets.</p></div>
    <div><strong>03</strong><p>Launch with channel owners.</p></div>
    <div><strong>04</strong><p>Review and compound winners.</p></div>
  </div>
</section>
```
