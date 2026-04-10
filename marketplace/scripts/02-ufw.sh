#!/bin/bash
set -euo pipefail

# AdClaw 1-Click — firewall setup

echo ">>> Configuring UFW firewall..."

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 8088/tcp  # AdClaw Web UI
ufw allow 80/tcp    # HTTP (optional reverse proxy)
ufw allow 443/tcp   # HTTPS (optional reverse proxy)

ufw --force enable

echo ">>> UFW configured: SSH(22), HTTP(80), HTTPS(443), AdClaw(8088)"
