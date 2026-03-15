# Browser Strategy — Which Tool, When, Why

## Overview

AdClaw has **4 browser automation tools**. Each has different strengths.
This guide tells agents (and humans) which one to use for which task.

```
  Task arrives
       |
       v
  +----+-----+
  | Is it     |
  | text-only |----YES----> PinchTab (cheapest, fastest)
  | extraction|              ~800 tokens/page
  +----+------+
       |NO
       v
  +----+------+
  | Needs     |
  | multi-step|----YES----> agent-browser (full workflow)
  | workflow? |              snapshot -> click -> fill -> submit
  +----+------+
       |NO
       v
  +----+------+
  | Needs     |
  | persistent|----YES----> browser-use (session persistence)
  | login?    |              cookies survive between runs
  +----+------+
       |NO
       v
  +----+------+
  | User wants|
  | to SEE    |----YES----> browser_visible (headed mode)
  | the browser|             real Chrome window
  +----+------+
       |NO
       v
  PinchTab (default — cheapest option)
```

---

## Decision Matrix

```
+-------------------+-----------+----------+----------+-----------+
| Capability        | PinchTab  | agent-   | browser- | browser_  |
|                   |           | browser  | use      | visible   |
+-------------------+-----------+----------+----------+-----------+
| Text extraction   | +++       | ++       | ++       | ++        |
| Token efficiency  | +++       | +        | +        | +         |
| Form filling      | ++        | +++      | +++      | +++       |
| Screenshots       | +         | +++      | +++      | +++       |
| Stealth mode      | +++       | +        | +        | +         |
| Multi-tab         | +++       | ++       | +        | +         |
| Persistent login  | +++       | ++       | +++      | +         |
| Electron apps     | -         | +++      | -        | -         |
| Visual debugging  | -         | +        | +        | +++       |
| Dogfood / QA      | -         | +++      | +        | ++        |
| Slack automation  | -         | +++      | -        | -         |
| Token cost/page   | ~800      | ~5,000   | ~5,000   | ~5,000    |
| Binary size       | 12MB      | ~200MB   | ~150MB   | ~150MB    |
| Dependencies      | none      | Node.js  | Python   | Python    |
+-------------------+-----------+----------+----------+-----------+

  +++ = best choice    ++ = good    + = works    - = not supported
```

---

## Tool Profiles

### 1. PinchTab (HTTP API)

```
  Endpoint: http://localhost:9867
  Binary:   12MB Go, zero deps
  Mode:     headless / headed
  Protocol: CDP (Chrome DevTools Protocol)
```

**Best for:**
- Text extraction from any webpage (cheapest: ~800 tokens)
- SERP scraping (Google, Bing results)
- News/article reading
- Price monitoring
- Competitor content analysis
- Any read-heavy task where you don't need screenshots

**How agents use it:**
```
  1. POST /instances/launch        --> get instance_id
  2. POST /instances/{id}/tabs/open --> get tab_id
  3. GET  /tabs/{id}/text          --> extracted text (~800 tokens)
  4. GET  /tabs/{id}/snapshot      --> interactive elements (refs)
  5. POST /tabs/{id}/action        --> click, fill, press
```

**Key advantage:** Accessibility-tree refs (`e0`, `e1`, ...) instead of
pixel coordinates. Stable across layout changes.

**Stealth:** Built-in bot detection evasion + IDPI domain allowlist.

---

### 2. agent-browser (CLI)

```
  Command:  agent-browser open/snapshot/click/fill
  Runtime:  Node.js + Chromium
  Protocol: CDP
```

**Best for:**
- Complex multi-step workflows (login -> navigate -> fill form -> submit)
- QA / dogfooding (structured bug reports with screenshots)
- Slack automation
- Electron app control (VS Code, Discord, Figma)
- Tasks requiring screenshots as evidence

**Sub-skills:**
```
  +------------------+--------------------------------------------+
  | Sub-skill        | When to use                                |
  +------------------+--------------------------------------------+
  | agent-browser    | General browser automation                 |
  | dogfood          | QA testing, find bugs, produce reports     |
  | slack            | Slack workspace automation                 |
  | electron         | Desktop app automation (VS Code, etc.)     |
  +------------------+--------------------------------------------+
```

**How agents use it:**
```bash
  agent-browser open https://example.com
  agent-browser snapshot -i          # get refs
  agent-browser click @e3            # click element
  agent-browser fill @e5 "query"     # fill input
  agent-browser screenshot           # capture proof
```

---

### 3. browser-use (CLI)

```
  Command:  browser-use <action>
  Runtime:  Python + Playwright
  Protocol: CDP
```

