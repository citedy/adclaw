# Railway Deployment State (private — internal log)

Snapshot of everything that was set up on Railway for AdClaw on **2026-04-30 → 2026-05-01**. This file lives in private `nttylock/AdClaw` only — do **not** sync to `Citedy/adclaw`.

## Live state

| Item | Value |
|---|---|
| **Marketplace template URL** | https://railway.com/deploy/adclaw |
| **Internal template code** | `EiYV1y` (retired after publish; `/deploy/EiYV1y` now 404) |
| **Internal template ID** | `b56e2af1-f649-4ff9-8850-32fb5d0390cf` |
| **Deploy URL on adclaw.app** | `https://railway.com/deploy/adclaw?referralCode=8K6-i5&utm_medium=integration&utm_source=template&utm_campaign=generic` |
| **Live demo instance** | https://adclaw-production.up.railway.app/ |
| **Railway plan** | Hobby ($5/mo + usage). Free 512 MB plan **does not work** — full and core variants both OOM at startup. |
| **Template status (API)** | published, but `templatePublish` mutation returns "blocked from publishing templates" — UI publish was the path that worked. Sales unblock pending. |

## Project IDs (need this constantly for API calls)

```
projectId      = a08d221b-61ae-451c-8b2c-04c3620ad919
environmentId  = ccb97ac8-e1ef-4562-8362-645d955f0689
serviceId      = 3bb47a68-10c9-411c-b002-7acaba1b5df3
workspaceId    = 3511933e-a5a8-4630-8c1e-edb9ffd5faf1
```

## Tokens (for the API; ask user before persisting elsewhere)

- **Project Access Token** (header `Project-Access-Token: <token>`): scoped to one project, can read/write the service but cannot publish templates / read account-level data
- **Account Token** (header `Authorization: Bearer <token>`): full account scope, `templateGenerate` / `templatePublish` / workspace read. Required to manage templates.

The user provided these in chat — they live in their head, not in this file. Re-ask in new sessions.

## Service config (live on Railway right now)

- **Source:** `nttylock/adclaw:1.0.2-core` Docker Hub image (NOT GitHub repo)
- **Reason `core`, not `full`:** core fits Hobby 2 GB without spike pressure, full sometimes flaps. Once the v2 runtime IPv6 quirk is resolved we can revisit `full`.
- **startCommand:** `sh -c 'adclaw init --defaults --accept-security 2>/dev/null || true; exec /app/venv/bin/adclaw app --host 0.0.0.0 --port 8088'`
- **Variables:** only `PORT=8088` (LOG_LEVEL and ADCLAW_ENABLED_CHANNELS were removed; ADCLAW_ENABLED_CHANNELS now defaults to `console` per image entrypoint)
- **Public domain:** `adclaw-production.up.railway.app` with `targetPort: 8088`
- **Volumes:** none currently. Earlier we attached `/app/working` and `/app/working.secret` but two-volume mount on the same service caused the container to fail to start; one-volume only also failed silently. Image works fine without persistent volumes for the wizard demo (config is regenerated on each redeploy). For real users in the template, we recommend they add a `/app/working` volume in Railway → Volumes after first deploy — see `docs/deploy/railway.md`.
- **healthcheckPath:** `/api/diagnostics/health`
- **healthcheckTimeout:** `300` (5 min) — Railway's max
- **sleepApplication:** `false`

## Required gotcha for any Railway deploy of AdClaw

> **Always set `PORT=8088` env var on the service.** Even though `serviceDomain.targetPort=8088` tells the public proxy where to forward, Railway's **internal health-check probe** queries `$PORT` (Railway-assigned, defaults to a random port). Without `PORT=8088` env, the probe goes to the wrong port, every healthcheck times out for 5 min, deploy is marked FAILED. We burned 6 deploys before finding this.
>
> Symptom: app logs show "Application startup complete" + "Uvicorn running on http://0.0.0.0:8088", but Railway healthcheck retries with "service unavailable" 9 times then fails.

## File locations

