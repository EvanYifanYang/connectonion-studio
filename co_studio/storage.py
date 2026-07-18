"""Change where agents are stored, migrating existing agent folders along with it.

An agent's identity (Ed25519 keys), QR, and logs all live inside its own folder
under the agents directory. So moving the location must MOVE those folders — not
just point at a new empty one, which would orphan every existing agent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import config, registry
from .supervisor import SUPERVISOR

_RUNNING = ("starting", "online", "offline", "crashed")


def current() -> str:
    """The agents directory in effect right now."""
    return str(config.AGENTS_DIR)


def pick_folder() -> str | None:
    """Pop the native macOS folder chooser; return the POSIX path (None if cancelled).

    Runs on the user's own machine (the studio is loopback-only), so the OS dialog
    is theirs — no path is ever typed or exposed to the browser.
    """
    script = 'POSIX path of (choose folder with prompt "Choose a folder for your agents")'
    try:
        done = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=180
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = done.stdout.strip()
    return path or None  # non-zero exit == user cancelled → empty stdout


def _validate(old: Path, new: Path) -> Path:
    """Resolve and sanity-check the requested new location."""
    raw = Path(new).expanduser()
    if not raw.is_absolute():
        raise ValueError("Please give an absolute path.")
    new = raw.resolve()
    if new == old:
        raise ValueError("That is already the current location.")
    if new.is_relative_to(old) or old.is_relative_to(new):
        raise ValueError("The new location can't be inside the current one (or vice-versa).")
    if not new.parent.is_dir():
        raise ValueError(f"The parent folder does not exist: {new.parent}")
    return new


async def change(new_raw: str) -> dict:
    """Stop running agents, move their folders to `new_raw`, and switch over."""
    old = config.AGENTS_DIR.resolve()
    new = _validate(old, new_raw)

    try:
        new.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"Can't create {new}: {exc}") from exc
    if not os.access(new, os.W_OK):
        raise ValueError(f"That folder isn't writable: {new}")

    metas = registry.load_all()
    for meta in metas:  # never overwrite an existing folder at the destination
        if (new / meta.slug).exists():
            raise ValueError(f"'{meta.slug}' already exists at the new location.")

    # subprocesses hold the old paths (cwd + co_dir), so they must stop before the move
    for meta in metas:
        if SUPERVISOR.state_of(meta.slug) in _RUNNING:
            await SUPERVISOR.stop(meta.slug)

    moved = 0
    if old.is_dir():
        for meta in metas:
            src = old / meta.slug
            if src.is_dir():
                shutil.move(str(src), str(new / meta.slug))
                moved += 1

    config.save_agents_dir(new)
    config.AGENTS_DIR = new
    return {"agents_dir": str(new), "moved": moved}
