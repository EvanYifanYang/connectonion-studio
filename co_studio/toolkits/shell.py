"""Dangerous capability: shell execution gated by the unified approval protocol."""

from __future__ import annotations

from typing import Any


def tools() -> list[Any]:
    """The framework's bash tool."""
    from connectonion import useful_tools

    return [useful_tools.bash]


def plugins() -> list[Any]:
    """Use the same approval/runtime-input graph as the framework's co-ai agent."""
    from connectonion import useful_plugins

    return [useful_plugins.tool_approval, useful_plugins.runtime_input]
