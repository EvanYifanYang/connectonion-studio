"""Selectable tool groups; generated agents resolve their checked groups at runtime."""

from __future__ import annotations

from importlib import import_module
from typing import Any

NAMES: tuple[str, ...] = ("utility", "web", "files", "shell", "image")

HINTS: dict[str, str] = {
    "utility": "math, a calculator, demo weather, the time, dice, text reversal, primes and Fibonacci",
    "web": "fetching web pages (WebFetch)",
    "files": "reading local files (read_file)",
    "shell": "running shell commands — every command needs the user's approval first",
    "image": "generating small demo images (renders as an image card)",
}


def validate(names: list[str]) -> list[str]:
    """Dedupe and order the selection canonically; raise ValueError on unknown groups."""
    unknown = sorted(set(names) - set(NAMES))
    if unknown:
        raise ValueError(f"unknown toolkits: {', '.join(unknown)} (available: {', '.join(NAMES)})")
    selected = set(names)
    return [name for name in NAMES if name in selected]


def resolve(names: list[str]) -> tuple[list[Any], list[Any]]:
    """Build the (tools, plugins) lists for the selected toolkit groups."""
    tools: list[Any] = []
    plugins: list[Any] = []
    for name in validate(names):
        module = import_module(f".{name}", __package__)
        tools.extend(module.tools())
        plugins.extend(module.plugins())
    return tools, plugins
