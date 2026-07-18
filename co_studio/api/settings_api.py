"""Studio settings: the agents storage location (with migration)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import storage

router = APIRouter(prefix="/settings", tags=["settings"])


class StorageBody(BaseModel):
    """POST /api/settings/storage payload."""

    path: str


@router.get("/storage")
def get_storage() -> dict[str, str]:
    """The agents directory in effect right now."""
    return {"agents_dir": storage.current()}


@router.post("/pick-folder")
def pick_folder() -> dict[str, str]:
    """Pop the native folder chooser and return the chosen path."""
    path = storage.pick_folder()
    if not path:
        raise HTTPException(status_code=409, detail="No folder chosen.")
    return {"path": path}


@router.post("/storage")
async def set_storage(body: StorageBody) -> dict[str, object]:
    """Move existing agents to a new folder and switch the studio over to it."""
    try:
        return await storage.change(body.path)
    except ValueError as exc:  # bad/rejected path
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:  # move failed mid-flight
        raise HTTPException(status_code=500, detail=f"Move failed: {exc}") from exc
