# AdClaw Deployment Protocol

## Architecture

```
nttylock/AdClaw (private/dev) → Citedy/adclaw (public) → Docker Hub → claude-worker
```

1. **Dev repo** (`nttylock/AdClaw`): all development happens here
2. **Public repo** (`Citedy/adclaw`): synced from dev via rsync (no `.git`, `node_modules`, `.env`)
3. **Docker Hub** (`nttylock/adclaw:latest`): built by GitHub Actions on `Citedy/adclaw`
4. **claude-worker** (`188.166.47.214`): production server, pulls from Docker Hub

## Step-by-Step Deploy

### 1. Make changes in dev repo

```bash
cd /root/AdClaw
# ... edit code ...
```

### 2. Build console (if frontend changed)

```bash
cd /root/AdClaw/console
npm run build
```

Build output goes to `src/adclaw/console/` (committed to repo, bundled into Docker image).

### 3. Commit and push to dev repo

```bash
cd /root/AdClaw
git add -A
git commit -m "description of changes"
git push origin main
```

### 4. Sync to public repo

```bash
rsync -a --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.env' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.mypy_cache' \
  /root/AdClaw/ /tmp/adclaw-public/
```

### 5. Commit and push public repo

```bash
cd /tmp/adclaw-public
git add -A
git commit -m "sync: description of changes"
git push origin main
```

### 6. Trigger Docker build

```bash
gh workflow run docker-release.yml --repo Citedy/adclaw -f version=latest
```

Wait for the workflow to complete (~3-5 min):
```bash
gh run list --repo Citedy/adclaw --limit 1
```

### 7. Deploy on claude-worker

```bash
docker pull nttylock/adclaw:latest
docker rm -f adclaw
docker run -d --name adclaw --restart unless-stopped -p 8088:8088 \
  -v copaw-data:/app/working \
  -v copaw-secret:/app/working.secret \
  -e ADCLAW_ENABLED_CHANNELS=discord,dingtalk,feishu,qq,console,telegram \
  -e LOG_LEVEL=DEBUG \
  nttylock/adclaw:latest
```

### 8. Verify

```bash
# Check container is running
docker ps | grep adclaw

# Check logs for errors
docker logs adclaw --tail 50

# Check UI
curl -s -o /dev/null -w "%{http_code}" http://188.166.47.214:8088/
```

## Pre-Deploy Checklist

- [ ] `npm run build` passes in `console/`
- [ ] No secrets in committed files (`.env`, API keys, tokens)
- [ ] Build artifacts in `src/adclaw/console/` are up to date
- [ ] Changes tested locally if possible

## Key Rules

1. **Never build Docker locally** — always use GitHub Actions via `Citedy/adclaw`
2. **Always rebuild console** before deploying frontend changes (`npm run build`)
3. **Always `docker rm -f adclaw`** before `docker run` — port 8088 conflict otherwise
4. **Always mount BOTH volumes**: `copaw-data` AND `copaw-secret` — without `copaw-secret`, API keys are lost on every redeploy
5. **Container name is always `adclaw`** — never `copaw`
6. **Never run `adclaw init` manually** — entrypoint handles it automatically

## Troubleshooting

### Docker build fails
- Check `npm run build` locally first
- Common: missing/wrong imports from `@agentscope-ai/design`
- Fix in source → rebuild console → commit → redeploy

### Container won't start
```bash
docker logs adclaw
```
- Port conflict: `docker rm -f adclaw` first
- Volume issues: verify both volumes exist (`docker volume ls | grep copaw`)

### API keys missing after redeploy
- `copaw-secret` volume not mounted — check `docker run` command
- Keys live in `/app/working.secret/providers.json` (NOT `/app/working/.secret/`)

### UI not loading
- Check container: `docker ps | grep adclaw`
- Check port: `curl http://188.166.47.214:8088/`
- Check logs: `docker logs adclaw --tail 100`
