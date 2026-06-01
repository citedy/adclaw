# Product Grid Layouts

Use these exact skeletons with `assets/template-product-grid.html`.

## PG01 Cover System

```html
<section class="slide theme-accent" data-system="product-grid" data-layout="PG01">
  <div class="dot-field"></div>
  <div class="chrome"><span>Product Launch</span><span>01</span></div>
  <div class="stage">
    <div class="grid-12">
      <div class="span-8 stack-lg">
        <div class="kicker">Citedy Workers</div>
        <h1 class="display">Marketing work that keeps moving.</h1>
        <p class="lead">One screen for long-running workers that research, create, publish, and report the receipt.</p>
      </div>
      <div class="span-4">
        <div class="panel h-full stack-lg">
          <div class="metric">24/7</div>
          <p class="label">Always-on execution</p>
        </div>
      </div>
    </div>
  </div>
  <div class="cover-mark"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
</section>
```

## PG02 Statement

```html
<section class="slide theme-dark" data-system="product-grid" data-layout="PG02">
  <div class="chrome"><span>Problem</span><span>02</span></div>
  <div class="stage">
    <h2 class="statement">The founder is still the content queue.</h2>
    <p class="lead">The product has automation, but the operating loop still asks the user to watch every tab.</p>
  </div>
</section>
```

## PG03 Metric Wall

```html
<section class="slide" data-system="product-grid" data-layout="PG03">
  <div class="chrome"><span>Operating Shape</span><span>03</span></div>
  <div class="stage">
    <h2 class="title title-wide">The offer is a rentable marketing team.</h2>
    <div class="grid-12">
      <div class="panel span-4"><div class="kicker">Coverage</div><div class="metric">24/7</div><p class="label">Always-on workers</p></div>
      <div class="panel span-4"><div class="kicker">Surface</div><div class="metric">1</div><p class="label">Casual screen</p></div>
      <div class="panel panel-accent span-4"><div class="kicker">Fleet</div><div class="metric">4</div><p class="label">Preset jobs</p></div>
    </div>
  </div>
</section>
```

## PG04 Screenshot Proof

```html
<section class="slide" data-system="product-grid" data-layout="PG04">
  <div class="chrome"><span>Product Proof</span><span>04</span></div>
  <div class="stage">
    <div class="grid-12 h-full">
      <div class="span-7">
        <div class="frame r-16x10 fit-contain">
          <img src="images/04-dashboard.png" alt="Dashboard screenshot" data-image-slot="pg04-main-16x10">
        </div>
      </div>
      <div class="panel span-5 stack">
        <div class="kicker">Readout</div>
        <h2 class="title">Show output before configuration.</h2>
        <p class="body">Screenshots should prove state, controls, and product value. Keep annotations sparse and leave the UI readable.</p>
      </div>
    </div>
  </div>
</section>
```

## PG05 Three Cards

```html
<section class="slide" data-system="product-grid" data-layout="PG05">
  <div class="chrome"><span>Worker Fleet</span><span>05</span></div>
  <div class="stage">
    <h2 class="title title-wide">Three jobs, one operating loop.</h2>
    <div class="grid-12">
      <div class="panel span-4 stack"><div class="kicker">Writer</div><p class="body">Finds source signals, writes articles, and prepares distribution.</p></div>
      <div class="panel span-4 stack"><div class="kicker">Creator</div><p class="body">Turns product knowledge into short-form video assets.</p></div>
      <div class="panel span-4 stack"><div class="kicker">Scout</div><p class="body">Watches competitor pages and reports meaningful changes.</p></div>
    </div>
  </div>
</section>
```

## PG06 Process Timeline

```html
<section class="slide" data-system="product-grid" data-layout="PG06">
  <div class="chrome"><span>Operating Loop</span><span>06</span></div>
  <div class="stage">
    <h2 class="title title-wide">Signal turns into output through one path.</h2>
    <div class="timeline">
      <div><strong class="metric-sm">01</strong><p class="body">Scan approved sources.</p></div>
      <div><strong class="metric-sm">02</strong><p class="body">Match product knowledge.</p></div>
      <div><strong class="metric-sm">03</strong><p class="body">Generate the asset.</p></div>
      <div><strong class="metric-sm">04</strong><p class="body">Publish or request review.</p></div>
    </div>
  </div>
</section>
```

## PG07 Before After

```html
<section class="slide" data-system="product-grid" data-layout="PG07">
  <div class="chrome"><span>Shift</span><span>07</span></div>
  <div class="stage">
    <div class="compare">
      <div class="stack-lg"><div class="kicker">Before</div><h2 class="title">Manual content operations.</h2><p class="body">The user coordinates research, writing, visuals, posting, and monitoring across disconnected tools.</p></div>
      <div class="divider"></div>
      <div class="stack-lg"><div class="kicker">After</div><h2 class="title">Worker-managed execution.</h2><p class="body">Workers run the loop and report outputs, exceptions, and approval requests in one feed.</p></div>
    </div>
  </div>
</section>
```

## PG08 System Diagram

