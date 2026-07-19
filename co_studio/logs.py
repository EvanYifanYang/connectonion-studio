"""Log tailing, following, and best-effort parsing of agent output."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import AsyncIterator, Callable

from . import config

_TAIL_BYTES = 131072
_RELAY_BAD = ("Relay error", "relay connection error", "relay still unreachable", "Relay disconnected")
_ANNOUNCE_RE = re.compile(r"\[co-studio\] announce ips=.* endpoints=(\d+)")
_TOOL_CALL_RE = re.compile(r"▸\s*(\w+)\(")
_USER_INPUT_RE = re.compile(r'>\s*"')
_BALANCE_RE = re.compile(r"balance:\s*\$?\s*([\d.]+)")


def latest_run_log(agent_dir: Path) -> Path | None:
    """The current/most-recent per-run stdout file, or the legacy single log as a fallback.

    Per-run files land in <agent_dir>/runs/<timestamp>.log (one per start→stop). Agents that
    predate per-run logging (or haven't been restarted since) still have the appended
    studio-stdout.log — returned only when no run files exist, so nothing breaks pre-migration.
    """
    run_dir = agent_dir / config.RUNS_DIR_NAME
    if run_dir.is_dir():
        runs = sorted(run_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        if runs:
            return runs[-1]
    legacy = agent_dir / config.STDOUT_LOG_NAME
    return legacy if legacy.exists() else None


def parse_balance(log_path: Path | None) -> str | None:
    """Newest 'balance: $X' from the agent's startup banner, formatted as '$X' (None if absent)."""
    for line in reversed(read_tail(log_path, 400)):
        match = _BALANCE_RE.search(line)
        if match:
            return f"${match.group(1)}"
    return None


def read_tail(path: Path | None, lines: int = 20) -> list[str]:
    """Return up to the last `lines` lines of a file (missing file → [])."""
    if path is None or not path.exists():
        return []
    try:
        with path.open("rb") as handle:  # seek to the tail — never load a multi-GB log whole
            handle.seek(0, 2)  # SEEK_END
            size = handle.tell()
            handle.seek(max(0, size - _TAIL_BYTES))
            data = handle.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()[-lines:]


def logger_log_path(agent_dir: Path) -> Path | None:
    """Newest framework Logger file under <agent_dir>/.co/logs, if any (name = agent name)."""
    logs_dir = agent_dir / ".co" / "logs"
    if not logs_dir.is_dir():
        return None
    candidates = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def find_last_traceback(lines: list[str]) -> str | None:
    """Extract the most recent Python traceback block from log lines."""
    start = None
    for index, line in enumerate(lines):
        if line.startswith("Traceback (most recent call last)"):
            start = index
    if start is None:
        return None
    block = [lines[start]]
    for line in lines[start + 1 :]:
        block.append(line)
        if line and not line[0].isspace():  # "ValueError: ..." closes the block
            break
    return "\n".join(block[:40])


def parse_runtime_signals(stdout_log: Path) -> tuple[int | None, bool | None]:
    """Parse (endpoints_announced, relay_ok) from an agent's stdout log, newest evidence first."""
    lines = read_tail(stdout_log, 400)
    endpoints: int | None = None
    for line in reversed(lines):
        match = _ANNOUNCE_RE.search(line)
        if match:
            endpoints = int(match.group(1))
            break
    relay: bool | None = None
    for line in reversed(lines):
        if any(bad in line for bad in _RELAY_BAD) or "no relay" in line:
            relay = False
            break
        if "✓ relay" in line or "♥" in line:
            relay = True
            break
    return endpoints, relay


def parse_events(lines: list[str], limit: int = 8) -> str | None:
    """Best-effort event timeline like "user_input → tool_call(get_weather) → complete"."""
    events: list[str] = []
    for line in lines:
        if _USER_INPUT_RE.search(line):
            events.append("user_input")
        match = _TOOL_CALL_RE.search(line)
        if match:
            events.append(f"tool_call({match.group(1)})")
        if "[OK] complete" in line:
            events.append("complete")
        elif "[ERROR]" in line:
            events.append("error")
    return " → ".join(events[-limit:]) if events else None


async def follow(
    get_path: Callable[[], Path | None], *, from_start: bool = False, backlog: int = 50, poll: float = 0.5
) -> AsyncIterator[str]:
    """Yield existing content then newly appended lines; waits for the file to appear.

    from_start=True streams the whole file from offset 0 (per-run logs → a run is shown from its
    very first line); otherwise only the last `backlog` lines precede the live tail.
    """
    while True:
        path = get_path()
        if path is not None and path.exists():
            break
        await asyncio.sleep(poll)
    if from_start:
        position = 0
    else:
        position = path.stat().st_size
        for line in read_tail(path, backlog):
            yield line
    buffer = b""
    while True:
        size = path.stat().st_size if path.exists() else 0
        if size < position:  # truncated or rotated — start over
            position, buffer = 0, b""
        if size > position:
            with path.open("rb") as handle:
                handle.seek(position)
                buffer += handle.read()
                position = handle.tell()
            *complete, buffer = buffer.split(b"\n")
            for raw in complete:
                yield raw.decode("utf-8", errors="replace")
        else:
            await asyncio.sleep(poll)
