"""Web toolkit: page fetching via connectonion's WebFetch."""

from __future__ import annotations

from typing import Any


def tools() -> list[Any]:
    """A WebFetch instance (expands into its public methods as tools)."""
    from connectonion import useful_tools

    return [useful_tools.WebFetch()]


def plugins() -> list[Any]:
    """No plugins needed for web fetching."""
    return []
