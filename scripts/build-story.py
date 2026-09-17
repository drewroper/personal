"""
Render Instagram story graphics (1080x1920) for the /40 countdown.

    python3 scripts/build-story.py [data.json] [--variant a|b|c|d] [--slug x ...]
                                   [--extras] [--out DIR]
                                   [--video [--riff detail-resolve|field|resolve|detail|accent ...] [--seconds 20]]

Reads data/albums.json (or the file given), renders every slotted album —
or just the slugs given — into out/stories/. --extras also renders the
highlight cover, the two intro slides, and the closing grid. --variant picks the layout; the
default is set in VARIANT below once one is chosen.

Layout rules shared by every variant:
  * Instagram covers the top ~250px (progress bar, handle) and bottom
    ~250px (reply bar). Nothing important lives there.
  * Artist above title, title above cover, cover centred.
  * The band under the cover is left open for the link sticker.
  * Day indicator is quiet: microcopy or a 40-dot rail.
"""

import json
import math
import subprocess
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
def edge_text(d, y, text, f, fill):
    """Draw so the glyph's ink starts exactly at PAD, whatever the face's
    side bearing is — one hard left edge across mono, sans and display."""
    d.text((PAD - f.getbbox(text)[0], y), text, font=f, fill=fill)


def edge_tracked(d, y, text, f, fill, em=0.10):
    tracked(d, (PAD - f.getbbox(text[0])[0], y), text, f, fill, em)


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


def breathe(theta):
    """Drift + threshold wobble for one loop of the breathing dither, as
    on the site's OG image. theta runs 0..2π over the loop, so frame N
    and frame 0 meet cleanly."""
    ox = int(round(math.sin(theta) * 6))
    oy = int(round(math.cos(theta) * 6))
    ts = math.sin(theta * 2) * 12
    return ox, oy, ts


_GRAY = {}

def _gray(im, grid, contrast):
    """Shrunk, contrast-stretched luminance for a dither pass. Cached by
    image identity so animated renders don't re-shrink every frame."""
    k = (id(im), grid, contrast)
    if k not in _GRAY or _GRAY[k][0] is not im:
        g = np.array(im.convert("L").resize((grid, int(grid * im.height / im.width)), Image.LANCZOS),
                     dtype=np.float32)
        _GRAY[k] = (im, ((g - 128.0) * contrast + 128.0).clip(0, 255))
        if len(_GRAY) > 64:
            _GRAY.pop(next(iter(_GRAY)))
    return _GRAY[k][1].copy()


