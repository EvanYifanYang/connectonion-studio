"""Dangerous capability: local file creation and editing with approval support."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def tools(*, work_dir: str | Path, runtime_dir: str | Path | None = None) -> list[Any]:
    """Workspace-confined file tools with read-before-edit and stale-read protection."""
    from co_studio.sandbox import SandboxedFileTools

    return [SandboxedFileTools(work_dir)]


def plugins() -> list[Any]:
    """Prefer file tools over bash and require approval for write/edit operations."""
    from connectonion import useful_plugins

    return [useful_plugins.prefer_write_tool, useful_plugins.tool_approval, useful_plugins.runtime_input]
