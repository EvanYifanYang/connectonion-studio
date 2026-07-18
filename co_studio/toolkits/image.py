"""Image toolkit: a tiny PNG generator plus the plugin that renders it as an image card."""

from __future__ import annotations

import base64
import struct
import zlib
from typing import Any

_PALETTE: dict[str, tuple[int, int, int]] = {
    "purple": (139, 120, 214),
    "green": (60, 200, 90),
    "red": (220, 70, 70),
    "blue": (80, 120, 246),
    "black": (20, 20, 22),
}


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Build a minimal solid-color PNG with no external dependencies."""
    r, g, b = rgb
    raw = b"".join(b"\x00" + bytes([r, g, b]) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def generate_image(color: str = "purple") -> str:
    """Generate a small solid-color image and return it as a data URL (tests the image card)."""
    png = _png(120, 120, _PALETTE.get(color.lower(), _PALETTE["purple"]))
    return "data:image/png;base64," + base64.b64encode(png).decode()


def tools() -> list[Any]:
    """The demo image generator."""
    return [generate_image]


def plugins() -> list[Any]:
    """image_result_formatter — turns the data URL result into an image card."""
    from connectonion import useful_plugins

    return [useful_plugins.image_result_formatter]
