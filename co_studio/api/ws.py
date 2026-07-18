"""WebSocket endpoints: fleet status pushes and per-agent log streams."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import config, logs, registry
from ..supervisor import SUPERVISOR
from .agents import summarize

router = APIRouter()


def _status_frame() -> dict[str, object]:
    """The {"type":"status","agents":[...]} frame."""
    return {"type": "status", "agents": [summarize(meta) for meta in registry.load_all()]}


@router.websocket("/ws/status")
async def status_ws(websocket: WebSocket) -> None:
    """Push a status frame on every state change and at least every 5 seconds."""
    await websocket.accept()
    queue = SUPERVISOR.subscribe()
    try:
        while True:
            await websocket.send_json(_status_frame())
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(queue.get(), timeout=config.HEALTH_INTERVAL)
    except (WebSocketDisconnect, RuntimeError):  # RuntimeError: send after client close
        pass
    finally:
        SUPERVISOR.unsubscribe(queue)


@router.websocket("/ws/agents/{slug}/logs")
async def logs_ws(websocket: WebSocket, slug: str) -> None:
    """Stream stdout and framework-logger lines as they arrive."""
    if registry.load(slug) is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    agent_dir = registry.agent_dir(slug)
    stdout_path = agent_dir / config.STDOUT_LOG_NAME
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()

    async def pump(source: str, get_path: Callable[[], Path | None]) -> None:
        async for line in logs.follow(get_path):
            await queue.put({"source": source, "line": line})

    tasks = [
        asyncio.create_task(pump("stdout", lambda: stdout_path)),
        asyncio.create_task(pump("logger", lambda: logs.logger_log_path(agent_dir))),
    ]
    try:
        while True:
            await websocket.send_json(await queue.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for task in tasks:
            task.cancel()
