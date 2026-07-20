"""Dangerous capability: local file creation and editing with approval support."""

from __future__ import annotations

from typing import Any


def tools() -> list[Any]:
    """Full FileTools bundle with read-before-edit and stale-read protection."""
    from connectonion import useful_tools

    return [useful_tools.FileTools()]


def plugins() -> list[Any]:
    """Prefer file tools over bash and require approval for write/edit operations."""
    from connectonion import useful_plugins

    return [useful_plugins.prefer_write_tool, useful_plugins.tool_approval, useful_plugins.runtime_input]
