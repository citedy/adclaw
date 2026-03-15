---
name: email
title: "Send Email"
description: >
  Send emails directly from your agent. Supports HTML and plain text.
  Works with Unosend (5,000 free emails/month) or any SMTP provider.
version: "1.0.0"
author: AdClaw
tags:
  - email
  - notification
  - communication
  - smtp
  - unosend
metadata:
  openclaw:
    requires:
      env:
        - UNOSEND_API_KEY
        - SMTP_FROM
    primaryEnv: UNOSEND_API_KEY
security_notes: |
  Uses SMTP with TLS encryption. API key authenticates via SMTP login.
  No emails are stored by AdClaw — delivery is handled by the SMTP provider.
---

# Send Email — Skill Instructions

## Overview

Send emails directly from your agent — reports, notifications, summaries, alerts.
Works with Unosend (5,000 free emails/month) or any SMTP provider.

**Use cases:**

- "Send the SEO report to team@company.com"
- "Email this summary to the client"
- "Notify marketing@company.com about the new trends"
- "Send a weekly digest to the team"

## When to Use

| Situation | What to do |
|-----------|------------|
| User asks to send/email something | Use `send_email` tool |
| User wants to notify someone | Compose message + `send_email` |
| User asks to share a report via email | Generate HTML report + `send_email` |

## Setup

### Option A: Unosend (recommended, free tier)

1. Sign up at [unosend.com](https://unosend.com)
2. Add and verify your sending domain
3. Get your API key (starts with `un_`)
4. Set environment variables:
   - `UNOSEND_API_KEY=un_your_key`
   - `SMTP_FROM=noreply@yourdomain.com`

5,000 emails/month free, no credit card needed.

### Option B: Custom SMTP

Set these environment variables:

```
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=your_username
SMTP_PASSWORD=your_password
SMTP_FROM=noreply@yourdomain.com
```

## Tool Reference

### send_email

```
send_email(
    to="recipient@example.com",
    subject="Weekly SEO Report",
    body="<h1>Report</h1><p>Your rankings improved 15%...</p>",
    html=True
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to` | string | yes | Recipient email (comma-separated for multiple) |
| `subject` | string | yes | Email subject line |
| `body` | string | yes | Email content (HTML or plain text) |
| `html` | bool | no | Treat body as HTML (default: true) |
| `from_email` | string | no | Sender email (default: from env) |
| `from_name` | string | no | Sender display name (default: AdClaw) |

## Response Guidelines

When sending emails:

1. **Confirm before sending** — always tell the user what you're about to send and to whom
2. **Use HTML for rich content** — tables, bold, headers make emails professional
3. **Keep subject lines clear** — "Weekly SEO Report — March 15" not "Report"
4. **Report success** — tell the user the email was sent with recipient and subject
