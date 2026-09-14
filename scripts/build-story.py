"""
Render Instagram story graphics (1080x1920) for the /40 countdown.

    python3 scripts/build-story.py [data.json] [--variant a|b|c|d] [--slug x ...]
                                   [--extras] [--out DIR]

Reads data/albums.json (or the file given), renders every slotted album —
or just the slugs given — into out/stories/. --extras also renders the
highlight cover and the two intro slides. --variant picks the layout; the
default is set in VARIANT below once one is chosen.

Layout rules shared by every variant:
  * Instagram covers the top ~250px (progress bar, handle) and bottom
    ~250px (reply bar). Nothing important lives there.
  * Artist above title, title above cover, cover centred.
  * The band under the cover is left open for the link sticker.
  * Day indicator is quiet: microcopy or a 40-dot rail.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT  = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"

W, H     = 1080, 1920
TOP, BOT = 250, 1670
PAD      = 84
COL      = W - PAD * 2

BG     = (12, 12, 13)
LIGHT  = (244, 241, 236)
MUTED  = (140, 138, 134)
FAINT  = (86, 84, 79)
RULE   = (38, 38, 40)
ACCENT = (214, 255, 56)

VARIANT = "a"

BAYER = np.array([
    [ 0,32, 8,40, 2,34,10,42],[48,16,56,24,50,18,58,26],
    [12,44, 4,36,14,46, 6,38],[60,28,52,20,62,30,54,22],
    [ 3,35,11,43, 1,33, 9,41],[51,19,59,27,49,17,57,25],
    [15,47, 7,39,13,45, 5,37],[63,31,55,23,61,29,53,21],
]) * 4


def font(name, size):
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)

mono      = lambda s: font("GeistMono-Regular", s)
sans      = lambda s: font("Geist-300", s)
sans_md   = lambda s: font("Geist-500", s)
display   = lambda s: font("Bricolage-800", s)


# ── text helpers ─────────────────────────────────────────────────────────
def tracked(d, xy, text, f, fill, em=0.10):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + f.size * em
    return x


def tracked_w(text, f, em=0.10):
    return sum(f.getlength(c) for c in text) + f.size * em * max(len(text) - 1, 0)


def wrap(text, f, width):
    lines, cur = [], ""
    for word in text.split():
        t = f"{cur} {word}".strip()
        if f.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = word
    lines.append(cur)
    return lines


def fit(text, mk, size, width, max_lines, min_size):
    """Largest size at which text wraps into <= max_lines within width."""
    while size > min_size:
        f = mk(size); lines = wrap(text, f, width)
        if len(lines) <= max_lines:
            return f, lines
        size -= 4
    f = mk(min_size)
    return f, wrap(text, f, width)[:max_lines]


# ── image helpers ────────────────────────────────────────────────────────
def square(im, size):
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                  (im.width + s) // 2, (im.height + s) // 2))
    return im.resize((size, size), Image.LANCZOS)


def dither(im, grid, on=LIGHT, off=BG, contrast=1.2, threshold_shift=0):
    """Two-tone ordered dither at `grid` cells across, scaled back up with
    hard pixels — the site's portrait treatment."""
    g = np.array(im.convert("L").resize((grid, int(grid * im.height / im.width)), Image.LANCZOS),
                 dtype=np.float32)
    g = ((g - 128.0) * contrast + 128.0 + threshold_shift).clip(0, 255)
    h, w = g.shape
    th = np.tile(BAYER, (h // 8 + 1, w // 8 + 1))[:h, :w]
    out = np.empty((h, w, 3), dtype=np.uint8)
    b = g > th
    out[b], out[~b] = on, off
    return Image.fromarray(out, "RGB").resize(im.size, Image.NEAREST)


def grain(size, density=0.06, tone=(26, 26, 28)):
    """Sparse Bayer speckle for a quiet background texture."""
    w, h = size
    gw, gh = w // 6, h // 6
    rng = np.random.default_rng(40)
    field = rng.random((gh, gw))
    out = np.full((gh, gw, 3), BG, dtype=np.uint8)
    out[field < density] = tone
    return Image.fromarray(out, "RGB").resize((w, h), Image.NEAREST)


# ── shared pieces ────────────────────────────────────────────────────────
def header(d, a, y):
    """Artist (H2) then album title (H1). Returns the y below the block."""
    d.text((PAD, y), a["artist"], font=sans(40), fill=MUTED)
    y += 62
    f, lines = fit(a["title"], display, 92, COL, 2, 56)
    for ln in lines:
        d.text((PAD - 4, y), ln, font=f, fill=LIGHT)
        y += int(f.size * 1.02)
    return y + 8


def microcopy(d, a, y, right=False):
    text = f'DAY {a["no"]:02d} / 40'
    f = mono(24)
    x = W - PAD - tracked_w(text, f) if right else PAD
    tracked(d, (x, y), text, f, FAINT)


def url(d, y):
    tracked(d, (PAD, y), "DREWROPER.COM/40", mono(24), ACCENT)


def dot_rail(d, a, side="left"):
    """40 dots down one edge, filled through today's number."""
    n = 40; gap = 30; r = 5
    total = (n - 1) * gap
    y0 = (H - total) // 2
    x = 40 if side == "left" else W - 40
    for i in range(n):
        y = y0 + i * gap
        fill = ACCENT if i < a["no"] else RULE
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


# ── variants ─────────────────────────────────────────────────────────────
COVER = 880
CX    = (W - COVER) // 2

def variant_a(a, art):
    """Offset dither: a 1-bit copy of the cover sits behind the real one,
    shifted down-right like a misregistered print. Dot rail on the left."""
    c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
    y = header(d, a, TOP + 40)
    cy = max(y + 36, 560)
    c.paste(dither(square(art, COVER), 110), (CX + 44, cy + 44))
    c.paste(square(art, COVER), (CX, cy))
    dot_rail(d, a, "left")
    url(d, BOT - 30)
    return c


def variant_b(a, art):
    """Field: the cover itself, blown up and dithered dim, is the texture
    behind everything. Microcopy for the day."""
    big = square(art, W).resize((W, W), Image.LANCZOS)
    tall = Image.new("RGB", (W, H), BG)
    tall.paste(big, (0, (H - W) // 2))
    tall = dither(tall, 135, on=(34, 34, 36), off=BG, contrast=1.4)
    c = tall; d = ImageDraw.Draw(c)
    microcopy(d, a, TOP + 4)
    y = header(d, a, TOP + 60)
    cy = max(y + 36, 580)
    c.paste(square(art, COVER), (CX, cy))
    d.rectangle([CX, cy, CX + COVER - 1, cy + COVER - 1], outline=(60, 60, 62), width=2)
    url(d, BOT - 30)
    return c


def variant_c(a, art):
    """Band: a dithered strip cut from the cover runs edge to edge above
    the type, like a sleeve spine. Dot rail on the right."""
    c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
    strip = square(art, W).crop((0, 0, W, 150))
    c.paste(dither(strip, 180, on=MUTED, off=BG, contrast=1.3), (0, TOP - 10))
    y = header(d, a, TOP + 180)
    cy = max(y + 36, 640)
    c.paste(square(art, 840), ((W - 840) // 2, cy))
    dot_rail(d, a, "right")
    url(d, BOT - 30)
    return c


def variant_d(a, art):
    """Grain: quiet Bayer speckle over the whole ground, cover with a thin
    accent frame, title big. Day as microcopy, right-aligned."""
    c = grain((W, H)); d = ImageDraw.Draw(c)
    microcopy(d, a, TOP + 4, right=True)
    y = header(d, a, TOP + 60)
    cy = max(y + 40, 600)
    c.paste(square(art, COVER), (CX, cy))
    d.rectangle([CX - 12, cy - 12, CX + COVER + 11, cy + COVER + 11], outline=ACCENT, width=2)
    url(d, BOT - 30)
    return c


VARIANTS = {"a": variant_a, "b": variant_b, "c": variant_c, "d": variant_d}


# ── extras: highlight cover + intro slides ───────────────────────────────
def highlight_cover():
    """Profile highlight circles crop to the centre — keep it dead centre."""
    c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
    f = display(520)
    w = f.getlength("40")
    d.text(((W - w) / 2 - 8, H / 2 - 330), "40", font=f, fill=ACCENT)
    t = "ALBUMS"; m = mono(34)
    tracked(d, ((W - tracked_w(t, m, .3)) / 2, H / 2 + 200), t, m, MUTED, .3)
    return c


def intro_1():
    """Title slide, with the site's dithered portrait as the ground."""
    c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
    p = square(Image.open(ROOT / "assets" / "portrait.jpg").convert("RGB"), 700)
    c.paste(dither(p, 96, on=(66, 66, 68), off=BG, contrast=1.25), ((W - 700) // 2, 380))
    tracked(d, (PAD, TOP + 4), "SEP 23 → NOV 1", mono(24), FAINT)
    f = display(112); y = 1090
    for ln, col in (("40 albums,", LIGHT), ("40 days,", ACCENT), ("40 years.", LIGHT)):
        d.text((PAD - 4, y), ln, font=f, fill=col); y += 116
    y += 30
    d.text((PAD, y), "Counting down forty albums that shaped me,", font=sans(34), fill=MUTED)
    d.text((PAD, y + 46), "one a day, before I turn forty.", font=sans(34), fill=MUTED)
    url(d, BOT - 30)
    return c


def intro_2():
    """The 40-cell grid, empty. It's the thing that fills in over 40 days."""
    c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
    tracked(d, (PAD, TOP + 4), "ONE A DAY · IN NO PARTICULAR ORDER", mono(24), FAINT)
    d.text((PAD - 3, TOP + 48), "Day 01 drops Sep 23.", font=display(64), fill=LIGHT)
    cols, rows = 5, 8
    cell, gap = 124, 22
    gw = cols * cell + (cols - 1) * gap
    x0 = (W - gw) // 2; y0 = 440
    for i in range(40):
        r, k = divmod(i, cols)
        x = x0 + k * (cell + gap); y = y0 + r * (cell + gap)
        d.rectangle([x, y, x + cell - 1, y + cell - 1], outline=RULE, width=2)
        d.text((x + 12, y + 8), f"{i + 1:02d}", font=mono(20), fill=FAINT)
    url(d, BOT - 30)
    return c


# ── main ─────────────────────────────────────────────────────────────────
def main():
    args   = sys.argv[1:]
    files  = [a for a in args if a.endswith(".json")]
    data_p = Path(files[0]) if files else ROOT / "data" / "albums.json"
    var    = args[args.index("--variant") + 1] if "--variant" in args else VARIANT
    out    = Path(args[args.index("--out") + 1]) if "--out" in args else ROOT / "out" / "stories"
    slugs  = [args[i + 1] for i, a in enumerate(args) if a == "--slug"]
    out.mkdir(parents=True, exist_ok=True)

    data = json.loads(data_p.read_text())
    for a in data["albums"]:
        if not a.get("no") or not a.get("art"):
            continue
        if slugs and a["slug"] not in slugs:
            continue
        art = Image.open(ROOT / a["art"]).convert("RGB")
        p = out / f'day-{a["no"]:02d}-{a["slug"]}-{var}.png'
        VARIANTS[var](a, art).save(p); print(p)

    if "--extras" in args:
        for name, fn in (("highlight-cover", highlight_cover), ("intro-1", intro_1), ("intro-2", intro_2)):
            p = out / f"{name}.png"; fn().save(p); print(p)


if __name__ == "__main__":
    main()
