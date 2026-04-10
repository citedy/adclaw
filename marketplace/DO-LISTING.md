# AdClaw — DigitalOcean Marketplace Listing

All fields for the Vendor Portal form at https://cloud.digitalocean.com/vendorportal

---

## System Image

- **Type:** Droplet 1-Click App
- **OS:** Ubuntu 24.04 LTS (x64)
- **Snapshot:** (created from clean $6 Droplet — see build instructions below)

---

## Software Included

| Package | Version | License |
|---------|---------|---------|
| [Docker CE](https://docs.docker.com/engine/) | 27.x | [Apache 2.0](https://github.com/moby/moby/blob/master/LICENSE) |
| [AdClaw](https://github.com/Citedy/adclaw) | 2.0.0 | [Apache 2.0](https://github.com/Citedy/adclaw/blob/main/LICENSE) |
| [UFW](https://launchpad.net/ufw) | (system) | [GPL](https://launchpad.net/ufw) |
| [fail2ban](https://github.com/fail2ban/fail2ban) | (system) | [GPL-2.0](https://github.com/fail2ban/fail2ban/blob/master/COPYING) |

---

## Minimum Resources

- **CPU:** 1 vCPU
- **RAM:** 2 GB
- **Disk:** 25 GB

---

## Application Summary

> AI marketing agent team with 118 built-in skills, multi-agent personas, 23 LLM providers, and web dashboard. Deploy in 60 seconds.

---

## Application Description

AdClaw is an open-source AI marketing agent platform that gives you a team of specialized AI personas — researcher, writer, SEO specialist, ads manager — all working together. It ships with 118 built-in skills covering SEO, content creation, ads, social media, analytics, and AI video generation, plus 52 marketing tools via the Citedy MCP server. Connect any of 23 LLM providers (OpenAI, Anthropic, Gemini, DeepSeek, Groq, and more) with automatic failover, and manage everything through a web dashboard or Telegram bot. Open the Web UI, enter your API key, and start chatting with your AI marketing team.

---

## Getting Started Instructions

```
After creating your AdClaw Droplet, you can access it in two ways:

Via the Web UI (recommended):
  1. Open http://your_droplet_public_ipv4:8088 in your browser
  2. Follow the welcome wizard to select your LLM provider and enter your API key
  3. Start chatting with your AI marketing team

Via SSH:
  ssh root@your_droplet_public_ipv4

Management commands (via SSH):
  adclaw-ctl status    — check service status
  adclaw-ctl logs      — stream container logs
  adclaw-ctl config    — edit environment configuration
  adclaw-ctl update    — pull latest version and restart
  adclaw-ctl restart   — restart service

Configuration file: /etc/adclaw/env
To connect a Telegram bot: add TELEGRAM_BOT_TOKEN to /etc/adclaw/env and run adclaw-ctl restart
```

---

## Port / Path

- **Port:** 8088
- **Path:** (leave empty)
- **Quick access URL:** `http://ip-address:8088`

---

## Managed Database Integration

- [ ] MySQL
- [ ] MongoDB
- [ ] Redis
- [ ] PostgreSQL

> Skip — AdClaw stores data in local files and SQLite. No external database needed.

---

## License Add-On

> Skip — AdClaw is open-source (Apache 2.0). No paid license required.

---

## Support Details

- **Supported by:** Citedy
- **Timezone:** UTC+1 (CET)
- **Support Hours:** Business hours (response within 24h)
- **Website:** https://www.citedy.com
- **Email:** support@citedy.com

### Emergency Contact (DO employees only)

- **Name:** Ntty
- **Email:** ntty@me.com

---

## Additional Links

| # | Name | URL | Description |
|---|------|-----|-------------|
| 1 | Documentation | https://github.com/Citedy/adclaw | Source code and full documentation |
| 2 | Getting Started | https://github.com/Citedy/adclaw/blob/main/docs/getting-started.md | Installation and setup guide |
| 3 | Skills Library | https://github.com/Citedy/adclaw/blob/main/docs/skills.md | 118 built-in marketing skills |
| 4 | Multi-Agent Guide | https://github.com/Citedy/adclaw/blob/main/docs/personas.md | Create specialized AI personas |
