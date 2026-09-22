#!/usr/bin/env python3
"""Per-record sleeve wear, built to read like a photograph of a real sleeve.

Two outputs in assets/40/wear/:
  paper.webp     one shared, tileable paper-stock texture (grain plus fibres). The page
                 lays it over every cover at a fixed physical scale, so every sleeve reads
                 as printed card rather than a digital file.
  <slug>.webp    that record's own wear, as a crisp RGBA overlay at 1200px: a hard, chipped
                 edge band concentrated on the cut edge, heavier at the corners; a thin,
                 broken ring where the disc rubbed; fine hairline scratches and rub marks.

Every record is seeded by its slug. Older records wear harder. Dark covers wear as
exposed paper (light); light covers wear as handling dirt (grey) and lean on the paper
texture and a faint age tone instead. No blur passes, no clouds, no speckle.

It also writes each album's paper strength to data/albums.json as `wear.paper`.

Usage: scripts/make-wear.py [--size 1200] [--only slug,slug] [--force] [--jobs 4]
"""
import sys, math, json, hashlib
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets/40/wear'
args = sys.argv[1:]
S = int(args[args.index('--size') + 1]) if '--size' in args else 1200
ONLY = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
FORCE = '--force' in args
JOBS = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4

WHITE = np.array([246, 243, 236], np.float32)   # exposed paper
DIRT = np.array([28, 26, 24], np.float32)       # handling grime, near-neutral
TONE = np.array([236, 222, 190], np.float32)    # age yellowing on light stock


def over(rgb, a, color, alpha):
    """Composite a flat colour at per-pixel alpha over a premultiplied RGBA pair, in place."""
    alpha = np.clip(alpha, 0, 1)[..., None]
    rgb *= (1 - alpha); rgb += color[None, None] * alpha
    a *= (1 - alpha[..., 0]); a += alpha[..., 0]


def fbm(rng, n, cell, octaves=3, gain=.5):
    """Smooth value noise in [0,1] at float precision (no 8-bit banding)."""
    out = np.zeros((n, n), np.float32); amp, tot, c = 1., 0., cell
    for _ in range(octaves):
        g = max(2, int(n / c) + 1)
        v = Image.fromarray(rng.random((g, g)).astype(np.float32), 'F').resize((n, n), Image.BICUBIC)
        out += np.asarray(v) * amp; tot += amp; amp *= gain; c = max(2, c / 2)
    return np.clip(out / tot, 0, 1)


def noise1(rng, n, cell, octaves=4, gain=.55):
    x = np.arange(n, dtype=np.float32); out = np.zeros(n, np.float32); amp, tot, c = 1., 0., cell
    for _ in range(octaves):
        k = int(n / c) + 2
        out += np.interp(x / c, np.arange(k), rng.random(k)) * amp; tot += amp; amp *= gain; c = max(2, c / 2)
    return out / tot


# ── Shared paper stock ─────────────────────────────────────────────────────
def paper_tile(T=512, seed=40):
    rng = np.random.default_rng(seed)
    fy, fx = np.fft.fftfreq(T)[:, None], np.fft.fftfreq(T)[None, :]
    def band(sig):  # periodic gaussian-filtered noise, so the tile wraps seamlessly
        g = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((T, T))) * np.exp(-2 * (np.pi * sig) ** 2 * (fx ** 2 + fy ** 2))))
        return (g / g.std()).astype(np.float32)
    grain = .65 * band(.5) + .35 * band(2.2)
    def fibres(count, lo, hi):
        big = Image.new('L', (3 * T, 3 * T), 0); d = ImageDraw.Draw(big)
        for _ in range(count):
            x, y = T + rng.uniform(0, T), T + rng.uniform(0, T); a = rng.uniform(0, math.pi); L = rng.uniform(3, 16)
            d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=int(rng.uniform(lo, hi)), width=1)
        arr = np.asarray(big).astype(np.float32) / 255
        return np.clip(sum(arr[i * T:(i + 1) * T, j * T:(j + 1) * T] for i in range(3) for j in range(3)), 0, 1)
    fl, fd = fibres(T * T // 170, 50, 170), fibres(T * T // 200, 50, 160)
    rgb = np.zeros((T, T, 3), np.float32); a = np.zeros((T, T), np.float32)
    over(rgb, a, WHITE, .022 + np.clip(grain, 0, None) * .03 + fl * .05)   # lifted blacks, light grain, pale fibres
    over(rgb, a, DIRT, np.clip(-grain, 0, None) * .03 + fd * .05)           # dark grain, dark fibres
    rgb = rgb / np.maximum(a[..., None], 1e-4)
    Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), (a * 255).astype(np.uint8)]), 'RGBA').save(OUT / 'paper.webp', 'WEBP', quality=88, method=6)


