"""Shell toolkit: bash execution gated by the shell_approval plugin (Approval card)."""

from __future__ import annotations

from typing import Any


def tools() -> list[Any]:
    """The framework's bash tool."""
    from connectonion import useful_tools

    return [useful_tools.bash]


def plugins() -> list[Any]:
    """shell_approval — every non-safe command asks the user before running."""
    from connectonion import useful_plugins

    return [useful_plugins.shell_approval]
