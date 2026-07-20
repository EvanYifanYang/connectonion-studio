"""Per-agent working directories, separate from identity and Studio state."""

from __future__ import annotations

import os
from pathlib import Path

from . import config, registry
from .registry import AgentMeta


def default_work_dir(slug: str) -> Path:
    """The private workspace that moves together with the agent directory."""
    return registry.agent_dir(slug) / config.WORKSPACE_DIR_NAME


def effective_work_dir(meta: AgentMeta) -> Path:
    """Resolve a stored external workspace or the agent's movable private default."""
    raw = Path(meta.work_dir).expanduser() if meta.work_dir else default_work_dir(meta.slug)
    return raw.resolve()


def prepare(
    slug: str,
    requested: str | None,
    *,
    require_write: bool,
) -> tuple[Path, str | None]:
    """Validate/create a workspace and return its path plus metadata representation.

    A blank request uses ``agents/<slug>/workspace`` and is stored as ``None`` so it
    continues to follow the agent if the Studio storage folder is moved. Explicit
    folders are stored as resolved absolute paths and must already exist; Studio never
    creates an arbitrary path typed by a browser client.
    """
    if requested is None or not requested.strip():
        path = default_work_dir(slug)
        path.mkdir(parents=True, exist_ok=True)
        stored = None
    else:
        raw = Path(requested.strip()).expanduser()
        if not raw.is_absolute():
            raise ValueError("workspace must be an absolute folder path")
        try:
            path = raw.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"workspace does not exist: {raw}") from exc
        if not path.is_dir():
            raise ValueError(f"workspace is not a folder: {path}")
        stored = str(path)

    if not os.access(path, os.R_OK | os.X_OK):
        raise ValueError(f"workspace is not readable: {path}")
    if require_write and not os.access(path, os.W_OK | os.X_OK):
        raise ValueError(f"workspace is not writable: {path}")
    return path, stored


def ensure(meta: AgentMeta, *, require_write: bool = False) -> Path:
    """Prepare an existing agent's workspace, failing clearly if it disappeared."""
    path, _stored = prepare(meta.slug, meta.work_dir, require_write=require_write)
    return path