| File | Repo | Purpose |
|---|---|---|
| `railway.json` | both private + public | Build config — points to `deploy/Dockerfile`, healthcheck, builder=DOCKERFILE. **Must be at repo root, not `deploy/`** — Railpack only reads from root |
| `deploy/Dockerfile` | both | Multi-variant build (full / browser / core via `ADCLAW_VARIANT`) |
| `deploy/entrypoint.sh` | both | `adclaw init` once + supervisord. **NOT used on Railway** — we override startCommand to bypass supervisord (whose stdout writes to `/var/log/*` files, invisible to Railway logs) |
| `docs/deploy/railway.md` | both | Public guide — link this from Railway template README field |
| `marketplace/RAILWAY-README.md` | **private only** | Internal marketing-format readme that fits Railway's official template (their boilerplate "Why Deploy on Railway?" etc.). Never sync to public — caught by `feedback_public_repo_security.md` rule |
| `marketplace/RAILWAY-TEMPLATE.md` | **private only** | Earlier draft with API publish recipe; superseded by RAILWAY-README.md |
| `website-landing/logo.svg`, `logo.png` | private | Transparent logo (white bg stripped) — served at https://adclaw.app/logo.svg + .png |
| `website-landing/index.html` | private | Two-button CTA: DigitalOcean (blue) + Railway (purple), unified 38px height |

## Logo / icon URLs

- **Recommended for Railway template image field:** https://adclaw.app/logo.svg (170 KB SVG-wrapped transparent PNG, served from CF Pages)
- Backups:
  - https://adclaw.app/logo.png (transparent PNG 512×512, ~125 KB)
  - https://github.com/Citedy/adclaw/raw/main/logo.svg (mirror in public repo)
- **Original PNG with white background** at https://github.com/citedy/adclaw/raw/main/logo.png — leave for backwards compat, don't use as icon

## Failed-paths log (so we don't repeat)

| Tried | Result | Lesson |
|---|---|---|
| Free 512 MB plan, `full` variant | OOM at startup | Image is 4 GB, RAM use ~700-900 MB. Min Hobby. |
| Free 512 MB plan, `core` variant | Also OOM (Python+sqlite+skill registry spike >512 MB) | Even core needs 2 GB for cold start |
| `railway.json` in `deploy/` subdir | Skipped by Railpack ("not rooted at a valid path") | Must be at repo root |
| `railway.json` with no `builder` field | Defaults to `RAILPACK`, ignored `dockerfilePath`, fell into Python auto-detect | Add `"builder": "DOCKERFILE"` explicitly |
| `healthcheckTimeout: 60` | Cold start 90-180s on asia-southeast1 | Bumped to `300` |
| 2 volumes (`/app/working` + `/app/working.secret`) | Container failed to start, no runtime logs | Railway 1-volume-per-service apparently. Drop secret volume |
| Single volume `/app/working` | Container started but healthcheck timed out | Volume permissions / adclaw user write conflict suspected |
| Service bound to `8088`, default Railway PORT random | Healthcheck "service unavailable" for 5 min | Set `PORT=8088` env explicitly |
| supervisord-based entrypoint on Railway | Stdout goes to `/var/log/app.*log` files inside container, invisible to Railway logs panel | Override startCommand to run adclaw directly |
| `templateGenerate` with project-token (Project-Access-Token header) | "Bad Access" | Need account token (Bearer header) |
| `templatePublish` via API (any token) | "You have been blocked from publishing templates. Please reach out to the team." | API publish unreachable; UI publish works. Sales contact pending. |
| Variables PORT, LOG_LEVEL, ADCLAW_ENABLED_CHANNELS without descriptions | UI publish: "Missing variable details: please add descriptions or default values" | Either add description+default in UI for each, OR remove unnecessary vars from service before regenerating template |
| Description longer than 75 chars in UI | UI form validation | API has no length limit but API publish is blocked. Workaround pending unblock |
| Sync `marketplace/RAILWAY-README.md` to public Citedy/adclaw | User flagged: internal doc | Removed (commit `252160c` in public repo). Rule already in `feedback_public_repo_security.md` |
| Delete `vW-nze` template "to avoid duplicate" without asking | User had shared `vW-nze` link with Railway Sales by email; soft-delete mangled the code permanently | New rule in `feedback_no_destructive_without_confirm.md` — never destroy shared/published resources without explicit user confirmation in current message |

