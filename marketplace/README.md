# AdClaw — DigitalOcean Marketplace 1-Click App

Build scripts for the AdClaw Droplet image on DigitalOcean Marketplace.

## Structure

```
marketplace/
├── adclaw-image.json          # Packer template
├── scripts/
│   ├── 01-adclaw.sh           # Install Docker + pull AdClaw + create systemd service
│   ├── 02-ufw.sh              # Firewall (SSH, HTTP, HTTPS, 8088)
│   ├── 90-cleanup.sh          # DO-required cleanup
│   └── 99-img-check.sh        # DO image validation (from marketplace-partners)
└── files/
    ├── etc/update-motd.d/99-one-click    # Welcome MOTD
    └── var/lib/cloud/scripts/per-instance/001_onboot  # First-boot init
```

## Build

```bash
export DIGITALOCEAN_TOKEN="your-do-api-token"
cd marketplace
packer build adclaw-image.json
```

This creates a snapshot in your DO account. Submit it via the [Vendor Portal](https://cloud.digitalocean.com/vendorportal).

## What the image includes

- Ubuntu 24.04 LTS
- Docker CE with AdClaw container (`nttylock/adclaw:latest`)
- Systemd service (`adclaw.service`) — auto-start on boot
- UFW firewall (ports 22, 80, 443, 8088)
- `adclaw-ctl` CLI helper
- Persistent Docker volumes (`adclaw-data`, `adclaw-secret`)

## User experience

1. User creates a Droplet from the Marketplace listing
2. Droplet boots, first-boot script starts AdClaw automatically
3. User opens `http://<droplet-ip>:8088` — welcome wizard appears
4. User sets their LLM API key and starts using the platform

## Update

Users run `adclaw-ctl update` to pull the latest image and restart.
