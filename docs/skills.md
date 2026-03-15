# Skills Guide

Skills are instruction sets that teach AdClaw how to perform specific tasks. Each skill is a markdown file (`SKILL.md`) that describes the task, tools to use, and expected output format.

## Pre-installed Skills

### Citedy SEO Agent
Full-stack SEO workflow: keyword research, competitor analysis, content briefs, and optimization scoring.

**Triggers:** "SEO audit for my website", "find keywords for [topic]", "analyze my competitors"

### Citedy Content Writer
Blog autopilot that generates SEO-optimized articles with proper structure, internal linking, and meta tags.

**Triggers:** "write a blog post about [topic]", "create an article targeting [keyword]"

### Citedy Content Ingestion
Ingests URLs and converts them into structured content for repurposing.

**Triggers:** "ingest this URL: [url]", "extract content from [url]"

### Citedy Trend Scout
Scouts X/Twitter and Reddit for trending topics in your niche.

**Triggers:** "find trending topics about [niche]", "what's trending in [industry]"

### Citedy Lead Magnets
Generates lead magnets: ebooks, checklists, templates, and guides.

**Triggers:** "create a lead magnet about [topic]", "generate an ebook on [subject]"

### Citedy Video Shorts
Creates AI UGC short-form video scripts and storyboards.

**Triggers:** "create a short video about [topic]", "make a TikTok script for [product]"

### Skill Creator
Meta-skill that helps you create new custom skills through conversation.

**Triggers:** "create a new skill", "help me build a skill for [task]"

### Self-Setup
Allows the agent to configure LLM providers and models through conversation.

**Triggers:** "add OpenAI provider", "switch to Claude", "what models are available?"

## Managing Skills

### Via Web UI
Navigate to `/skills` to enable, disable, or view installed skills.

### Via API
```bash
# List all skills
curl http://localhost:8088/api/skills

# Enable a skill
curl -X POST http://localhost:8088/api/skills/enable \
  -H "Content-Type: application/json" \
  -d '{"skill_name": "citedy-seo-agent"}'

# Disable a skill
curl -X POST http://localhost:8088/api/skills/disable \
  -H "Content-Type: application/json" \
  -d '{"skill_name": "citedy-seo-agent"}'
```

## Creating Custom Skills

1. Ask the bot: "create a new skill for [your task]"
2. Or manually create a `SKILL.md` file in `/app/working/customized_skills/your-skill-name/`

### Skill File Format

```markdown
# Skill Name

Description of what the skill does.

## When to Use
- Trigger condition 1
- Trigger condition 2

## Instructions
Step-by-step instructions for the agent.

## Output Format
Expected output structure.
```

## Updating Citedy Skills

Pull the latest skill versions from GitHub:

```bash
curl -X POST http://localhost:8088/api/skills/hub/update-citedy
```
