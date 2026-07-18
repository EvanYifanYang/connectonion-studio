"""Setup status endpoint (doctor + auth/key checks)."""

from __future__ import annotations

from fastapi import APIRouter

from .. import setup_check

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status")
def setup_status() -> dict[str, object]:
    """GET /api/setup/status."""
    return setup_check.status()