## Kickback model (for our marketing, not for users)

| Income | Source | Cadence |
|---|---|---|
| Template kickback 15% | Default — every user who deploys our template, on usage they incur | Continuous, $0.01 minimum payout |
| Template kickback +10% (25% total) | When we actively answer questions in our Template Queue (Railway Help Station) | Continuous |
| Referral signup bonus | When new Railway users sign up via `?referralCode=8K6-i5` (Dmitry's personal code) | Per signup |

UTM params on the deploy URL (`utm_medium=integration&utm_source=template&utm_campaign=generic`) are analytics only — no money attached.

## Open follow-ups

- [ ] **Sales unblock** — `templatePublish` via API still returns "blocked from publishing". User emailed Sales (with old `vW-nze` link, now 404 after my mistake — needs follow-up email with `/deploy/adclaw` instead).
- [ ] **Description on tile is short** — current 54-char "Multi-agent AI marketing platform with sharing memory.". When unblocked, replace via API with the 177-char version: *"AI marketing agent team — 130+ skills, multi-agent personas, 24 LLM providers, multi-channel (Telegram/Discord/Web). Deploys in 60s. Requires Hobby plan or higher (≥ 2 GB RAM)."*
- [ ] **Optional persistent volume in template** — currently template has no volume, so wizard re-runs on every redeploy. Consider documenting "Add a 25GB volume on /app/working" as a post-deploy step in template README (already in `docs/deploy/railway.md`).
- [ ] **Service ADCLAW_VARIANT switch** — current uses `1.0.2-core`. Once Railway IPv6 quirk is verified safe, switch back to `1.0.2-full` so out-of-the-box has Chromium for browser skills. Trade-off: full needs more RAM, may not fit smaller Hobby.

## Useful API recipes

```bash
TOKEN_ACCOUNT=<account token>           # Bearer
TOKEN_PROJECT=<project token>           # Project-Access-Token
PROJ=a08d221b-61ae-451c-8b2c-04c3620ad919
ENV=ccb97ac8-e1ef-4562-8362-645d955f0689
SVC=3bb47a68-10c9-411c-b002-7acaba1b5df3

# Trigger redeploy
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN_PROJECT" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { serviceInstanceDeployV2(serviceId:\\\"$SVC\\\", environmentId:\\\"$ENV\\\") }\"}"

# Get deploy status
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN_PROJECT" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"query { deployments(first:1, input:{projectId:\\\"$PROJ\\\",environmentId:\\\"$ENV\\\",serviceId:\\\"$SVC\\\"}) { edges { node { id status } } } }\"}"

# Tail logs
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN_PROJECT" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"query { deploymentLogs(deploymentId:\\\"<deploymentId>\\\", limit:200) { message timestamp } }\"}"

# Update startCommand / source / healthcheck
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN_PROJECT" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { serviceInstanceUpdate(serviceId:\\\"$SVC\\\", environmentId:\\\"$ENV\\\", input: { source: { image: \\\"nttylock/adclaw:1.0.2-core\\\" }, healthcheckTimeout: 300, sleepApplication: false }) }\"}"

# Set env var
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: $TOKEN_PROJECT" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { variableUpsert(input: { projectId:\\\"$PROJ\\\", environmentId:\\\"$ENV\\\", serviceId:\\\"$SVC\\\", name:\\\"PORT\\\", value:\\\"8088\\\" }) }\"}"

# (Account token only) regenerate template after config changes
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $TOKEN_ACCOUNT" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { templateGenerate(input: {projectId: \\\"$PROJ\\\", environmentId: \\\"$ENV\\\"}) { id code } }\"}"

# (Account token only) inspect template state
rtk proxy curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $TOKEN_ACCOUNT" \
  -H "Content-Type: application/json" \
  -d '{"query":"query { template(code: \"adclaw\") { id code name description status serializedConfig } }"}'
```
