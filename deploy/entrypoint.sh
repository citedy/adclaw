#!/bin/sh
# Substitute ADCLAW_PORT in supervisord template and start supervisord.
# Default port 8088; override at runtime with -e ADCLAW_PORT=3000.
set -e
export ADCLAW_PORT="${ADCLAW_PORT:-8088}"

# Ensure config.json exists (first run only — don't overwrite user config)
CONFIG="${ADCLAW_WORKING_DIR:-/app/working}/config.json"
if [ ! -f "$CONFIG" ] || [ ! -s "$CONFIG" ]; then
  echo "entrypoint: No config.json found, generating default..."
  adclaw init --defaults --accept-security 2>/dev/null || true
fi

# Migrate config.json — apply new defaults to existing config without overwriting user data
python3 -c "
import json, os, sys
cfg_path = os.environ.get('ADCLAW_WORKING_DIR', '/app/working') + '/config.json'
if not os.path.isfile(cfg_path):
    sys.exit(0)
with open(cfg_path) as f:
    cfg = json.load(f)
changed = False
# Force correct defaults that should never be True in production
if cfg.get('show_tool_details') is not False:
    cfg['show_tool_details'] = False
    changed = True
# Ensure filter_tool_messages=True on all channels
for ch_name, ch_cfg in cfg.get('channels', {}).items():
    if isinstance(ch_cfg, dict) and ch_cfg.get('filter_tool_messages') is not True:
        ch_cfg['filter_tool_messages'] = True
        changed = True
if changed:
    with open(cfg_path, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print('entrypoint: config.json migrated (applied new defaults)')
else:
    print('entrypoint: config.json OK (no migration needed)')
" 2>/dev/null || true

# Enable Citedy MCP client if API key is provided at runtime
if [ -n "$CITEDY_API_KEY" ]; then
  CONFIG="${ADCLAW_WORKING_DIR:-/app/working}/config.json"
  if [ -f "$CONFIG" ]; then
    python3 -c "
import json, os
cfg_path = os.environ.get('ADCLAW_WORKING_DIR', '/app/working') + '/config.json'
with open(cfg_path) as f:
    cfg = json.load(f)
mcp = cfg.setdefault('mcp', {}).setdefault('clients', {})
key = os.environ['CITEDY_API_KEY']
mcp['citedy'] = {
    'name': 'citedy_mcp',
    'description': 'Citedy SEO & Marketing Tools (59 tools)',
    'enabled': True,
    'transport': 'streamable_http',
    'url': 'https://mcp.citedy.com/mcp',
    'headers': {'Authorization': f'Bearer {key}', 'Accept': 'application/json, text/event-stream'},
    'env': {'CITEDY_API_KEY': key},
}
with open(cfg_path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('entrypoint: Citedy MCP client enabled')
" 2>/dev/null || true
  fi
fi

# Enable Exa search MCP if API key is provided at runtime
if [ -n "$EXA_API_KEY" ]; then
  CONFIG="${ADCLAW_WORKING_DIR:-/app/working}/config.json"
  if [ -f "$CONFIG" ]; then
    python3 -c "
import json, os
cfg_path = os.environ.get('ADCLAW_WORKING_DIR', '/app/working') + '/config.json'
with open(cfg_path) as f:
    cfg = json.load(f)
mcp = cfg.setdefault('mcp', {}).setdefault('clients', {})
key = os.environ['EXA_API_KEY']
mcp['exa'] = {
    'name': 'exa_mcp',
    'description': 'Exa AI search: web, code, people, companies',
    'enabled': True,
    'command': 'npx',
    'args': ['-y', 'exa-mcp-server'],
    'env': {'EXA_API_KEY': key},
}
with open(cfg_path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('entrypoint: Exa MCP client enabled')
" 2>/dev/null || true
  fi
fi

# Enable Telegram channel if bot token is provided at runtime
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
  CONFIG="${ADCLAW_WORKING_DIR:-/app/working}/config.json"
  if [ -f "$CONFIG" ]; then
    python3 -c "
import json, os
cfg_path = os.environ.get('ADCLAW_WORKING_DIR', '/app/working') + '/config.json'
with open(cfg_path) as f:
    cfg = json.load(f)
tg = cfg.setdefault('channels', {}).setdefault('telegram', {})
tg['enabled'] = True
tg['bot_token'] = os.environ['TELEGRAM_BOT_TOKEN']
with open(cfg_path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('entrypoint: Telegram channel enabled')
" 2>/dev/null || true
  fi
fi

# Sync new built-in skills to active_skills (non-destructive: skip existing)
python3 -c "
from adclaw.agents.skills_manager import sync_skills_to_working_dir
synced, skipped = sync_skills_to_working_dir(skill_names=None, force=False)
if synced:
    print(f'entrypoint: synced {synced} new skill(s) to active_skills')
else:
    print(f'entrypoint: all skills up to date ({skipped} existing)')
" 2>/dev/null || true

# Ensure working dirs are owned by adclaw user (entrypoint runs as root)
mkdir -p /app/logs 2>/dev/null || true
chown -R adclaw:adclaw "${ADCLAW_WORKING_DIR:-/app/working}" "${ADCLAW_WORKING_DIR:-/app/working}.secret" /app/logs 2>/dev/null || true

# Generate supervisord.conf from templates based on ADCLAW_VARIANT.
# core → base template only (supervisord + app).
# browser/full → base + browser template (adds dbus, xvfb, xfce4, pinchtab).
ADCLAW_VARIANT="${ADCLAW_VARIANT:-full}"
SUPERVISORD_CONF="/etc/supervisor/conf.d/supervisord.conf"
envsubst '${ADCLAW_PORT}' \
  < /etc/supervisor/conf.d/supervisord.conf.template \
  > "$SUPERVISORD_CONF"
if [ "$ADCLAW_VARIANT" != "core" ] && [ -f /etc/supervisor/conf.d/supervisord.browser.conf.template ]; then
  cat /etc/supervisor/conf.d/supervisord.browser.conf.template >> "$SUPERVISORD_CONF"
  echo "entrypoint: supervisord configured with browser programs (variant=${ADCLAW_VARIANT})"
else
  echo "entrypoint: supervisord configured without browser (variant=${ADCLAW_VARIANT})"
fi
exec /usr/bin/supervisord -c "$SUPERVISORD_CONF"
