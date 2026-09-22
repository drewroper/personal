#!/usr/bin/env python3
"""Per-record sleeve wear. Every album gets its own history, seeded by slug: whether it
has ring wear (and how the disc sat), a second ring from an inner sleeve, shelf wear on
the top edge, blunted corners with creases, a seam split, a price-sticker ghost,
directional scuffs, hairlines, foxing and grime — and how hard a life it has had.

Output: assets/40/wear/<slug>.webp, an RGBA overlay to lay over the cover with normal
blending: exposed paper fibres (near-white) and grime (near-black) in one image.

Usage: scripts/make-wear.py [--size 900] [--only slug,slug] [--force] [--preview]
"""
import sys, math, json, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
args = sys.argv[1:]
S = int(args[args.index('--size') + 1]) if '--size' in args else 900
ONLY = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
FORCE = '--force' in args
OUT = ROOT / 'assets/40/wear'; OUT.mkdir(parents=True, exist_ok=True)

def blur(a, r):
    if r <= 0: return a
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255

def make(slug, year=None):
    seed = int(hashlib.sha1(slug.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    U = rng.uniform; P = lambda p: rng.random() < p

    def noise(scale, octaves=3, gain=.5):
        out = np.zeros((S, S), np.float32); amp = 1; tot = 0; sc = scale
        for _ in range(octaves):
            n = rng.random((max(2, S // sc), max(2, S // sc))).astype(np.float32)
            n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)).astype(np.float32) / 255
            out += n * amp; tot += amp; amp *= gain; sc = max(2, sc // 2)
        return out / tot

    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    # How hard a life: older records have been played and shelved for decades, newer ones barely.
    age = (2026 - int(str(year)[:4])) if year else 20
    life = float(np.clip(.2 + (age / 40) ** 1.6 * 1.2 + U(-.1, .1), .18, 1.45))   # steep: 2005 ≈ half of 1995
    fibre = (0.35 + 0.65 * noise(2, 2, .6)) * (0.7 + 0.6 * (noise(2, 1) > .45))   # paper fibre: high frequency, partly binary
    light = np.zeros((S, S), np.float32); dark = np.zeros((S, S), np.float32)

    # Ring wear: the disc's edge abrading the print. Never a compass circle: the radius wobbles
    # as the disc shifted, the band's width varies, and the wear only covers one to three arcs,
    # heaviest where the disc rested (usually low, from gravity) and broken up elsewhere.
    def arc_cover(ang, n, rest):
        cover = np.zeros_like(ang)
        for i in range(n):
            c = rest + (U(-.6, .6) if i == 0 else U(-math.pi, math.pi)); span = U(.6, 3.6) if i == 0 else U(.4, 2.2)
            d = np.abs(((ang - c + math.pi) % (2 * math.pi)) - math.pi)
            cover += np.clip(1 - (d - span / 2) / (span * .3), 0, 1) * (1 if i == 0 else U(.4, .9))
        return np.clip(cover, 0, 1)
    if P(.35 + .5 * min(1, age / 35)):
        cx, cy = S * U(.46, .54), S * U(.47, .55); R0 = S * U(.42, .47)
        r = np.hypot(xx - cx, yy - cy); ang = np.arctan2(yy - cy, xx - cx)
        ph1, ph2, ph3 = U(0, 6.28), U(0, 6.28), U(0, 6.28)
        R = R0 * (1 + U(.01, .035) * np.sin(ang + ph1) + U(.005, .02) * np.sin(3 * ang + ph2))
        w = S * U(.01, .03) * (.55 + .9 * (.5 + .5 * np.sin(2 * ang + ph3)))
        band = np.exp(-((r - R) / w) ** 2) + .3 * np.exp(-((r - R) / (w * 2.8)) ** 2)
        rest = U(math.pi * .15, math.pi * .85) if P(.7) else U(0, 2 * math.pi)   # low on the sleeve, mostly
        lobe = .25 + .75 * (.5 + .5 * np.cos(ang - rest)) ** U(1, 2.5)
        cover = arc_cover(ang, int(U(1, 4)), rest) * (.35 + .65 * noise(60))
        mottle = (.4 + noise(24) * 1.0) * (noise(3, 2) > U(.3, .5))
        ring = band * lobe * cover * mottle
        light += blur(ring, .5) * U(.9, 1.4)
        dark += np.exp(-((r - R * 1.035) / (w * 1.5)) ** 2) * lobe * cover * (.3 + noise(40) * .6) * U(.15, .4)
        if P(.3):                                                        # a second, offset arc from an inner sleeve
            R2 = R0 * U(.92, .99); cx2, cy2 = cx + S * U(-.04, .04), cy + S * U(-.04, .04)
            r2 = np.hypot(xx - cx2, yy - cy2); ang2 = np.arctan2(yy - cy2, xx - cx2)
            light += blur(np.exp(-((r2 - R2) / (w * .8)) ** 2) * arc_cover(ang2, int(U(1, 3)), U(0, 6.28)) * (.3 + noise(26) * .7) * (noise(3, 2) > .35), .6) * U(.3, .7)
        if P(.35):                                                       # faint spindle/label arc
            light += np.exp(-((r - S * U(.15, .19)) / (S * .01)) ** 2) * arc_cover(ang, 1, U(0, 6.28)) * noise(24) * U(.15, .35)

    # Edge whitening: ink chipping off the folded edges. Top edge often worse (shelf wear).
    dl, dr_, dt, db = xx, S - 1 - xx, yy, S - 1 - yy
    wts = [U(.4, 1), U(.4, 1), U(.6, 1.6) if P(.5) else U(.4, 1), U(.4, 1)]
    edge = np.zeros_like(light)
    for d, wt in zip([dl, dr_, dt, db], wts):
        edge += np.exp(-d / (S * U(.006, .02))) * wt
    edge = edge * (.4 + noise(12) * 1.1) * (noise(2, 2) > U(.3, .5))
    light += blur(edge, .4) * U(.9, 1.4)

    # Corners: blunted, with creases fanning out of the worst ones.
    corners = [(0, 0), (S, 0), (0, S), (S, S)]
    for (px, py) in corners:
        if P(.7):
            rad = S * U(.03, .09); k = U(.4, 1.2)
            c = np.exp(-np.hypot(xx - px, yy - py) / rad) * (.5 + noise(16) * .9) * k
            light += blur(c, 1.0)
            dark += np.exp(-np.hypot(xx - px, yy - py) / (rad * 1.6)) * (.4 + noise(22) * .6) * k * .35
            if P(.45):
                im = Image.new('L', (S, S), 0); d = ImageDraw.Draw(im)
                for _ in range(int(U(1, 4))):
                    a = math.atan2((S / 2 - py), (S / 2 - px)) + U(-.7, .7); L = S * U(.08, .3)
                    d.line([(px, py), (px + math.cos(a) * L, py + math.sin(a) * L)], fill=int(U(120, 220)), width=int(U(1, 3)))
                light += blur(np.asarray(im).astype(np.float32) / 255, .8) * .8

    # Seam split: a jagged white tear along one edge.
    if P(.32):
        side = int(U(0, 4)); im = Image.new('L', (S, S), 0); d = ImageDraw.Draw(im)
        L = S * U(.25, 1.0); start = U(0, S - L); pts = []
        for i in range(30):
            t = start + L * i / 29; off = U(0, S * .012)
            pts.append((t, off) if side == 0 else (t, S - 1 - off) if side == 1 else (off, t) if side == 2 else (S - 1 - off, t))
        d.line(pts, fill=230, width=int(U(2, 6)))
        light += blur(np.asarray(im).astype(np.float32) / 255, 1.2) * 1.2

    # Price sticker ghost: a pale patch with darker residue at its edge.
    if P(.35):
        px, py = rng.choice(corners); px += (S * U(.08, .18)) * (1 if px == 0 else -1); py += (S * U(.08, .18)) * (1 if py == 0 else -1)
        w_, h_ = S * U(.07, .12), S * U(.05, .09)
        im = Image.new('L', (S, S), 0); d = ImageDraw.Draw(im)
        if P(.5): d.rounded_rectangle([px - w_ / 2, py - h_ / 2, px + w_ / 2, py + h_ / 2], radius=S * .01, fill=255)
        else: d.ellipse([px - w_ / 2, py - w_ / 2, px + w_ / 2, py + w_ / 2], fill=255)
        st = np.asarray(im).astype(np.float32) / 255
        light += blur(st, 1.5) * (.12 + noise(10) * .2)
        dark += (blur(st, 2.5) - blur(st, .6)).clip(0, 1) * .8 * (.5 + noise(8) * .6)

    # Scuffs: directional streaks, and soft pale patches.
    for _ in range(int(U(2, 7))):
        a = U(0, math.pi); px, py = U(0, S), U(0, S); Lx, Ly = S * U(.08, .3), S * U(.02, .07)
        ux, uy = (xx - px) * math.cos(a) + (yy - py) * math.sin(a), -(xx - px) * math.sin(a) + (yy - py) * math.cos(a)
        light += np.exp(-((ux / Lx) ** 2 + (uy / Ly) ** 2)) * noise(8) * U(.15, .45)
    # Hairlines
    im = Image.new('L', (S, S), 0); d = ImageDraw.Draw(im)
    for _ in range(int(U(8, 90) * life)):
        L = U(S * .03, S * .5); a = U(0, math.pi); x0, y0 = U(0, S), U(0, S)
        d.line([(x0, y0), (x0 + math.cos(a) * L, y0 + math.sin(a) * L)], fill=int(U(70, 230)), width=int(rng.choice([1, 1, 1, 2])))
    light += blur(np.asarray(im).astype(np.float32) / 255, .5) * .9
    # Speckle
    light += blur((rng.random((S, S)) > 1 - .002 * life).astype(np.float32), .5) * 2

    # Grime: clouds, foxing spots, dirt specks.
    for _ in range(int(U(2, 6))):
        px, py = U(0, S), U(0, S); rad = S * U(.08, .28)
        dark += np.exp(-np.hypot(xx - px, yy - py) / rad) * U(.05, .18) * noise(14)
    if P(.5):
        for _ in range(int(U(3, 20))):
            px, py = U(0, S), U(0, S); rad = S * U(.003, .01)
            dark += np.exp(-(np.hypot(xx - px, yy - py) / rad) ** 2) * U(.3, .7)
    dark += (rng.random((S, S)) > 1 - .0006 * life).astype(np.float32) * .9

    light = np.clip((light * life * fibre) ** .8 * 1.25, 0, 1); dark = np.clip(blur(dark, .6) * life, 0, .85)
    # Compose one RGBA overlay for normal blending: grime over fibres.
    a_l = light; a_d = dark
    rgb_l = np.array([238, 234, 226], np.float32); rgb_d = np.array([22, 20, 18], np.float32)
    A = a_d + a_l * (1 - a_d)
    rgb = (rgb_d[None, None] * a_d[..., None] + rgb_l[None, None] * (a_l * (1 - a_d))[..., None]) / np.maximum(A[..., None], 1e-4)
    out = np.dstack([rgb.clip(0, 255).astype(np.uint8), (A * 255).astype(np.uint8)])
    return Image.fromarray(out, 'RGBA'), dict(life=float(life), age=age)

albums = json.loads((ROOT / 'data/albums.json').read_text())['albums']
for a in albums:
    slug = a['slug']
    if ONLY and slug not in ONLY: continue
    dst = OUT / f'{slug}.webp'
    if dst.exists() and not FORCE: continue
    im, meta = make(slug, a.get('year'))
    im.save(dst, 'WEBP', quality=68, method=6)
    print(f'{slug:52} {a.get("year")} life={meta["life"]:.2f} {dst.stat().st_size // 1024}KB', flush=True)