```html
<section class="slide" data-system="product-grid" data-layout="PG08">
  <div class="chrome"><span>Architecture</span><span>08</span></div>
  <div class="stage">
    <h2 class="title title-wide">Workers remain clients of the primary API.</h2>
    <div class="diagram">
      <div><div class="kicker">Inputs</div><p class="body">Sources, schedules, account state, and tenant knowledge.</p></div>
      <div><div class="kicker">Runtime</div><p class="body">Plan runs, enforce budget, execute tasks, and emit events.</p></div>
      <div><div class="kicker">Outputs</div><p class="body">Articles, shorts, findings, approvals, and live feed receipts.</p></div>
    </div>
  </div>
</section>
```

## PG09 Evidence Grid

```html
<section class="slide" data-system="product-grid" data-layout="PG09">
  <div class="chrome"><span>Evidence</span><span>09</span></div>
  <div class="stage">
    <div class="grid-12">
      <div class="panel span-4 stack"><div class="kicker">Policy</div><p class="body">Trust levels decide whether work publishes, previews, or asks every time.</p></div>
      <div class="panel span-4 stack"><div class="kicker">Billing</div><p class="body">Rent and operations draw from the same tenant credit balance.</p></div>
      <div class="panel panel-2 span-4 stack"><div class="kicker">Control</div><p class="body">Budget caps stop expensive work before it starts.</p></div>
    </div>
  </div>
</section>
```

## PG10 Quote

```html
<section class="slide theme-dark" data-system="product-grid" data-layout="PG10">
  <div class="dot-field"></div>
  <div class="chrome"><span>Takeaway</span><span>10</span></div>
  <div class="stage">
    <blockquote class="quote">The feed is the proof that the worker actually worked.</blockquote>
    <p class="meta">Launch narrative</p>
  </div>
</section>
```

## PG11 Ledger

```html
<section class="slide" data-system="product-grid" data-layout="PG11">
  <div class="chrome"><span>Rollout</span><span>11</span></div>
  <div class="stage">
    <h2 class="title title-wide">Launch in phases without splitting the product.</h2>
    <div class="ledger">
      <div class="ledger-row"><div class="metric-sm">01</div><p class="body">Casual surface and scheduled workers on the existing runtime.</p><p class="label">Phase 1</p></div>
      <div class="ledger-row"><div class="metric-sm">02</div><p class="body">Advanced dashboard, MCP tools, and Cloudflare execution.</p><p class="label">Phase 2</p></div>
      <div class="ledger-row"><div class="metric-sm">03</div><p class="body">Browser Radar, priority behavior, and live progress.</p><p class="label">Phase 3</p></div>
    </div>
  </div>
</section>
```

## PG12 Closing

```html
<section class="slide theme-yellow" data-system="product-grid" data-layout="PG12">
  <div class="chrome"><span>Decision</span><span>12</span></div>
  <div class="stage">
    <div class="grid-12">
      <div class="span-8 stack-lg">
        <h2 class="statement">Stop managing marketing work. Hire the workers.</h2>
      </div>
      <div class="panel span-4 stack">
        <div class="kicker">Call to action</div>
        <p class="body">Connect accounts once, turn workers on, and review the live feed when the work is done.</p>
      </div>
    </div>
  </div>
</section>
```

## PG13 Bar Evidence

```html
<section class="slide" data-system="product-grid" data-layout="PG13">
  <div class="chrome"><span>Evidence</span><span>13</span></div>
  <div class="stage">
    <div class="grid-12">
      <div class="span-5 stack-lg">
        <div class="kicker">Quantified Shift</div>
        <h2 class="title">Use bars only when values are real.</h2>
        <p class="body">This layout is for measured comparison: coverage, time saved, adoption, throughput, accuracy, or cost.</p>
      </div>
      <div class="span-7">
        <div class="bar-chart">
          <div class="bar-row"><span class="label">Manual</span><span class="bar-track"><span class="bar-fill" style="--w:38%"></span></span><span class="metric-sm">38</span></div>
          <div class="bar-row"><span class="label">Assisted</span><span class="bar-track"><span class="bar-fill" style="--w:64%"></span></span><span class="metric-sm">64</span></div>
          <div class="bar-row"><span class="label">Worker</span><span class="bar-track"><span class="bar-fill" style="--w:86%"></span></span><span class="metric-sm">86</span></div>
        </div>
      </div>
    </div>
  </div>
</section>
```

## PG14 Matrix Brief

```html
<section class="slide" data-system="product-grid" data-layout="PG14">
  <div class="chrome"><span>Brief</span><span>14</span></div>
  <div class="stage">
    <h2 class="title title-wide">Eight compact proof points, one highlighted takeaway.</h2>
    <div class="matrix">
      <div class="matrix-cell"><p class="body">Source scan</p><p class="label">Input</p></div>
      <div class="matrix-cell"><p class="body">Knowledge match</p><p class="label">Filter</p></div>
      <div class="matrix-cell"><p class="body">Article draft</p><p class="label">Output</p></div>
      <div class="matrix-cell"><p class="body">Video short</p><p class="label">Output</p></div>
      <div class="matrix-cell"><p class="body">Approval gate</p><p class="label">Control</p></div>
      <div class="matrix-cell"><p class="body">Budget cap</p><p class="label">Policy</p></div>
      <div class="matrix-cell is-accent"><p class="body">Live receipt</p><p class="label">Proof</p></div>
      <div class="matrix-cell"><p class="body">Digest</p><p class="label">Report</p></div>
    </div>
  </div>
</section>
```
