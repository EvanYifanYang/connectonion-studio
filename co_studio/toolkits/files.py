"""Sensitive capability: read and search local files without write methods."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def tools(*, work_dir: str | Path, runtime_dir: str | Path | None = None) -> list[Any]:
    """A workspace-confined read-only bundle: read_file, glob and grep."""
    from co_studio.sandbox import SandboxedFileTools

    return [SandboxedFileTools(work_dir, permission="read")]


def plugins() -> list[Any]:
    """No plugins needed for read-only file access."""
    return []
