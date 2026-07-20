"""Dangerous capability: browser automation with per-chat tab binding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..sandbox import create_sandboxed_browser

_browser: Any | None = None


def tools(*, work_dir: str | Path | None = None, runtime_dir: str | Path | None = None) -> list[Any]:
    """One visible browser shared by request agents; the plugin isolates their tabs."""
    from connectonion.useful_tools.browser_tools import BrowserAutomation

    global _browser
    if _browser is None:
        _browser = (
            create_sandboxed_browser(work_dir, headless=False)
            if work_dir is not None
            else BrowserAutomation(headless=False)
        )
    return [_browser]


def plugins() -> list[Any]:
    """Bind browser tabs to chat sessions and format screenshot/image results."""
    from connectonion import useful_plugins

    return [useful_plugins.bind_browser_session, useful_plugins.image_result_formatter]