# ── One record ─────────────────────────────────────────────────────────────
def make(job):
    slug, year, art = job
    rng = np.random.default_rng(int(hashlib.sha1(slug.encode()).hexdigest()[:8], 16))
    U = rng.uniform; P = lambda p: rng.random() < p
    age = (2026 - int(str(year)[:4])) if year else 20
    life = float(np.clip(.2 + (age / 40) ** 1.6 * 1.2 + U(-.1, .1), .18, 1.45))
    lum = .35
    if art and (ROOT / art).exists():
        lum = float(np.asarray(Image.open(ROOT / art).convert('L').resize((64, 64))).mean() / 255)
    light = lum > .62

    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    wear = np.zeros((S, S), np.float32)      # where the print is worn; coloured by cover tone below

    # Edge band: a hard, chipped line on the cut edge. Width follows a 1-D profile along
    # each side, with chips, a worn seam on some, and more wear toward the corners.
    def profile():
        n = S; t = np.arange(n, dtype=np.float32)
        base = S * U(.0016, .0032) * (.45 + life)
        prof = base * (.2 + 1.3 * noise1(rng, n, S * .07) ** 2)
        for _ in range(int(U(1, 7) * life)):
            c, w = U(0, n), U(S * .003, S * .025)
            prof += base * U(1.2, 3) * np.exp(-((t - c) / w) ** 2)
        if P(.22 * life):
            c, w = U(.2, .8) * n, U(.08, .25) * n
            prof += base * U(.5, 1.1) * np.exp(-((t - c) / w) ** 4)
        k = U(.8, 2.4)
        prof *= 1 + k * (np.exp(-t / (S * .03)) + np.exp(-(n - 1 - t) / (S * .03)))
        return prof
    shelf = U(1.2, 1.8) if P(.5) else 1.0
    top, bot, lef, rig = profile() * shelf, profile(), profile(), profile()
    xi = xx.astype(np.int32); yi = yy.astype(np.int32)
    edge = np.maximum.reduce([
        np.clip(top[xi] - yy + .5, 0, 1), np.clip(bot[xi] - (S - 1 - yy) + .5, 0, 1),
        np.clip(lef[yi] - xx + .5, 0, 1), np.clip(rig[yi] - (S - 1 - xx) + .5, 0, 1)])
    chips = np.clip((fbm(rng, S, 3, 2) - U(.28, .4)) * 7, 0, 1)            # ink flaking inside the band: crisp, broken
    outer = np.clip(1.6 - np.minimum.reduce([xx, yy, S - 1 - xx, S - 1 - yy]), 0, 1) * U(.5, .9)   # the cut edge itself
    wear = np.maximum(wear, np.maximum(edge * chips, outer * min(1, .4 + life)))

    # Ring wear: thin (2–5px), close to the edge, broken, strongest where the disc rested.
    if P(.15 + .5 * min(1, age / 35)):
        cx, cy = S * U(.49, .51), S * U(.495, .515); R0 = S * U(.462, .485)
        r = np.hypot(xx - cx, yy - cy); ang = np.arctan2(yy - cy, xx - cx)
        ph = [U(0, 6.28) for _ in range(3)]
        R = R0 * (1 + U(.003, .01) * np.sin(ang + ph[0]) + U(.002, .006) * np.sin(2 * ang + ph[1]))
        w = S * U(.0017, .0038) * (.6 + .8 * (.5 + .5 * np.sin(3 * ang + ph[2])))
        band = np.clip(1 - np.abs(r - R) / w, 0, 1)
        rest = U(math.pi * .15, math.pi * .85) if P(.7) else U(0, 2 * math.pi)
        lobe = .25 + .75 * (.5 + .5 * np.cos(ang - rest)) ** U(1, 2.5)
        cover = np.zeros_like(ang)
        for i in range(int(U(1, 4))):
            c = rest + (U(-.6, .6) if i == 0 else U(-math.pi, math.pi)); span = U(.8, 3.6) if i == 0 else U(.4, 2)
            dd = np.abs(((ang - c + math.pi) % (2 * math.pi)) - math.pi)
            cover = np.maximum(cover, np.clip(1 - (dd - span / 2) / (span * .25), 0, 1) * (1 if i == 0 else U(.4, .9)))
        fine = fbm(rng, S, 2.5, 2); coarse = fbm(rng, S, S * .02, 2)          # grain along the ring, and where it thins out
        abr = np.clip((fine * .55 + coarse * .45 - U(.36, .46)) * 3.2, 0, 1) * np.clip((coarse - .25) * 2.5, 0, 1)
        prof = band ** U(.6, 1.4)
        wear = np.maximum(wear, prof * lobe * cover * abr * U(.55, .9) * min(1, .45 + life))

    # Hairlines and rub marks, drawn at 2x and downsampled for crisp 1px anti-aliased lines.
    SS = 2; cv = Image.new('L', (S * SS, S * SS), 0); d = ImageDraw.Draw(cv)
    for _ in range(int(U(3, 16) * life)):
        L = S * math.exp(U(math.log(.03), math.log(.4))); a = U(0, math.pi)
        x0, y0 = U(0, S), U(0, S); x1, y1 = x0 + math.cos(a) * L, y0 + math.sin(a) * L
        bend = U(-.06, .06) * L; mx, my = (x0 + x1) / 2 - math.sin(a) * bend, (y0 + y1) / 2 + math.cos(a) * bend
        peak = U(70, 170) if P(.85) else U(170, 235)
        gaps = [(g, g + U(.03, .12)) for g in rng.uniform(.1, .9, int(U(0, 3)))]
        segs = 28
        for i in range(segs):
            t0, t1 = i / segs, (i + 1) / segs
            if any(g0 < t0 < g1 for g0, g1 in gaps): continue
            q = lambda t: ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1)
            p0, p1 = q(t0), q(t1)
            v = peak * math.sin(math.pi * (t0 + t1) / 2) ** .5
            d.line([(p0[0] * SS, p0[1] * SS), (p1[0] * SS, p1[1] * SS)], fill=int(v), width=2)
    for _ in range(int(U(0, 3.5) * life)):                                   # rub marks: short parallel strokes in a patch
        cx, cy = U(.1, .9) * S, U(.1, .9) * S; a = U(0, math.pi); rx, ry = S * U(.03, .09), S * U(.015, .04)
        for _k in range(int(U(15, 55))):
            t = U(0, 2 * math.pi); rr = math.sqrt(U(0, 1))
            px = cx + rr * rx * math.cos(t) * math.cos(a) - rr * ry * math.sin(t) * math.sin(a)
            py = cy + rr * rx * math.cos(t) * math.sin(a) + rr * ry * math.sin(t) * math.cos(a)
            L = U(4, 22); aa = a + U(-.05, .05)
            d.line([(px * SS, py * SS), ((px + math.cos(aa) * L) * SS, (py + math.sin(aa) * L) * SS)], fill=int(U(40, 110)), width=1)
    marks = np.asarray(cv.resize((S, S), Image.BOX)).astype(np.float32) / 255

    rgb = np.zeros((S, S, 3), np.float32); A = np.zeros((S, S), np.float32)
    if light:
        # Light stock: a faint age tone heavier toward the edges, and wear as grey handling dirt.
        if age > 15:
            dmin = np.minimum.reduce([xx, yy, S - 1 - xx, S - 1 - yy])
            over(rgb, A, TONE, min(.07, age / 800) + .05 * np.exp(-dmin / (S * .05)) * min(1, age / 40))
        over(rgb, A, DIRT, np.maximum(wear * .42, marks * .1))            # scratches barely register on light stock
        paper = 1.0
    else:
        over(rgb, A, WHITE, np.maximum(wear, marks) * .95)
        paper = .6 + .3 * lum
    rgb = rgb / np.maximum(A[..., None], 1e-4)
    Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), (A * 255).astype(np.uint8)]), 'RGBA').save(OUT / f'{slug}.webp', 'WEBP', quality=84, method=6)
    return slug, year, round(life, 2), round(lum, 2), light, round(paper, 2)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    data_path = ROOT / 'data/albums.json'
    doc = json.loads(data_path.read_text())
    if FORCE or not (OUT / 'paper.webp').exists():
        paper_tile(); print('paper.webp', (OUT / 'paper.webp').stat().st_size // 1024, 'KB')
    jobs = [(a['slug'], a.get('year'), a.get('art')) for a in doc['albums']
            if (not ONLY or a['slug'] in ONLY) and (FORCE or not (OUT / f"{a['slug']}.webp").exists())]
    with Pool(JOBS) as pool:
        results = pool.map(make, jobs)
    paper = {}
    for slug, year, life, lum, light, pp in results:
        paper[slug] = pp
        print(f'{slug:52} {year} life={life:.2f} lum={lum:.2f} {"light" if light else "dark "} paper={pp:.2f} {(OUT / f"{slug}.webp").stat().st_size // 1024}KB')
    doc = json.loads(data_path.read_text())                                  # re-read: don't clobber edits made meanwhile
    for a in doc['albums']:
        if a['slug'] in paper: a.setdefault('wear', {})['paper'] = paper[a['slug']]
    data_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
