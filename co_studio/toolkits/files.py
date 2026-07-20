"""Sensitive capability: read and search local files without write methods."""

from __future__ import annotations

from typing import Any


def tools() -> list[Any]:
    """A stateful read-only FileTools bundle: read_file, glob and grep."""
    from connectonion import useful_tools

    return [useful_tools.FileTools(permission="read")]


def plugins() -> list[Any]:
    """No plugins needed for read-only file access."""
    return []
