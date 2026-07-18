#!/usr/bin/env python3
"""Render the brand wordmark "ConnectOnion Studio" (New York serif) as light/dark transparent PNGs
for the README. Markdown can't use custom fonts, so the wordmark ships as an image (via <picture>).

    ../.venv/bin/python make_wordmark.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
# Georgia, not New York: the app's --font-brand stack is 'New York', ui-serif, Georgia, ... but the
# WKWebView falls through to Georgia, so THAT is the wordmark the user actually sees. Match it.
NY = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
NYI = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"

SCALE = 3
SIZE = 64 * SCALE
PAD_X = 10 * SCALE
PAD_Y = 12 * SCALE
GAP = 10 * SCALE                      # space between the two words


def weighted(path: str, prefer: list[str]) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, SIZE)
    try:
        names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
        for want in prefer:
            if want in names:
                f.set_variation_by_name(want)
                print(f"  {Path(path).name}: using '{want}'  (of {names})")
                return f
        print(f"  {Path(path).name}: default weight  (available {names})")
    except Exception as e:  # noqa: BLE001
        print(f"  {Path(path).name}: not variable ({e})")
    return f


def render(out: Path, ink: tuple, muted: tuple) -> None:
    bold = weighted(NY, ["Bold", "Semibold", "Medium"])
    ital = weighted(NYI, ["Regular", "Italic"])

    w1 = bold.getlength("ConnectOnion")
    w2 = ital.getlength("Studio")
    asc, desc = bold.getmetrics()
    W = int(PAD_X * 2 + w1 + GAP + w2)
    H = int(PAD_Y * 2 + asc + desc)
    baseline = PAD_Y + asc

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((PAD_X, baseline), "ConnectOnion", font=bold, fill=ink, anchor="ls")
    d.text((PAD_X + w1 + GAP, baseline), "Studio", font=ital, fill=muted, anchor="ls")
    img.save(out)
    print(f"wrote {out.name}  ({W}x{H})")


def main() -> None:
    print("light:")
    render(HERE / "wordmark-light.png", ink=(38, 37, 35, 255), muted=(38, 37, 35, 178))   # #262523 / 0.70
    print("dark:")
    render(HERE / "wordmark-dark.png", ink=(236, 234, 228, 255), muted=(236, 234, 228, 158))  # #ECEAE4 / 0.62


if __name__ == "__main__":
    main()
