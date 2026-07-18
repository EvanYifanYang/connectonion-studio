#!/usr/bin/env python3
"""Generate the macOS AppIcon — a warm-paper card with the brand onion — into Assets.xcassets.

Reproducible: re-run to regenerate every size + Contents.json.
    ../../.venv/bin/python make_appicon.py        # (any python with Pillow >= 8.2)

Source onion is `onion_source_1024.png` (the iOS app's flattened 1024 brand onion, copied in so this
script needs no sibling repo). Tune the LOOK knobs below if the proportions want adjusting.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
SRC = HERE / "onion_source_1024.png"
ICONSET = HERE.parent / "ConnectOnionStudio/ConnectOnionStudio/Assets.xcassets/AppIcon.appiconset"

# --- LOOK knobs ------------------------------------------------------------
CANVAS = 1024                     # master canvas
CARD = 824                        # rounded card size (macOS Big Sur grid: 100px margin each side)
RADIUS = 185                      # card corner radius (~0.224 * CARD)
PAPER = (250, 249, 245, 255)      # #FAF9F5 warm paper
ONION_SCALE = 0.78                # onion width as a fraction of the card
SHADOW_RGBA = (30, 26, 22, 70)    # soft contact shadow so the near-white card reads on white
SHADOW_DY = 10                    # shadow drop
SHADOW_BLUR = 18
# ---------------------------------------------------------------------------

MARGIN = (CANVAS - CARD) // 2

# macOS AppIcon slots: (point size, scale, filename). Emitted from one master.
SLOTS = [
    (16, "1x", "AppIcon-16.png"),
    (16, "2x", "AppIcon-16@2x.png"),
    (32, "1x", "AppIcon-32.png"),
    (32, "2x", "AppIcon-32@2x.png"),
    (128, "1x", "AppIcon-128.png"),
    (128, "2x", "AppIcon-128@2x.png"),
    (256, "1x", "AppIcon-256.png"),
    (256, "2x", "AppIcon-256@2x.png"),
    (512, "1x", "AppIcon-512.png"),
    (512, "2x", "AppIcon-512@2x.png"),
]


def build_master() -> Image.Image:
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [MARGIN, MARGIN + SHADOW_DY, MARGIN + CARD, MARGIN + CARD + SHADOW_DY],
        radius=RADIUS, fill=SHADOW_RGBA,
    )
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR)))

    card = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle(
        [MARGIN, MARGIN, MARGIN + CARD, MARGIN + CARD], radius=RADIUS, fill=PAPER,
    )
    canvas = Image.alpha_composite(canvas, card)

    onion = Image.open(SRC).convert("RGBA")
    target = int(round(CARD * ONION_SCALE))
    onion = onion.resize((target, target), Image.LANCZOS)
    off = (CANVAS - target) // 2
    canvas.alpha_composite(onion, (off, off))
    return canvas


def px(size: int, scale: str) -> int:
    return size * (2 if scale == "2x" else 1)


def main() -> None:
    master = build_master()
    ICONSET.mkdir(parents=True, exist_ok=True)

    resized: dict[int, Image.Image] = {}
    for size, scale, fname in SLOTS:
        p = px(size, scale)
        if p not in resized:
            resized[p] = master.resize((p, p), Image.LANCZOS)
        resized[p].save(ICONSET / fname)

    contents = {
        "images": [
            {"idiom": "mac", "size": f"{s}x{s}", "scale": sc, "filename": fn}
            for s, sc, fn in SLOTS
        ],
        "info": {"author": "make_appicon.py", "version": 1},
    }
    (ICONSET / "Contents.json").write_text(json.dumps(contents, indent=2) + "\n")
    print(f"Wrote {len(SLOTS)} PNGs + Contents.json to {ICONSET.relative_to(HERE.parents[1])}")


if __name__ == "__main__":
    main()
