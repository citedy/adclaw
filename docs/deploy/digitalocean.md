# Deploying AdClaw on DigitalOcean

This guide covers the user-facing DigitalOcean path for AdClaw.

## One-click deploy

1. Open the DigitalOcean Marketplace listing for AdClaw.
2. Create a Droplet from the **AdClaw** 1-click image.
3. Pick at least:
   - `1 vCPU`
   - `2 GB RAM`
   - `25 GB disk`
4. Wait for the Droplet to finish first boot.

## First login

After the Droplet is ready, open:

```text
http://<your-droplet-ip>:8088
```

The AdClaw welcome wizard will appear.

## First-run setup

In the welcome wizard:

1. choose your LLM provider
2. paste the provider API key
3. optionally connect Telegram or other channels
4. start using the web console

## SSH management

You can also manage the Droplet over SSH:

```bash
ssh root@<your-droplet-ip>
```

Available helper commands:

```bash
adclaw-ctl status
adclaw-ctl logs
adclaw-ctl config
adclaw-ctl update
adclaw-ctl restart
```

## Configuration

- Main environment file: `/etc/adclaw/env`
- AdClaw web UI: `http://<your-droplet-ip>:8088`

To connect Telegram later:

1. add `TELEGRAM_BOT_TOKEN` to `/etc/adclaw/env`
2. run `adclaw-ctl restart`

## Updates

To pull the latest shipped image and restart AdClaw:

```bash
adclaw-ctl update
```

## What this deploy includes

- Ubuntu 24.04 LTS
- Docker-based AdClaw runtime
- `adclaw-ctl` helper
- firewall defaults for SSH, HTTP, HTTPS, and port `8088`

## Related docs

- [`docs/getting-started.md`](../getting-started.md)
- [`docs/personas.md`](../personas.md)
- [`marketplace/README.md`](../../marketplace/README.md)
