"""Ed25519 identity and QR helpers around connectonion.address."""

from __future__ import annotations

import io
from pathlib import Path

import segno


def create(co_dir: Path) -> str:
    """Generate a fresh identity into <agent_dir>/.co and return its 0x address."""
    from connectonion import address as co_address

    co_dir.mkdir(parents=True, exist_ok=True)
    data = co_address.generate()
    co_address.save(data, co_dir)
    return str(data["address"])


def load_address(co_dir: Path) -> str | None:
    """Read the 0x address saved in a .co directory, if present."""
    from connectonion import address as co_address

    data = co_address.load(co_dir)
    return str(data["address"]) if data else None


def qr_svg(payload: str) -> str:
    """Render the bare 0x address as a high-error-correction SVG QR on a white card."""
    qr = segno.make(payload, error="h")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=8, border=3, dark="#262523", light="#FFFFFF", xmldecl=True)
    return buffer.getvalue().decode("utf-8")