def dither(im, grid, on=LIGHT, off=BG, contrast=1.2, theta=None):
    """Two-tone ordered dither at `grid` cells across, scaled back up with
    hard pixels — the site's portrait treatment. theta animates it."""
    g = _gray(im, grid, contrast)
    h, w = g.shape
    th = np.tile(BAYER, (h // 8 + 2, w // 8 + 2))
    if theta is not None:
        ox, oy, ts = breathe(theta)
        th = np.roll(th, (oy, ox), axis=(0, 1))
        g = g - ts
    th = th[:h, :w]
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
    edge_text(d, y, a["artist"], sans(40), MUTED)
    y += 62
    f, lines = fit(a["title"], display, 92, COL, 2, 56)
    for ln in lines:
        edge_text(d, y, ln, f, LIGHT)
        y += int(f.size * 1.02)
    return y + 8


def microcopy(d, a, y, right=False):
    text = f'DAY {a["no"]:02d} / 40'
    f = mono(24)
    if right:
        tracked(d, (W - PAD - tracked_w(text, f), y), text, f, ACCENT)
    else:
        edge_tracked(d, y, text, f, ACCENT)


def url(d, y):
    edge_tracked(d, y, "DREWROPER.COM/40", mono(24), ACCENT)


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
COVER = W - PAD * 2   # 912 — cover shares the type's left edge
CX    = PAD

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


GROUND = (34, 34, 36)          # dim bone — the ground dither's "on" tone
GROUND_ACCENT = (56, 66, 20)   # the same, pulled toward the accent


_CACHE = {}

def _prep(art, key, fn):
    """Per-album prep cache. The image object is stored alongside so its
    id() can't be recycled by a later album and hand back stale work."""
    k = (id(art), key)
    if k not in _CACHE or _CACHE[k][0] is not art:
        _CACHE[k] = (art, fn())
    return _CACHE[k][1]


def reset_caches():
    _CACHE.clear(); _GRAY.clear()


def _ground(art, theta, riff):
    """Full-frame dithered ground for the B family."""
    if "detail" in riff:
        # A 3x detail of the cover, drifting on a small circle so it loops.
        # Pre-shrunk to the dither grid's scale so the crop + dither is cheap.
        big = _prep(art, "big3", lambda: square(art, W * 3))
        t = theta or 0.0
        cx = W + int(math.cos(t) * 90); cy = (W * 3 - H) // 2 + int(math.sin(t) * 90)
        src = big.crop((cx, cy, cx + W, cy + H))
    else:
        src = _prep(art, "field", lambda: (lambda b: (lambda s_: (s_.paste(b, (0, (H - W) // 2)), s_)[1])(Image.new("RGB", (W, H), BG)))(square(art, W)))
    tone = GROUND_ACCENT if "accent" in riff else GROUND
    return dither(src, 135, on=tone, off=BG, contrast=1.4, theta=theta)


REVEAL_STEPS = (16, 32, 64, 128, 256)   # dither cells across the cover, coarse → fine
STEP_HOLD    = 0.022                     # fraction of the loop per step
SNAP         = 0.020                     # fraction of the loop for the final fade to color
SINK_AT      = 0.90                      # where the reverse begins


def _reveal(cover, theta):
    """The cover resolves out of its own dither in hard steps — each step
    halves the cell size, so it's one-bit the whole way and never mushy.
    Only the last step fades, briefly, to color. Reverses at loop end."""
    u = theta / (2 * math.pi)
    n = len(REVEAL_STEPS)
    rise = n * STEP_HOLD + SNAP
    if u < rise:
        k = u / STEP_HOLD
    elif u > SINK_AT:
        k = (1 - u) / (1 - SINK_AT) * rise / STEP_HOLD
    else:
        return cover
    if k < n:
        grid = REVEAL_STEPS[int(k)]
        return dither(cover, grid, on=LIGHT, off=BG, contrast=1.2, theta=theta)
    fine = dither(cover, REVEAL_STEPS[-1], on=LIGHT, off=BG, contrast=1.2, theta=theta)
    x = min(1.0, (k - n) * STEP_HOLD / SNAP)
    return Image.blend(fine, cover, x * x * (3 - 2 * x))


def variant_b(a, art, theta=None, riff="field"):
    """Field: the cover itself, blown up and dithered dim, is the ground
    behind everything, breathing. Riffs: field (base), resolve (cover
    emerges from its own dither), detail (zoomed drifting ground),
    accent (ground dither tinted toward the accent)."""
    c = _ground(art, theta, riff); d = ImageDraw.Draw(c)
    microcopy(d, a, TOP + 4)
    y = header(d, a, TOP + 60)
    cy = max(y + 36, 580)
    cover = _prep(art, "cover", lambda: square(art, COVER))
    if "resolve" in riff and theta is not None:
        cover = _reveal(cover, theta)
    c.paste(cover, (CX, cy))
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


def grid_card(albums, through=0, headline="", eyebrow="ONE A DAY · IN NO PARTICULAR ORDER"):
    """The 40-cell grid. Cells through `through` show that day's cover;
    the rest stay empty. through=0 is the intro card, 40 is the closer."""
    c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
    tracked(d, (PAD, TOP + 4), eyebrow, mono(24), FAINT)
    if headline:
        d.text((PAD - 3, TOP + 48), headline, font=display(64), fill=LIGHT)
    by_no = {a["no"]: a for a in albums if a.get("no") and a.get("art")}
    cols, rows = 5, 8
    cell, gap = 124, 22
    gw = cols * cell + (cols - 1) * gap
    x0 = (W - gw) // 2; y0 = 440
    for i in range(40):
        r, k = divmod(i, cols)
        x = x0 + k * (cell + gap); y = y0 + r * (cell + gap)
        a = by_no.get(i + 1)
        if a and i + 1 <= through:
            art = Image.open(ROOT / a["art"]).convert("RGB")
            c.paste(square(art, cell), (x, y))
        else:
            d.rectangle([x, y, x + cell - 1, y + cell - 1], outline=RULE, width=2)
            d.text((x + 12, y + 8), f"{i + 1:02d}", font=mono(20), fill=FAINT)
    url(d, BOT - 30)
    return c


def intro_2(albums):
    return grid_card(albums, 0, "40 albums, 40 days.")


def closing(albums):
    return grid_card(albums, 40, "That's forty.", "SEP 23 → NOV 1 · ALL FORTY")


# ── video ────────────────────────────────────────────────────────────────
def ffmpeg_bin():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def render_video(frame_fn, out_path, seconds=10, fps=30):
    """Pipe frames straight into ffmpeg. frame_fn(theta) -> PIL image."""
    n = seconds * fps
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
           "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(frame_fn(2 * math.pi * i / n).tobytes())
    proc.stdin.close(); proc.wait()
    if proc.returncode:
        raise SystemExit(f"ffmpeg failed on {out_path}")


# ── main ─────────────────────────────────────────────────────────────────
def main():
    args   = sys.argv[1:]
    files  = [a for a in args if a.endswith(".json")]
    data_p = Path(files[0]) if files else ROOT / "data" / "albums.json"
    var    = args[args.index("--variant") + 1] if "--variant" in args else VARIANT
    out    = Path(args[args.index("--out") + 1]) if "--out" in args else ROOT / "out" / "stories"
    slugs  = [args[i + 1] for i, a in enumerate(args) if a == "--slug"]
    riffs  = [args[i + 1] for i, a in enumerate(args) if a == "--riff"] or ["detail-resolve"]
    out.mkdir(parents=True, exist_ok=True)

    data = json.loads(data_p.read_text())
    for a in data["albums"]:
        if not a.get("no") or not a.get("art"):
            continue
        if slugs and a["slug"] not in slugs:
            continue
        art = Image.open(ROOT / a["art"]).convert("RGB")
        reset_caches()
        if "--video" in args:
            secs = int(args[args.index("--seconds") + 1]) if "--seconds" in args else 20
            for riff in riffs:
                p = out / f'day-{a["no"]:02d}-{a["slug"]}-b-{riff}.mp4'
                render_video(lambda th: variant_b(a, art, th, riff), p, secs); print(p)
        else:
            p = out / f'day-{a["no"]:02d}-{a["slug"]}-{var}.png'
            VARIANTS[var](a, art).save(p); print(p)

    if "--extras" in args:
        albums = data["albums"]
        for name, im in (("highlight-cover", highlight_cover()), ("intro-1", intro_1()),
                         ("intro-2", intro_2(albums)), ("closing", closing(albums))):
            p = out / f"{name}.png"; im.save(p); print(p)


if __name__ == "__main__":
    main()
