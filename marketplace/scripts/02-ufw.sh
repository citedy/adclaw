#!/bin/bash
set -euo pipefail

# AdClaw 1-Click — firewall setup
# Includes Docker+UFW compatibility fix for port forwarding

echo ">>> Configuring UFW firewall..."

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 8088/tcp  # AdClaw Web UI
ufw allow 80/tcp    # HTTP (optional reverse proxy)
ufw allow 443/tcp   # HTTPS (optional reverse proxy)

# Fix Docker+UFW conflict: Docker bypasses UFW by default.
# This routes Docker traffic through UFW's user-forward chain.
cat >> /etc/ufw/after.rules << 'RULES'

# BEGIN UFW AND DOCKER
*filter
:ufw-user-forward - [0:0]
:DOCKER-USER - [0:0]
-A DOCKER-USER -j ufw-user-forward
-A DOCKER-USER -j RETURN
COMMIT
RULES

ufw --force enable

# Allow routed traffic to Docker port 8088
ufw route allow proto tcp from any to any port 8088

echo ">>> UFW configured: SSH(22), HTTP(80), HTTPS(443), AdClaw(8088)"