**Best for:**
- Persistent sessions (cookies/auth survive restarts)
- Form filling workflows
- Data extraction from authenticated pages
- Tasks requiring login state

**How agents use it:**
```bash
  browser-use doctor                 # check installation
  browser-use open https://app.com
  browser-use fill "#email" "user@example.com"
  browser-use click "button[type=submit]"
  browser-use screenshot
```

---

### 4. browser_visible (headed mode)

```
  Command:  browser_use with headed=true
  Runtime:  Python + Playwright
  Protocol: CDP
```

**Best for:**
- User wants to watch the browser in real-time
- Demos and presentations
- Visual debugging
- CAPTCHA solving (user intervenes manually)

**When to trigger:**
User says "open a real browser", "I want to see it", "show me", "visible browser".

---

## Cost Comparison

```
  Task: Read Hacker News front page

  +------------------+--------+---------+
  | Tool             | Tokens | Cost*   |
  +------------------+--------+---------+
  | PinchTab text    |    800 | $0.002  |
  | agent-browser    |  5,000 | $0.015  |
  | browser-use      |  5,000 | $0.015  |
  | Screenshot (any) | 10,000 | $0.030  |
  +------------------+--------+---------+
  * Approximate, based on GPT-4 pricing

  PinchTab is 6-13x cheaper for text extraction.
```

---

## Routing Rules for Agents

Agents should follow this priority order:

```
  Priority 1: PinchTab
  +---------------------------------------------------------+
  | USE WHEN:                                               |
  | - Extracting text/data from a webpage                   |
  | - Reading articles, news, search results                |
  | - Checking prices, stock, availability                  |
  | - Any task where text content is sufficient             |
  | - Stealth is important (bot detection sites)            |
  | - Running many parallel browser tasks                   |
  +---------------------------------------------------------+

  Priority 2: agent-browser
  +---------------------------------------------------------+
  | USE WHEN:                                               |
  | - Complex multi-step form workflows                     |
  | - QA testing / dogfooding with screenshot evidence      |
  | - Automating Slack, Electron apps                       |
  | - Need screenshots as proof of action                   |
  | - PinchTab can't handle the interaction                 |
  +---------------------------------------------------------+

  Priority 3: browser-use
  +---------------------------------------------------------+
  | USE WHEN:                                               |
  | - Need persistent authenticated sessions                |
  | - Simple form filling without complex workflows         |
  | - agent-browser is not available                        |
  +---------------------------------------------------------+

  Priority 4: browser_visible
  +---------------------------------------------------------+
  | USE WHEN:                                               |
  | - User explicitly asks to see the browser               |
  | - CAPTCHA requires human intervention                   |
  | - Demo or presentation mode                             |
  +---------------------------------------------------------+
```

---

## Fallback Chain

```
  PinchTab available?
       |
      YES --> Use PinchTab
       |
       NO
       |
  agent-browser available?
       |
      YES --> Use agent-browser
       |
       NO
       |
  browser-use available?
       |
      YES --> Use browser-use
       |
       NO
       |
  Report: "No browser tools available.
           Install PinchTab: curl -fsSL https://pinchtab.com/install.sh | bash"
```

---

## Setup

### PinchTab

```bash
# Install (one command)
curl -fsSL https://pinchtab.com/install.sh | bash

# Start server (runs on port 9867)
pinchtab

# Verify
curl http://localhost:9867/health
```

### agent-browser

Pre-installed in AdClaw Docker image. No setup needed.

```bash
agent-browser open https://example.com
```

### browser-use

Pre-installed in AdClaw Docker image. Verify:

```bash
browser-use doctor
```

---

## Integration with Personas

Each persona can be configured to prefer specific browser tools:

```
  Researcher persona:
    Primary:   PinchTab (cheap text extraction)
    Fallback:  agent-browser (if interaction needed)
    Use case:  SERP analysis, news scanning, competitor monitoring

  SEO Specialist persona:
    Primary:   PinchTab (SERP scraping, stealth)
    Secondary: agent-browser (site auditing with screenshots)
    Use case:  Rank tracking, technical audits, competitor analysis

  Content Writer persona:
    Primary:   PinchTab (research, article reading)
    Use case:  Source research, fact-checking, inspiration

  Social Media persona:
    Primary:   agent-browser (platform interaction)
    Fallback:  PinchTab (trend reading)
    Use case:  Post scheduling, trend monitoring, engagement

  Ads Manager persona:
    Primary:   agent-browser (ad platform dashboards)
    Secondary: PinchTab (competitor ad reading)
    Use case:  Campaign management, competitor ad analysis
```
