"""FastAPI application factory: API routers, websockets, and the static frontend."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, registry, setup_check
from .api import agents, settings_api, setup, ws
from .supervisor import SUPERVISOR


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the doctor, adopt orphan agents, and drive the health-poll loop."""
    registry.ensure_dirs()
    for entry in setup_check.run_doctor():
        mark = "ok  " if entry["ok"] else "FAIL"
        print(f"[co-studio] doctor {mark} {entry['check']} — {entry['detail']}", flush=True)
    SUPERVISOR.adopt_orphans()
    poller = asyncio.create_task(SUPERVISOR.run())
    yield
    poller.cancel()
    with suppress(asyncio.CancelledError):
        await poller


def create_app() -> FastAPI:
    """Build the studio app: /api/*, /ws/*, and the zero-build frontend at /."""
    app = FastAPI(title="ConnectOnion Studio", lifespan=_lifespan)

    @app.middleware("http")
    async def _always_revalidate(request, call_next):
        """No heuristic caching: the browser must revalidate every asset each load,
        so edits to the zero-build frontend show up on a plain reload (still cheap —
        unchanged files come back as a 304 via StaticFiles' ETag/Last-Modified)."""
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(agents.router, prefix="/api")
    app.include_router(setup.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")
    app.include_router(ws.router)

    for sub in ("assets", "css", "js"):
        directory = config.FRONTEND_DIR / sub
        if directory.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=directory), name=sub)

    @app.get("/", include_in_schema=False)
    def index() -> Response:
        """Serve the SPA (or a plain notice while the frontend is absent)."""
        page = config.FRONTEND_DIR / "index.html"
        if page.exists():
            return FileResponse(page)
        return HTMLResponse("<h1>ConnectOnion Studio</h1><p>frontend/ not built yet — the API is live under /api.</p>")

    return app
