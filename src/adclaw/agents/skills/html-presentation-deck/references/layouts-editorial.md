# Editorial Layouts

Use these section skeletons inside `assets/template-editorial.html`.

## Cover

```html
<section class="slide dark">
  <div class="kicker">Product Strategy / 2026</div>
  <h1 class="hero-title">The market is moving faster than our planning cycle.</h1>
  <p class="lead">A practical operating model for turning weekly signals into launch decisions.</p>
  <div class="meta">Project / Confidential</div>
</section>
```

## Two Column Narrative

```html
<section class="slide">
  <div class="grid-2">
    <div>
      <div class="kicker">Context</div>
      <h2 class="headline">The old funnel is now a network of moments.</h2>
      <p class="lead">Discovery, evaluation, and trust happen across search, communities, AI answers, and product proof.</p>
    </div>
    <div class="frame"><img src="images/03-market-map.jpg" alt="Market map"></div>
  </div>
</section>
```

## Three Evidence Cards

```html
<section class="slide">
  <div class="kicker">Evidence</div>
  <h2 class="headline">Three signals changed the plan.</h2>
  <div class="rule"></div>
  <div class="grid-3">
    <article class="card">
      <div class="number">42%</div>
      <h3>Search shifted</h3>
      <p>More discovery moved into AI summaries and community threads.</p>
    </article>
    <article class="card">
      <div class="number">3.1x</div>
      <h3>Proof compounds</h3>
      <p>Customer examples outperform generic category claims.</p>
    </article>
    <article class="card">
      <div class="number">9d</div>
      <h3>Launch window</h3>
      <p>The best content now ships while the discussion is still live.</p>
    </article>
  </div>
</section>
```

## Quote

```html
<section class="slide accent">
  <div class="kicker">Principle</div>
  <p class="quote">A launch is not a day. It is a sequence of proof arriving at the right moment.</p>
  <p class="caption">Use this layout for a memorable transition or closing idea.</p>
</section>
```
