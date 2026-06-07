#!/usr/bin/env python3
"""Generate the AILIEN alien head tray icon.

Run this script to recreate ``icons/ailien_icon.png``.

Uses Pillow to draw a stylized alien head — green dome with large
dark eyes, antennae, and a subtle smile — composited onto a transparent
background so the tray code can overlay it on colored status circles.

Usage::

    python3 generate_icon.py          # saves to icons/ailien_icon.png
    python3 generate_icon.py --size 128 --out icons/ailien_icon_lg.png
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def generate_alien_icon(size: int = 128) -> Image.Image:
    """Draw a stylised alien head at *size* × *size* pixels.

    Returns an RGBA ``PIL.Image`` with a transparent background.
    The recommended output size for the tray is 64 px (generated at 2×
    then LANCZOS-scaled down for crisp sub-pixel rendering).
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2

    # --- colour palette ---------------------------------------------------
    alien_green  = (144, 238, 144, 255)   # light green
    alien_dark   = (60, 179, 113, 255)    # medium sea green
    alien_darker = (34, 120, 70, 255)     # shadow green
    eye_white    = (240, 248, 255, 255)   # alice blue
    pupil        = (20, 30, 50, 255)      # nearly black
    glow_colour  = (144, 238, 144, 60)    # green aura

    # --- head (scaled to size) --------------------------------------------
    def s(v: float) -> int:
        return max(1, round(size * v / 128))

    head_top    = cy - s(48)
    head_bottom = cy + s(42)
    head_left   = cx - s(34)
    head_right  = cx + s(34)

    # Outline / shadow
    for offset in (3, 2, 1):
        draw.ellipse(
            [head_left - offset, head_top - offset,
             head_right + offset, head_bottom + offset],
            fill=alien_darker,
        )

    # Main head (ellipse)
    draw.ellipse([head_left, head_top, head_right, head_bottom], fill=alien_green)

    # Chin taper
    chin_y  = cy + s(38)
    chin_tip = cy + s(52)
    cw = s(14)
    draw.polygon([
        (cx - s(28), chin_y),
        (cx + s(28), chin_y),
        (cx + cw // 2, chin_tip),
        (cx - cw // 2, chin_tip),
    ], fill=alien_green)

    # --- eyes -------------------------------------------------------------
    eye_y = cy - s(8)
    for ex in (cx - s(14), cx + s(14)):
        # Socket shadow
        draw.ellipse([ex - s(12), eye_y - s(11), ex + s(12), eye_y + s(11)], fill=alien_darker)
        # White
        draw.ellipse([ex - s(9), eye_y - s(8), ex + s(9), eye_y + s(8)], fill=eye_white)
        # Pupil
        draw.ellipse([ex - s(4), eye_y - s(5), ex + s(4), eye_y + s(5)], fill=pupil)
        # Shine
        draw.ellipse([ex - s(2), eye_y - s(4), ex + s(1), eye_y - s(1)], fill=(255, 255, 255, 200))

    # --- mouth -------------------------------------------------------------
    mouth_y = cy + s(24)
    draw.arc(
        [cx - s(10), mouth_y - s(2), cx + s(10), mouth_y + s(4)],
        start=0, end=180, fill=alien_darker, width=s(2),
    )

    # --- head highlight ----------------------------------------------------
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(highlight)
    hdraw.ellipse(
        [head_left + s(8), head_top + s(2), head_right - s(8), head_top + s(18)],
        fill=(255, 255, 255, 40),
    )
    img = Image.alpha_composite(img, highlight)

    # --- glow ring ---------------------------------------------------------
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(
        [head_left - s(6), head_top - s(6), head_right + s(6), head_bottom + s(6)],
        outline=glow_colour, width=s(2),
    )
    img = Image.alpha_composite(img, glow)

    # --- antennae ----------------------------------------------------------
    ant_base_y = cy - s(46)
    dr = s(4)
    for dx in (-s(12), 0, s(12)):
        ax = cx + dx
        ay = ant_base_y - s(6)
        draw.line([(ax, ant_base_y), (ax, ay + dr)], fill=alien_dark, width=s(2))
        draw.ellipse([ax - dr, ay - dr, ax + dr, ay + dr], fill=(255, 100, 100, 255))
        draw.ellipse([ax - s(1), ay - s(2), ax + s(1), ay], fill=(255, 200, 200, 200))

    # --- antialiasing ------------------------------------------------------
    img = img.filter(ImageFilter.SMOOTH)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AILIEN alien head icon")
    parser.add_argument(
        "--size", type=int, default=128,
        help="Base generation size (default 128; output is downscaled to --out-size)",
    )
    parser.add_argument(
        "--out-size", type=int, default=64,
        help="Output icon size in pixels (default 64)",
    )
    parser.add_argument(
        "--out", "-o", type=str, default="icons/ailien_icon.png",
        help="Output path (default icons/ailien_icon.png)",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating alien icon at {args.size}px…")
    img = generate_alien_icon(size=args.size)

    final = img.resize((args.out_size, args.out_size), Image.LANCZOS)
    final.save(str(out_path))
    print(f"Saved {args.out_size}×{args.out_size} icon to {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
