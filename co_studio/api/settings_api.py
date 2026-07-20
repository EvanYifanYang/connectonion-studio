"""Studio settings: appearance and the agents storage location."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, storage

router = APIRouter(prefix="/settings", tags=["settings"])


class StorageBody(BaseModel):
    """POST /api/settings/storage payload."""

    path: str


class AppearanceBody(BaseModel):
    """POST /api/settings/appearance payload."""

    appearance: str


@router.get("/appearance")
def get_appearance() -> dict[str, str]:
    """The persisted appearance shared across browser origins and the macOS shell."""
    return {"appearance": config.appearance()}


@router.post("/appearance")
def set_appearance(body: AppearanceBody) -> dict[str, str]:
    """Persist the user's explicit appearance choice."""
    try:
        config.save_appearance(body.appearance)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"appearance": body.appearance}


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


@router.post("/pick-workspace")
def pick_workspace() -> dict[str, str]:
    """Choose a project/workspace folder for one Agent."""
    path = storage.pick_folder("Choose this Agent's workspace")
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
