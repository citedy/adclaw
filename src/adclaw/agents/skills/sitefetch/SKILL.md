---
name: Site Fetcher
description: Fetch entire websites or specific pages as clean text for AI analysis. Use for competitor analysis, content audits, SEO research, and gathering reference material from any website.
read_when:
  - Fetching website content for analysis
  - Competitor site analysis
  - Content audit of a website
  - Gathering text from multiple pages
  - Downloading site content for review
metadata: {"clawdbot":{"emoji":"📥","requires":{"bins":["node","npx"]}}}
allowed-tools: Bash(sitefetch:*)
---

# Site Fetcher (sitefetch)

Fetch an entire website (or specific pages) as clean readable text — ready for AI analysis.

## Quick Usage

```bash
# Fetch entire site
sitefetch https://example.com -o site.txt

# Fetch only blog posts
sitefetch https://example.com --match '/blog/**' -o blog.txt

# Fetch with higher concurrency (faster)
sitefetch https://example.com --concurrency 10 -o site.txt

# Fetch specific section
sitefetch https://docs.example.com --match '/api/**' -o api-docs.txt
```

## When to Use

- **Competitor analysis**: fetch their site, analyze content strategy
- **Content audit**: get all pages as text, find gaps
- **SEO research**: extract all content from a domain
- **Documentation gathering**: pull docs site into one file
- **Before/after comparison**: fetch site, make changes, fetch again

## Output

Creates a single text file with all pages concatenated. Each page is separated with its URL. Content is extracted using Mozilla Readability (same as Firefox Reader View) — no ads, navs, footers.

## Options

- `-o, --output <file>` — output file path (default: stdout)
- `--match <glob>` — only fetch pages matching glob pattern
- `--concurrency <n>` — parallel requests (default: 5)

## Examples

### Analyze competitor blog
```bash
sitefetch https://competitor.com --match '/blog/**' -o /tmp/competitor-blog.txt
# Then read and analyze the file
```

### Full site content audit
```bash
sitefetch https://mysite.com -o /tmp/mysite-content.txt
# Analyze for thin content, duplicates, missing topics
```

### Grab documentation
```bash
sitefetch https://docs.library.com -o /tmp/docs.txt
# Use as reference for implementation
```

## Notes

- HTTP only (no JavaScript rendering) — for JS-heavy SPAs use `agent-browser` instead
- Respects robots.txt
- Works best on content-heavy sites (blogs, docs, marketing pages)
- For single interactive pages, prefer `agent-browser`
