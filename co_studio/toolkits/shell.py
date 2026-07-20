"""Dangerous capability: shell execution gated by the unified approval protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def tools(*, work_dir: str | Path, runtime_dir: str | Path | None = None) -> list[Any]:
    """A bash tool confined to the Agent workspace by the host OS."""
    from co_studio.sandbox import SandboxedShell

    runtime = Path(runtime_dir or Path(work_dir) / ".co-studio-runtime")
    return [SandboxedShell(work_dir, runtime)]


def plugins() -> list[Any]:
    """Use the same approval/runtime-input graph as the framework's co-ai agent."""
    from connectonion import useful_plugins

    return [useful_plugins.tool_approval, useful_plugins.runtime_input]
