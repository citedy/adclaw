# Deploying AdClaw outside DigitalOcean

For the DigitalOcean 1-click Droplet flow, use
[`docs/deploy/digitalocean.md`](./deploy/digitalocean.md).

AdClaw ships as a single Docker image (`nttylock/adclaw:latest`) with three variants: `full` (default, 4.2 GB, includes Chromium + Playwright + xvfb), `browser` (4.1 GB, browser-only), and `core` (2.7 GB, no browser, no desktop). For most managed-Docker platforms (Railway, Render, Fly.io, Northflank) **use `latest` (full)** unless you have a hard reason not to — see the variant tradeoff below.

## Quick reference

| Item | Value |
|---|---|
| Image | `nttylock/adclaw:1.0.5` (or `nttylock/adclaw:1.0.5-core` if minimal) |
| Architectures | release workflow publishes `linux/amd64`, `linux/arm64` |
| Container port | `8088` |
| Health check endpoint | `GET /api/diagnostics/health` → 200 |
| Persistent volumes | `/app/working` (config, sessions, skills) and `/app/working.secret` (provider API keys) — both **required** for restart-safe state |
| Min RAM | 2 GB for `full`, 1 GB for `core` |
| Min disk | 25 GB recommended (image + data + sqlite) |

## Variant choice

The Docker release workflow publishes multi-arch manifests for both
`linux/amd64` and `linux/arm64`.

| You're deploying… | Pick |
|---|---|
| A general AdClaw template / first deploy | `latest` (full) — Chromium ready, all skills work out of the box |
| RAM-constrained box (≤ 1.5 GB), no browser skills needed | `core` |
| Browser automation but no audio/video tools | `browser` |

**Why default to `full` on managed platforms (Railway, Render, Fly):** users don't see the image size on their bill — they pay for CPU/RAM/disk consumption. The 1.5 GB extra disk is ≈ $0.40/month at standard rates and prevents the worst first-time experience: a user types "open this URL and screenshot the hero" into chat and the agent reports it can't.

## Required environment variables

Most config lives in `/app/working/config.json` after first-boot wizard. The handful that should be set in the platform's env panel:

```bash
ADCLAW_ENABLED_CHANNELS=console,telegram   # any subset of: console,telegram,discord,dingtalk,feishu,qq
LOG_LEVEL=INFO                             # DEBUG for troubleshooting
TELEGRAM_BOT_TOKEN=...                     # if telegram channel enabled
```

LLM provider keys are entered through the wizard at `http://<host>:8088`, not env vars — they land in `/app/working.secret/providers.json`.

## Platform-specific notes

### Railway

1. **New Project → Deploy from Docker Image** → `nttylock/adclaw:1.0.5`.
2. Settings → Networking → expose port `8088`. Generate the public domain.
3. Settings → Variables → add `ADCLAW_ENABLED_CHANNELS=console,telegram` and any tokens.
4. Settings → Volumes → mount `adclaw-data` at `/app/working` and `adclaw-secret` at `/app/working.secret`. Both **must** persist or the wizard reruns on every redeploy and providers re-disappear.
5. Settings → Deploy → set **Health Check Path** to `/api/diagnostics/health`. Cold start is 20–40 s.
6. Bump the service to **2 GB RAM, 1 vCPU minimum** (default 512 MB will OOM `full`). Disk: 25 GB.

### Render

`render.yaml`:
```yaml
services:
  - type: web
    name: adclaw
    runtime: image
    image:
      url: docker.io/nttylock/adclaw:1.0.5
    plan: standard          # 2 GB RAM
    healthCheckPath: /api/diagnostics/health
    envVars:
      - key: ADCLAW_ENABLED_CHANNELS
        value: console,telegram
      - key: LOG_LEVEL
        value: INFO
    disk:
      name: adclaw-data
      mountPath: /app/working
      sizeGB: 25
```

Render only allows one disk per service — mount `/app/working` and accept that the secret volume is co-located on disk inside `/app/working.secret` if you symlink it (see `Caveats`).

### Fly.io

```bash
fly launch --image nttylock/adclaw:1.0.5 --no-deploy
# in fly.toml:
#   [http_service]
#     internal_port = 8088
#     [[http_service.checks]]
#       grace_period = "30s"
#       interval = "10s"
#       method = "GET"
#       path = "/api/diagnostics/health"
fly volumes create adclaw_data --size 25 --region ams
fly secrets set ADCLAW_ENABLED_CHANNELS=console,telegram
fly deploy
```

In `fly.toml` mount the volume:
```toml
[[mounts]]
  source = "adclaw_data"
  destination = "/app/working"
```

For two-volume parity with the Docker reference setup, create a second volume `adclaw_secret` and add a second `[[mounts]]` block on `/app/working.secret`.

### Northflank, Koyeb, plain VPS

Same recipe: image + port 8088 + two persistent volumes + health check on `/api/diagnostics/health` + min 2 GB RAM. Supply env vars from the platform's secret store.

### Plain Docker (any VPS)

```bash
docker run -d --name adclaw --restart unless-stopped \
  -p 8088:8088 \
  -v adclaw-data:/app/working \
  -v adclaw-secret:/app/working.secret \
  -e ADCLAW_ENABLED_CHANNELS=console,telegram \
  -e LOG_LEVEL=INFO \
  nttylock/adclaw:1.0.5
```

## Caveats

- **Two-volume requirement is real**: provider API keys live in `/app/working.secret/providers.json`. Skip the secret volume and every redeploy nukes your LLM credentials.
- **Moving vs pinned tags**: `latest`, `browser`, and `core` are moving tags. If you need a stable release pin, use a versioned tag such as `nttylock/adclaw:1.0.5-core` or a digest.
- **Cold start**: 20–40 s on first boot (Python + skill registry + SQLite migrations). Health check `grace_period` should be ≥ 30 s.
- **Memory profile**: `full` idles around 600–800 MB; spikes to 1.4 GB during skill use (Chromium pages). Sustained `core` is around 250 MB.
- **HTTP only by default**: place behind your platform's TLS-terminating proxy or run a Caddy/Cloudflare in front.

## Health check

```bash
curl http://<host>:8088/api/diagnostics/health
# → 200 OK
# → {"overall": "healthy", ...}
```

The endpoint is unauthenticated and intentionally lightweight — safe to poll every 10–30 s.
