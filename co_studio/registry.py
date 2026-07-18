"""Persistence for agent metadata under ~/.co-studio/agents/<slug>/meta.json."""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from filelock import FileLock

from . import config


@dataclass
class AgentMeta:
    """Static per-agent record stored in meta.json (runtime state lives in the supervisor)."""

    slug: str
    name: str
    address: str
    port: int
    model: str
    toolkits: list[str]
    created_at: str
    trust: str = "open"   # who may connect: open | careful | strict (default keeps old agents valid)


def ensure_dirs() -> None:
    """Create the studio home and agents directories."""
    config.AGENTS_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def locked() -> Iterator[None]:
    """Exclusive cross-platform lock serialising registry mutations across threads/processes.

    filelock uses fcntl.flock on POSIX (same primitive as before) and msvcrt on Windows,
    so this works identically on macOS/Linux and no longer crashes on `import fcntl`.
    A fresh FileLock per call gives plain mutual exclusion (no reentrancy), matching the
    old flock behaviour; the default timeout=-1 blocks until the lock is free.
    """
    ensure_dirs()
    with FileLock(str(config.INDEX_LOCK)):
        yield


def agent_dir(slug: str) -> Path:
    """Directory holding one agent's meta.json, agent.py, .env, .co/, and logs."""
    return config.AGENTS_DIR / slug


def save(meta: AgentMeta) -> None:
    """Write meta.json atomically (temp file + rename) so a crash never leaves it half-written."""
    path = agent_dir(meta.slug) / "meta.json"
    tmp = path.with_name("meta.json.tmp")
    tmp.write_text(json.dumps(dataclasses.asdict(meta), indent=2) + "\n")
    os.replace(tmp, path)


def load(slug: str) -> AgentMeta | None:
    """Read one agent's meta.json, or None if it does not exist or is unreadable."""
    path = agent_dir(slug) / "meta.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    known = {f.name for f in dataclasses.fields(AgentMeta)}
    return AgentMeta(**{k: v for k, v in data.items() if k in known})


def load_all() -> list[AgentMeta]:
    """All registered agents, oldest first."""
    if not config.AGENTS_DIR.is_dir():
        return []
    metas = [load(p.name) for p in sorted(config.AGENTS_DIR.iterdir()) if p.is_dir()]
    return sorted((m for m in metas if m is not None), key=lambda m: m.created_at)


def delete(slug: str) -> None:
    """Permanently remove the agent directory (identity, keys, logs — all of it)."""
    shutil.rmtree(agent_dir(slug), ignore_errors=True)
