---
name: skill-creator
title: "Skill Creator"
description: >
  Create custom skills for AdClaw. A skill is a directory with a SKILL.md file
  that teaches the agent new capabilities — tools, workflows, or domain knowledge.
version: "1.0.0"
author: AdClaw
tags:
  - meta
  - skill-creation
  - customization
metadata:
  openclaw:
    emoji: "🛠️"
---

# Skill Creator

You can create new skills for the user. A skill is a directory containing a `SKILL.md` file and optional `references/` and `scripts/` subdirectories.

## Skill Directory Structure

```
my-skill/
├── SKILL.md              # Required: skill definition and instructions
├── references/           # Optional: reference documentation
│   └── api-docs.md
└── scripts/              # Optional: executable scripts
    └── helper.py
```

## SKILL.md Format

The SKILL.md file must start with YAML frontmatter (between `---` delimiters), followed by markdown instructions.

### Required Frontmatter Fields

```yaml
---
name: my-skill-name          # Unique identifier (lowercase, hyphens allowed)
description: >               # Brief description of what the skill does
  A short description of the skill's purpose and capabilities.
---
```

### Optional Frontmatter Fields

```yaml
---
name: my-skill-name
title: "My Skill Display Name"    # Human-readable title
description: >
  Description here.
version: "1.0.0"
author: Your Name
tags:
  - category1
  - category2
metadata:
  openclaw:
    emoji: "🔧"                  # Emoji icon for the skill
    requires:
      env:                        # Required environment variables
        - MY_API_KEY
      bins:                       # Required system binaries
        - curl
    primaryEnv: MY_API_KEY        # Main env var for authentication
---
```

### Markdown Body

After the frontmatter, write the skill instructions in markdown. This is what the agent reads to understand how to use the skill. Include:

1. **Overview** — what the skill does
2. **Available tools/commands** — what the agent can do with this skill
3. **Usage examples** — concrete examples of how to use each capability
4. **Important notes** — constraints, rate limits, authentication requirements

## How to Create a Skill

When the user asks to create a skill:

1. Ask the user what the skill should do
2. Create the skill directory in the customized skills location
3. Write the SKILL.md file with proper frontmatter and instructions
4. Optionally add reference docs in `references/`
5. Optionally add helper scripts in `scripts/`
6. Enable the skill so it appears in active skills

### Creating the Skill File

Use the file writing tool to create the skill at:
```
{working_dir}/customized_skills/{skill-name}/SKILL.md
```

Where `{working_dir}` is the AdClaw working directory (typically `~/.adclaw/`).

### Example: Creating a Simple Skill

```markdown
---
name: weather-checker
title: "Weather Checker"
description: >
  Check current weather and forecasts for any location using the wttr.in API.
version: "1.0.0"
author: User
tags:
  - weather
  - utility
metadata:
  openclaw:
    emoji: "🌤️"
---

# Weather Checker

Check weather for any location using wttr.in.

## Usage

To check weather, run:
\```bash
curl -s "wttr.in/{location}?format=3"
\```

## Examples

- Current weather: `curl -s "wttr.in/London?format=3"`
- Detailed forecast: `curl -s "wttr.in/Tokyo"`
- Moon phase: `curl -s "wttr.in/Moon"`
```

## Guidelines for Good Skills

- Keep skill names lowercase with hyphens (e.g., `my-cool-skill`)
- Write clear, specific instructions — the agent will follow them literally
- Include concrete examples with expected inputs and outputs
- Document any required environment variables or API keys
- If the skill uses external APIs, note rate limits and authentication
- Keep the SKILL.md focused — one skill per capability domain
