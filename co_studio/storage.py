"""Change where agents are stored, migrating existing agent folders along with it.

An agent's identity (Ed25519 keys), QR, and logs all live inside its own folder
under the agents directory. So moving the location must MOVE those folders — not
just point at a new empty one, which would orphan every existing agent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

from . import config, registry
from .supervisor import SUPERVISOR

_RUNNING = ("starting", "online", "offline", "crashed")


def current() -> str:
    """The agents directory in effect right now."""
    return str(config.AGENTS_DIR)


def _picker_command(prompt: str = "Choose a folder for your agents") -> list[str] | None:
    """The native "choose folder" command for this OS, or None if none is available.

    Runs on the user's own machine (the studio is loopback-only), so the OS dialog is
    theirs — no path is ever typed or exposed to the browser. When None (e.g. headless
    Linux without zenity), the UI still has its typed-path field, so the feature stays
    usable everywhere.
    """
    if sys.platform == "darwin":
        return ["osascript", "-e",
                f'POSIX path of (choose folder with prompt "{prompt}")']
    if os.name == "nt":
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            f"$d.Description = '{prompt}';"
            "if ($d.ShowDialog() -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }"
        )
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]
    if shutil.which("zenity"):  # most Linux desktops
        return ["zenity", "--file-selection", "--directory",
                f"--title={prompt}"]
    return None


def pick_folder(prompt: str = "Choose a folder for your agents") -> str | None:
    """Pop the native folder chooser for this OS; return the path (None if cancelled/unavailable)."""
    command = _picker_command(prompt)
    if command is None:
        return None
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    path = done.stdout.strip()
    return path or None  # non-zero exit == user cancelled → empty stdout


def reveal(path: Path) -> bool:
    """Open a folder in the OS file browser (Finder / Explorer / xdg). Local-only by design —
    the studio is loopback, so this launches on the user's own machine. False if unsupported."""
    target = str(Path(path))
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", target], check=False)
        elif os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]  # Windows-only
        elif shutil.which("xdg-open"):
            subprocess.run(["xdg-open", target], check=False)
        else:
            return False
    except (OSError, subprocess.SubprocessError):
        return False
    return True


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
    for meta in metas:  # fast pre-check before we stop anything (authoritative check is below)
        if (new / meta.slug).exists():
            raise ValueError(f"'{meta.slug}' already exists at the new location.")

    # subprocesses hold the old paths (cwd + co_dir), so they must stop before the move
    for meta in metas:
        if SUPERVISOR.state_of(meta.slug) in _RUNNING:
            await SUPERVISOR.stop(meta.slug)

    # Serialise the move + switch against create/save/port-allocation (all of which take
    # this lock), and enumerate the LIVE folders — not a stale meta snapshot — so an agent
    # created during the stop phase, or one with a corrupt meta.json, is never stranded.
    with registry.locked():
        folders = [p for p in sorted(old.iterdir()) if p.is_dir()] if old.is_dir() else []
        for src in folders:  # never overwrite an existing folder at the destination
            if (new / src.name).exists():
                raise ValueError(f"'{src.name}' already exists at the new location.")

        done: list[str] = []
        try:
            for src in folders:
                shutil.move(str(src), str(new / src.name))
                done.append(src.name)
        except OSError as exc:  # roll back partial moves so a failed change() is a no-op
            for name in reversed(done):
                with suppress(OSError):
                    shutil.move(str(new / name), str(old / name))
            raise ValueError(f"Migration failed and was rolled back: {exc}") from exc

        config.save_agents_dir(new)
        config.AGENTS_DIR = new
    return {"agents_dir": str(new), "moved": len(folders)}
