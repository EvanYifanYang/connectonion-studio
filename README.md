<div align="center">

<img src="https://raw.githubusercontent.com/EvanYifanYang/connectonion-studio/main/co_studio/frontend/assets/onion/onion_full.png" width="96" alt="" />
<br />
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/EvanYifanYang/connectonion-studio/main/assets/wordmark-dark.png">
  <img src="https://raw.githubusercontent.com/EvanYifanYang/connectonion-studio/main/assets/wordmark-light.png" width="360" alt="ConnectOnion Studio" />
</picture>

**A local test cockpit for [ConnectOnion](https://github.com/openonion/connectonion) agents.**

Click toolkits to build an agent · scan its QR from the iOS app · watch live logs

[![PyPI](https://img.shields.io/pypi/v/connectonion-studio.svg)](https://pypi.org/project/connectonion-studio/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)](#requirements)

</div>

---

## Install

```bash
pipx install connectonion-studio      # or: pip install connectonion-studio
co-studio                             # opens http://127.0.0.1:9900
```

That's it. The first launch **auto-creates your identity and activates your managed model key** (needs internet — it's your own key, one per user). Offline on first run? Just run `co auth` once you're back online.

## Desktop app (macOS)

A native macOS app (SwiftUI + WKWebView) lives in [`macos/`](macos/) — the same cockpit in a real window with the traffic-light chrome and app icon. Build and run it from Xcode (`macos/ConnectOnionStudio/`); a signed `.dmg` for one-click install is on the way.

## What it does

|  |  |
|---|---|
| 🧩 **Create** | Form: name · model · toolkit checkboxes → identity + QR ready instantly |
| ▶️ **Run** | One process per agent, health-polled every 5 s, live state over WebSocket |
| 📱 **QR** | Encodes `connectonion://add?address&name&endpoint` — one scan fills all three iOS "Add agent" fields (direct LAN endpoint, bypasses the relay) |
| 📜 **Logs** | Master–detail cockpit: per-agent live console (this run only), stat tiles, follow / errors-only, reveal-in-Finder |
| 🩺 **Copy for Claude** | Paste-ready markdown diagnostics bundle, one click |
| 🗑️ **Delete** | Two-step confirm, then a permanent delete — identity, keys, and logs are removed for good |

**Toolkits:** `utility` · `web` · `files` · `shell` (approval-gated) · `image`

## Requirements

**Python 3.11+** · macOS, Linux, or Windows (WSL recommended)

<details>
<summary><b>API reference</b></summary>

<br>

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/agents` | `{"agents": [AgentSummary]}` |
| `POST` | `/api/agents` | AgentDetail — body `{name, model, toolkits, trust}` |
| `GET` | `/api/agents/{slug}` | AgentDetail |
| `POST` | `/api/agents/{slug}/start` · `/stop` · `/restart` | `{"state": …}` |
| `POST` | `/api/agents/{slug}/rename` | AgentSummary — body `{name}` |
| `DELETE` | `/api/agents/{slug}` | `204` (stops the agent, then permanently deletes it) |
| `GET` | `/api/agents/{slug}/qr.svg` | SVG QR of the `connectonion://add` deep link (address · name · endpoint) |
| `POST` | `/api/agents/{slug}/reveal-logs` | Opens the agent's `runs/` folder in the OS file browser (local) |
| `GET` | `/api/agents/{slug}/diagnostics` | Markdown bundle |
| `GET` | `/api/setup/status` | Doctor checks |
| `GET` | `/api/setup/update` | PyPI update check — `{current, latest, update_available}` |
| `WS` | `/ws/status` | Status frames (each change + every 5 s) |
| `WS` | `/ws/agents/{slug}/logs` | `{"source": "stdout", "line": …}` — the current run, from its first line |

</details>

<details>
<summary><b>Storage &amp; internals</b></summary>

<br>

```
~/.co-studio/agents/<slug>/   meta.json · agent.py · .env · .co/ · runs/<timestamp>.log
```

- One stdout log **per run** under `runs/`; the live console (and diagnostics) read only the current run.
- Agent ports `8000–8099`, allocated by socket probe (busy ports skipped, re-probed at start).
- `agent.py` is standalone — eject it anywhere and `python agent.py` still works (the announce IP-trim patch is inlined).

</details>

<details>
<summary><b>Development (from source)</b></summary>

<br>

```bash
git clone https://github.com/EvanYifanYang/connectonion-studio && cd connectonion-studio
./install.sh
.venv/bin/co-studio
```

| Env | Effect |
|---|---|
| `CONNECTONION_PATH=~/repo/connectonion ./install.sh` | Install the framework from a local checkout instead of PyPI |
| `PYTHON=python3.12 ./install.sh` | Pick the interpreter |

</details>

## Security

- The manager binds **`127.0.0.1:9900` only**.
- Agent ports are **unauthenticated** and exposed on your LAN by `host()` — that is how the phone connects. **Don't run on hostile networks.**
