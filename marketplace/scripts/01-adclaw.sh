#!/bin/bash
set -euo pipefail

# AdClaw 1-Click Droplet — install script
# Runs during Packer image build (NOT at first boot)

echo ">>> Installing AdClaw..."

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Pre-pull the AdClaw image so first boot is fast
docker pull nttylock/adclaw:latest

# Create persistent volumes
docker volume create adclaw-data
docker volume create adclaw-secret

# Create systemd service for AdClaw
cat > /etc/systemd/system/adclaw.service <<'EOF'
[Unit]
Description=AdClaw AI Marketing Agent
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStartPre=-/usr/bin/docker rm -f adclaw
ExecStart=/usr/bin/docker run --rm --name adclaw \
  -p 8088:8088 \
  -v adclaw-data:/app/working \
  -v adclaw-secret:/app/working.secret \
  --env-file /etc/adclaw/env \
  nttylock/adclaw:latest
ExecStop=/usr/bin/docker stop adclaw

[Install]
WantedBy=multi-user.target
EOF

# Create default env file
mkdir -p /etc/adclaw
cat > /etc/adclaw/env <<'EOF'
ADCLAW_ENABLED_CHANNELS=console,telegram
LOG_LEVEL=INFO
# Uncomment and set your Telegram bot token:
# TELEGRAM_BOT_TOKEN=
# Optional: Citedy API key for MCP tools
# CITEDY_API_KEY=
EOF

# Enable service (will start on first boot)
systemctl daemon-reload
systemctl enable adclaw.service

# Create adclaw helper command
cat > /usr/local/bin/adclaw-ctl <<'SCRIPT'
#!/bin/bash
case "${1:-help}" in
  status)  systemctl status adclaw ;;
  logs)    docker logs -f adclaw ;;
  restart) systemctl restart adclaw ;;
  stop)    systemctl stop adclaw ;;
  start)   systemctl start adclaw ;;
  config)  nano /etc/adclaw/env && echo "Run 'adclaw-ctl restart' to apply changes." ;;
  update)
    docker pull nttylock/adclaw:latest
    systemctl restart adclaw
    echo "AdClaw updated to latest version."
    ;;
  help|*)
    echo "Usage: adclaw-ctl {status|logs|restart|stop|start|config|update}"
    echo ""
    echo "  status   — show service status"
    echo "  logs     — stream container logs"
    echo "  restart  — restart AdClaw"
    echo "  stop     — stop AdClaw"
    echo "  start    — start AdClaw"
    echo "  config   — edit environment config"
    echo "  update   — pull latest image and restart"
    ;;
esac
SCRIPT
chmod +x /usr/local/bin/adclaw-ctl

echo ">>> AdClaw installed successfully."
