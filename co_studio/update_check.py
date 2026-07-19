"""Is a newer connectonion-studio published on PyPI? Drives the 'update available' banner.

Loopback-only for SERVING doesn't stop outbound checks — this makes ONE cached, short-timeout,
offline-tolerant GET to PyPI. It only ever reports whether an update exists; applying it (a
`pipx upgrade` + restart) stays the user's call. See docs/ for the desktop Sparkle channel.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import time
import urllib.request

_PYPI_URL = "https://pypi.org/pypi/connectonion-studio/json"
_CACHE_TTL = 3600.0  # PyPI is polled at most hourly; the banner is never time-critical
_cache: dict[str, object] = {"at": 0.0, "latest": None}


def current_version() -> str:
    """Installed distribution version (a bare dev checkout falls back to 0.0.0)."""
    try:
        return importlib.metadata.version("connectonion-studio")
    except Exception:  # noqa: BLE001 — not installed as a dist
        return "0.0.0"


def _fetch_latest() -> str | None:
    """Latest version on PyPI, or None on any failure (offline, timeout, bad JSON)."""
    try:
        with urllib.request.urlopen(_PYPI_URL, timeout=3) as response:  # noqa: S310 — fixed https URL
            return str(json.loads(response.read().decode("utf-8"))["info"]["version"])
    except Exception:  # noqa: BLE001 — a failed check just means "no update info right now"
        return None


def _newer(latest: str, current: str) -> bool:
    """latest > current — via packaging when present, else a numeric-tuple fallback."""
    try:
        from packaging.version import Version

        return Version(latest) > Version(current)
    except Exception:  # noqa: BLE001 — packaging absent or a non-PEP440 string
        parse = lambda v: tuple(int(n) for n in re.findall(r"\d+", v))  # noqa: E731
        return parse(latest) > parse(current)


def check(force: bool = False) -> dict[str, object]:
    """{current, latest, update_available} — cached hourly, never raises."""
    current = current_version()
    now = time.time()
    if force or _cache["latest"] is None or now - float(_cache["at"]) > _CACHE_TTL:
        latest = _fetch_latest()
        if latest:
            _cache["at"], _cache["latest"] = now, latest
    latest = _cache["latest"]
    return {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and _newer(str(latest), current)),
    }
