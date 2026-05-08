"""
Build the Open Graph image for drewroper.com.

Reads assets/portrait.jpg, dithers it at the same chunky resolution as the
on-page version, and composes it onto a 1200x630 canvas as a centered
3:2 portrait with the site name + URL beside it.

Outputs both:
  - assets/og-image.png  (static, frame 0)
  - assets/og-image.gif  (animated breathing dither, ~4s loop)

Run: python3 scripts/build-og.py
"""

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parent.parent
SRC      = ROOT / "assets" / "portrait.jpg"
OUT_PNG  = ROOT / "assets" / "og-image.png"
OUT_GIF  = ROOT / "assets" / "og-image.gif"

OG_W, OG_H = 1200, 630
BG     = (12, 12, 13)
DARK   = (12, 12, 13)
LIGHT  = (244, 241, 236)
ACCENT = (214, 255, 56)

PAD_Y = 70
PORTRAIT_H = OG_H - PAD_Y * 2          # 490
PORTRAIT_W = int(round(PORTRAIT_H * 3 / 2))  # 735
DITHER_W   = 120
DITHER_H   = 80

PORTRAIT_X = OG_W - PAD_Y - PORTRAIT_W
PORTRAIT_Y = PAD_Y

# Animation: 12 frames, 4-second loop.
FRAMES   = 12
DURATION = 4.0
FRAME_MS = int(round(DURATION * 1000 / FRAMES))  # 333ms

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


def _load_gray():
    """Cover-fit crop + resize the source portrait to the dither grid."""
    img = Image.open(SRC).convert("L")
    sw, sh = img.size

    target = 3 / 2
    src    = sw / sh
    if src > target:
        new_w = int(round(sh * target))
        left = (sw - new_w) // 2
        img = img.crop((left, 0, left + new_w, sh))
    else:
        new_h = int(round(sw / target))
        top   = max(0, (sh - new_h) // 2 - sh // 12)
        top   = min(top, sh - new_h)
        img = img.crop((0, top, sw, top + new_h))

    img = img.resize((DITHER_W, DITHER_H), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)
    arr = ((arr - 128.0) * 1.18 + 128.0).clip(0, 255)
    return arr


def dither_portrait(gray, t=0.0):
    """Render one breathing-dither frame from the cached gray array."""
    th_full = np.tile(BAYER, (DITHER_H // 8 + 2, DITHER_W // 8 + 2))

    # Drift the Bayer matrix and modulate threshold over time so the
    # speckle shimmers like the on-page canvas.
    ox = int(round(math.sin(t * 0.25) * 6))
    oy = int(round(math.cos(t * 0.18) * 6))
    ts = math.sin(t * 0.40) * 12

    th = np.roll(th_full, (oy, ox), axis=(0, 1))[:DITHER_H, :DITHER_W]
    binary = gray > (th + ts)

    out = np.empty((DITHER_H, DITHER_W, 3), dtype=np.uint8)
    out[binary]  = LIGHT
    out[~binary] = DARK

    _stamp_big_x(out)

    return Image.fromarray(out, "RGB").resize(
        (PORTRAIT_W, PORTRAIT_H), Image.NEAREST
    )


def _stamp_big_x(arr):
    """Two thick diagonal lines crossing at the face."""
    h, w, _ = arr.shape
    cx = int(round(w * 0.52))
    cy = int(round(h * 0.30))
    hw = int(round(w * 0.22))
    hh = int(round(h * 0.22))

    brush = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]

    for x1, y1, x2, y2 in [
        (cx - hw, cy - hh, cx + hw, cy + hh),
        (cx + hw, cy - hh, cx - hw, cy + hh),
    ]:
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x1 + (x2 - x1) * t))
            y = int(round(y1 + (y2 - y1) * t))
            for dx, dy in brush:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    arr[ny, nx] = ACCENT


def load_font(size, bold=False):
    name = "Silkscreen-Bold.ttf" if bold else "Silkscreen-Regular.ttf"
    path = ROOT / "assets" / "fonts" / name
    return ImageFont.truetype(str(path), size)


def load_mono(size):
    return ImageFont.truetype(str(ROOT / "assets" / "fonts" / "GeistMono-Regular.ttf"), size)


def build_frame(gray, t):
    """Compose one full OG frame (portrait + text) for animation time t."""
    canvas = Image.new("RGB", (OG_W, OG_H), BG)
    canvas.paste(dither_portrait(gray, t), (PORTRAIT_X, PORTRAIT_Y))

    draw = ImageDraw.Draw(canvas)
    text_x = 70

    eyebrow = load_mono(18)
    draw.text((text_x, PAD_Y + 10), "DESIGNER · EST. 1986",
              font=eyebrow, fill=(140, 138, 134))

    title = load_font(140)
    draw.text((text_x, PAD_Y + 60), "Drew",  font=title, fill=LIGHT)
    draw.text((text_x, PAD_Y + 200), "Roper", font=title, fill=LIGHT)

    url_font = load_mono(20)
    draw.text((text_x, OG_H - PAD_Y - 26), "drewroper.com",
              font=url_font, fill=ACCENT)

    return canvas


def main():
    gray = _load_gray()

    frames = [build_frame(gray, (i / FRAMES) * DURATION) for i in range(FRAMES)]

    frames[0].save(OUT_PNG, format="PNG", optimize=True)
    print(f"wrote {OUT_PNG.relative_to(ROOT)}  ({OG_W}x{OG_H})")

    # Quantise each frame to a tight palette so the GIF stays small.
    quantised = [
        f.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        for f in frames
    ]
    quantised[0].save(
        OUT_GIF,
        save_all=True,
        append_images=quantised[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    size_kb = OUT_GIF.stat().st_size / 1024
    print(f"wrote {OUT_GIF.relative_to(ROOT)}  ({FRAMES} frames, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
