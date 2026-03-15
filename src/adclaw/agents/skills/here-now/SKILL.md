---
name: here-now
title: "here.now File Publisher"
description: >
  Instantly publish any file to the web and get a shareable link.
  Upload reports, PDFs, HTML pages, images, or any file to here.now —
  free instant hosting for AI agents. Anonymous uploads expire in 24 hours;
  set HERENOW_API_KEY for permanent links.
version: "1.0.0"
author: nttylock
tags:
  - file-sharing
  - hosting
  - publishing
  - utilities
metadata:
  openclaw:
    requires:
      env:
        - HERENOW_API_KEY
    primaryEnv: HERENOW_API_KEY
security_notes: |
  Files are uploaded to here.now (third-party service).
  Anonymous uploads are public and expire in 24 hours.
  Authenticated uploads are permanent. Do not upload sensitive data
  unless you understand the privacy implications.
---

# here.now File Publisher

## Overview

Publish any file to the web instantly using here.now. Get a shareable public URL
that you can send to the user in any channel (Telegram, Discord, etc.).

This solves the problem of channels that can't send file attachments —
instead of struggling with attachment limits, just upload and share the link.

## When to Use

- You created a file (report, PDF, HTML, image) and want to share it with the user
- The channel doesn't support file attachments or has size limits
- You want to give the user a link they can open in a browser
- Use the `publish_to_herenow` tool with the file path

## How to Use

### Publish a file

```
Tool: publish_to_herenow
Arguments:
  file_path: "/path/to/report.pdf"
```

Returns a public URL like `https://bright-canvas-a7k2.here.now/report.pdf`

### Example workflow

1. Create the file (write report, generate PDF, etc.)
2. Call `publish_to_herenow` with the file path
3. Share the returned URL with the user
4. Optionally also send the file as an attachment if the channel supports it

## Configuration

- **Without API key**: anonymous mode, links expire in 24 hours, 250MB max file size
- **With HERENOW_API_KEY**: permanent links, 5GB max file size

Set the API key as an environment variable or in the AdClaw settings.

## Supported File Types

All file types are supported: HTML, CSS, JS, images, PDFs, videos, documents, archives, and more.

## Limits

| Feature | Anonymous | Authenticated |
|---------|-----------|---------------|
| Max file size | 250 MB | 5 GB |
| Link expiry | 24 hours | Permanent |
| Rate limit | 5/hour | 60/hour |
