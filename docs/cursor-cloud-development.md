# Cursor Cloud development

This document mirrors the **Cursor Cloud specific instructions** section in the repo-root `AGENTS.md` (root `AGENTS.md` is gitignored so each developer can keep local agent notes).

## Product overview

AdClaw is a single Python FastAPI app (`python3 -m adclaw app`, default `http://127.0.0.1:8088`) with a prebuilt React console under `src/adclaw/console/`. SQLite and MCP run in-process; there is no separate database container in `docker-compose.yml`.

## Commands (use `python3`, not `python`)

| Task | Command |
|------|---------|
| Install backend + dev tools | `python3 -m pip install -e ".[dev]"` |
| Install console deps | `cd console && npm ci` |
| Init working dir (non-interactive) | `python3 -m adclaw init --defaults --accept-security` |
| Run server (dev) | `python3 -m adclaw app --host 127.0.0.1 --port 8088` |
| Run server (reload) | `python3 -m adclaw app --reload` |
| Console hot reload (split dev) | `cd console && npm run dev` (Vite `:5173`, proxies `/api` → `:8088`) |
| Tests | `python3 -m pytest` (add `-m "not slow"` to skip slow tests) |
| Frontend format (CI) | `cd console && npm run format:check` |
| Frontend lint | `cd console && npm run lint` |
| PR quality gate | `pre-commit run --all-files` (after `pre-commit install`) |

See `CONTRIBUTING.md` for the full contributor workflow.

## Running the server in Cloud Agent VMs

Use **tmux** for long-lived `adclaw app` processes:

```bash
SESSION_NAME="adclaw-app"
tmux -f /exec-daemon/tmux.portal.conf has-session -t "=$SESSION_NAME" 2>/dev/null \
  || tmux -f /exec-daemon/tmux.portal.conf new-session -d -s "$SESSION_NAME" -c "/workspace" -- bash -l
tmux -f /exec-daemon/tmux.portal.conf send-keys -t "$SESSION_NAME:0.0" \
  'cd /workspace && python3 -m adclaw app --host 127.0.0.1 --port 8088' C-m
```

Health check: `curl -sf http://127.0.0.1:8088/api/diagnostics/health`

Working directory after `adclaw init`: `~/.adclaw`.

## Tests: what needs a running server

- Default `pytest` uses mocks and in-memory SQLite.
- `tests/test_coordinator_real.py` expects AdClaw on `:8088`.
- Live LLM tests need provider API keys; see `.env.example`.

## Optional extras

Channel extras: `pip install adclaw[discord]`, `adclaw[browser]` (+ `playwright install chromium`).

## Rebuilding the console

After editing `console/`, run `cd console && npm run build` before commit.
