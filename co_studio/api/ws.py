"""WebSocket endpoints: fleet status pushes and per-agent log streams."""

from __future__ import annotations

import asyncio
from contextlib import suppress

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
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()

    async def pump() -> None:
        # Follow ONLY this run's file, from its first line — so the console shows the current start
        # onward, never earlier runs. (The framework's own .co/logs accumulates across runs and is
        # deliberately left out here.)
        async for line in logs.follow(lambda: SUPERVISOR.current_log_path(slug), from_start=True):
            await queue.put({"source": "stdout", "line": line})

    async def send_loop() -> None:
        while True:
            await websocket.send_json(await queue.get())

    async def recv_loop() -> None:
        # Nothing else reads the socket, so an idle client's disconnect would never
        # surface (send_loop is parked on queue.get()). Draining receives lets a close
        # wake us so the pump task doesn't leak forever.
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return

    tasks = [
        asyncio.create_task(pump()),
        asyncio.create_task(send_loop()),
        asyncio.create_task(recv_loop()),
    ]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            with suppress(WebSocketDisconnect, RuntimeError):
                task.result()  # absorb the expected disconnect/close; re-raise anything else
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
