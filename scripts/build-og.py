"""
Build the Open Graph image for drewroper.com.

Reads assets/portrait.jpg, dithers it at the same chunky resolution as the
on-page version, and composes it onto a 1200x630 canvas as a centered
3:2 portrait with the site name + URL beside it. Output:
assets/og-image.png.

Run: python3 scripts/build-og.py
"""

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "assets" / "portrait.jpg"
OUT  = ROOT / "assets" / "og-image.png"

OG_W, OG_H = 1200, 630
BG     = (12, 12, 13)
DARK   = (12, 12, 13)
LIGHT  = (244, 241, 236)
ACCENT = (214, 255, 56)

# Dithered portrait dimensions — 3:2 to match the source crop, sized to
# fill the OG height with comfortable padding.
PAD_Y = 70
PORTRAIT_H = OG_H - PAD_Y * 2          # 490
PORTRAIT_W = int(round(PORTRAIT_H * 3 / 2))  # 735
DITHER_W   = 120                       # same as on-page canvas width
DITHER_H   = 80                        # same as on-page canvas height

# Layout: portrait flush right with text on the left.
PORTRAIT_X = OG_W - PAD_Y - PORTRAIT_W
PORTRAIT_Y = PAD_Y

BAYER = np.array([
    [ 0, 32,  8, 40,  2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44,  4, 36, 14, 46,  6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [ 3, 35, 11, 43,  1, 33,  9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47,  7, 39, 13, 45,  5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
]) * 4   # 0..252


def dither_portrait():
    img = Image.open(SRC).convert("L")
    sw, sh = img.size

    # Cover-fit crop to 3:2, biased slightly up so the face sits in the
    # upper third (matches the way the live canvas renders).
    target = 3 / 2
    src    = sw / sh
    if src > target:
        new_w = int(round(sh * target))
        left = (sw - new_w) // 2
        img = img.crop((left, 0, left + new_w, sh))
    else:
        new_h = int(round(sw / target))
        top   = max(0, (sh - new_h) // 2 - sh // 12)  # bias up ~8%
        top   = min(top, sh - new_h)
        img = img.crop((0, top, sw, top + new_h))

    img = img.resize((DITHER_W, DITHER_H), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)

    # Mild contrast stretch (matches the JS sample function).
    arr = ((arr - 128.0) * 1.18 + 128.0).clip(0, 255)

    # Tile Bayer to image size and threshold.
    th = np.tile(BAYER, (DITHER_H // 8 + 2, DITHER_W // 8 + 2))[:DITHER_H, :DITHER_W]
    binary = arr > th

    out = np.empty((DITHER_H, DITHER_W, 3), dtype=np.uint8)
    out[binary]  = LIGHT
    out[~binary] = DARK

    return Image.fromarray(out, "RGB").resize((PORTRAIT_W, PORTRAIT_H), Image.NEAREST)


def load_font(size, prefer=("Geist", "Inter", "DejaVuSans")):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    canvas = Image.new("RGB", (OG_W, OG_H), BG)

    portrait = dither_portrait()
    canvas.paste(portrait, (PORTRAIT_X, PORTRAIT_Y))

    draw = ImageDraw.Draw(canvas)
    text_x = 70

    # Eyebrow line (mono-ish small)
    eyebrow = load_font(20)
    draw.text((text_x, PAD_Y + 10), "DESIGNER · EST. 1986",
              font=eyebrow, fill=(140, 138, 134))

    # Big name
    title = load_font(140)
    draw.text((text_x, PAD_Y + 60), "Drew",  font=title, fill=LIGHT)
    draw.text((text_x, PAD_Y + 200), "Roper", font=title, fill=LIGHT)

    # URL line at the bottom-left
    url_font = load_font(22)
    draw.text((text_x, OG_H - PAD_Y - 28), "drewroper.com",
              font=url_font, fill=ACCENT)

    canvas.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)}  ({OG_W}x{OG_H})")


if __name__ == "__main__":
    main()
