"""Allocate agent HTTP ports in 8000-8099 by socket probing."""

from __future__ import annotations

import socket

from . import config


def is_free(port: int) -> bool:
    """True when nothing is bound on the port (bind probe on all interfaces)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("", port))
        except OSError:
            return False
        return True


def allocate(reserved: set[int]) -> int:
    """First free, unreserved port in the range; raises RuntimeError when exhausted."""
    for port in config.AGENT_PORT_RANGE:
        if port in reserved:
            continue
        if is_free(port):
            return port
    raise RuntimeError("no free agent port left in 8000-8099")
