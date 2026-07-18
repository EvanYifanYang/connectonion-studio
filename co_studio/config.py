"""Paths, ports, and constants shared across the studio."""

from __future__ import annotations

import json
from pathlib import Path

STUDIO_HOST = "127.0.0.1"  # manager is loopback-only: agent ports are unauthenticated
STUDIO_PORT = 9900
AGENT_PORT_RANGE = range(8000, 8100)

STUDIO_HOME = Path.home() / ".co-studio"
SETTINGS_FILE = STUDIO_HOME / "config.json"
DEFAULT_AGENTS_DIR = STUDIO_HOME / "agents"
TRASH_DIR = STUDIO_HOME / "trash"
INDEX_LOCK = STUDIO_HOME / "index.lock"


def _read_settings() -> dict:
    """The persisted studio config (empty dict if absent/unreadable)."""
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_agents_dir(path: Path) -> None:
    """Persist the agents directory so the choice survives a restart."""
    STUDIO_HOME.mkdir(parents=True, exist_ok=True)
    data = _read_settings()
    data["agents_dir"] = str(path)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2) + "\n")


# Where agent folders live. Loaded from config.json (falls back to the default),
# and reassigned at runtime by storage.change() when the user moves it.
_saved = _read_settings().get("agents_dir")
AGENTS_DIR = Path(_saved).expanduser() if _saved else DEFAULT_AGENTS_DIR

MAIN_CO_DIR = Path.home() / ".co"
KEYS_ENV = MAIN_CO_DIR / "keys.env"

PACKAGE_DIR = Path(__file__).resolve().parent
RUNNER_PATH = PACKAGE_DIR / "runner" / "co_studio_runner.py"
TEMPLATE_PATH = PACKAGE_DIR / "templates" / "agent.py.tmpl"
FRONTEND_DIR = PACKAGE_DIR.parent / "frontend"

STDOUT_LOG_NAME = "studio-stdout.log"
PIDFILE_NAME = "studio.pid"

HEALTH_INTERVAL = 5.0  # seconds between health polls and WS status keepalives
STOP_GRACE = 5.0  # seconds between SIGTERM and SIGKILL
START_GRACE = 45.0  # seconds an agent may stay "starting" before it is "offline"
