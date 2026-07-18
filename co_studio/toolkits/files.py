"""Files toolkit: read-only local file access."""

from __future__ import annotations

from typing import Any


def tools() -> list[Any]:
    """The framework's read_file tool."""
    from connectonion import useful_tools

    return [useful_tools.read_file]


def plugins() -> list[Any]:
    """No plugins needed for read-only file access."""
    return []
