# ConnectOnion Studio

Local test cockpit for [ConnectOnion](https://github.com/openonion/connectonion) agents. Click toolkits to
create an agent, scan its QR from the iOS app, watch live logs, and copy a one-click diagnostics bundle
straight into Claude.

## Quick start

```bash
git clone https://github.com/EvanYifanYang/connectonion-studio && cd connectonion-studio
./install.sh
.venv/bin/co-studio          # opens http://127.0.0.1:9900
```

First run only: `.venv/bin/co auth` (creates `~/.co` identity + managed model key).

## What it does

| Feature | Detail |
|---|---|
| Create agent | Form: name / model / toolkit checkboxes → identity + QR ready instantly (not started) |
| Toolkits | `utility` `web` `files` `shell` (approval-gated) `image` |
| Run | One process per agent, health-polled every 5s, states pushed over WebSocket |
| QR | Bare `0x` address SVG — scan in the iOS "Add agent" flow |
| Logs | Live stdout + framework-logger streams, per agent |
| Copy for Claude | `GET /api/agents/{slug}/diagnostics` — paste-ready markdown debug bundle |
| Delete | Moves the agent dir to `~/.co-studio/trash/` — keys are identity, never hard-deleted |

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/agents` | `{"agents":[AgentSummary]}` |
| POST | `/api/agents` | AgentDetail (body: `{name, model, toolkits}`) |
| GET | `/api/agents/{slug}` | AgentDetail |
| POST | `/api/agents/{slug}/start` · `/stop` · `/restart` | `{"state": ...}` |
| DELETE | `/api/agents/{slug}` | 204 (moved to trash) |
| GET | `/api/agents/{slug}/qr.svg` | SVG QR |
| GET | `/api/agents/{slug}/diagnostics` | markdown bundle |
| GET | `/api/setup/status` | doctor checks |
| WS | `/ws/status` | status frames (each change + every 5s) |
| WS | `/ws/agents/{slug}/logs` | `{"source":"stdout"\|"logger","line":...}` |

## Layout

```
~/.co-studio/agents/<slug>/   meta.json · agent.py · .env · .co/ · studio-stdout.log
~/.co-studio/trash/           deleted agents (timestamped)
```

- Agent ports: `8000–8099`, allocated by socket probe (busy ports skipped, re-probed at start).
- `agent.py` is standalone — eject it anywhere and `python agent.py` still works (the announce
  IP-trim patch is inlined).

## Security

- The manager binds **127.0.0.1:9900 only**.
- Agent ports are **unauthenticated** and exposed on your LAN by `host()` — that is how the phone
  connects. Don't run on hostile networks.

## Dev mode

| Env | Effect |
|---|---|
| `CONNECTONION_PATH=~/repo/connectonion ./install.sh` | Use a local framework checkout instead of git |
| `PYTHON=python3.12 ./install.sh` | Pick the interpreter |

`connectonion` is always installed from git source, never PyPI (0.4.x lacks `host()`).
