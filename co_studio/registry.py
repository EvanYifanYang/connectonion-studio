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
    capabilities: list[str]
    created_at: str
    trust: str = "open"   # who may connect: open | careful | strict (default keeps old agents valid)
    preset: str = "custom"   # custom | co-ai (default keeps old agents valid)
    invite_code: str | None = None
    # None means agents/<slug>/workspace, so the default follows storage-folder moves.
    work_dir: str | None = None

    @property
    def toolkits(self) -> list[str]:
        """Legacy read alias for integrations built before capabilities were named."""
        return self.capabilities


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


def _write_metadata(path: Path, data: dict[str, object]) -> None:
    """Atomically write a complete metadata mapping."""
    tmp = path.with_name("meta.json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def save(meta: AgentMeta) -> None:
    """Write the current schema plus the legacy capability alias atomically.

    ``toolkits`` keeps an older installed Studio able to open the registry after a
    newer version has created or modified an agent. New code treats ``capabilities``
    as authoritative and always re-synchronises the alias on save.
    """
    path = agent_dir(meta.slug) / "meta.json"
    data: dict[str, object] = dataclasses.asdict(meta)
    data["toolkits"] = list(meta.capabilities)
    _write_metadata(path, data)


def migrate_capability_aliases() -> int:
    """Make every readable metadata file safe for both old and new Studio versions.

    Old-only files gain ``capabilities``; new-only files gain ``toolkits``. If both
    exist but disagree, the current ``capabilities`` value wins. Unknown/new fields
    are preserved because the raw JSON mapping is updated rather than re-serialising
    through ``AgentMeta``.
    """
    migrated = 0
    with locked():
        for directory in sorted(config.AGENTS_DIR.iterdir()):
            path = directory / "meta.json"
            if not directory.is_dir() or not path.exists():
                continue
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            capabilities = data.get("capabilities")
            if capabilities is None:
                capabilities = data.get("toolkits")
            if not isinstance(capabilities, list):
                continue
            capabilities = list(capabilities)
            if data.get("capabilities") == capabilities and data.get("toolkits") == capabilities:
                continue
            data["capabilities"] = capabilities
            data["toolkits"] = capabilities
            _write_metadata(path, data)
            migrated += 1
    return migrated


def load(slug: str) -> AgentMeta | None:
    """Read one agent's meta.json, or None if it does not exist or is unreadable."""
    path = agent_dir(slug) / "meta.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if "capabilities" not in data and "toolkits" in data:
        data["capabilities"] = data["toolkits"]
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
