#!/usr/bin/env python3
"""Sleeve wear: every record's own history, built to read like a scan of a real,
well-played sleeve (calibrated against scans of worn black sleeves).

For each album a wear mask (0..1, how far the print has worn through) is built from:
  - the cut edge: a thin, continuous pale line with chips, heavier toward the corners
  - ring wear, where the disc pressed through the sleeve: a thin granular ring and/or a
    broad band of abrasion that streaks along the turn, strongest where the disc rested
    and broken elsewhere, with a faint sheen; rub streaks at the bottom and top; on some,
    a faint ring at the label's edge
  - creases: fine, wavy cracks at dog-eared corners and along the seam side
  - slide scratches in one prevailing direction, a few hairlines and rub marks; the worn
    cut edge shows the card beneath; on the oldest sleeves, a small tear
Older records carry more of all of it. The seed is the slug, so no two sleeves match.

The mask is baked onto the cover per pixel: over dark ink the wear shows as exposed pale
paper, over light ink as grey grime, so white sleeves wear like white sleeves. A shared
paper-grain tile and a faint scanner-lamp falloff finish it.

Outputs
  assets/40/worn/<slug>.jpg        the sleeve every surface uses (site, grid, stories): art_worn
  assets/40/worn/<slug>-back.jpg   the back, squared, with the same wear mirrored: art_back_worn
Strength comes from the album's wear.level: low | med | high (default med).

Usage: scripts/make-wear.py [--only slug,slug] [--jobs 4] [--levels DIR]
  --levels DIR   also bake low/med/high and the clean art at 1000px into DIR (for the picker)
"""
import sys, math, json, hashlib
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MASKS = ROOT / 'out/wear-masks'           # build intermediates (gitignored)
WORN = ROOT / 'assets/40/worn'
PAPER_TILE = ROOT / 'assets/40/wear/paper.webp'
S = 1200
LEVELS = {'low': (.6, .8, .72), 'med': (1.0, 1.0, .85), 'high': (1.4, 1.25, 1.0)}   # (abrasion amount, edge width, strength)
args = sys.argv[1:]
ONLY = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
JOBS = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4
LEVELS_DIR = Path(args[args.index('--levels') + 1]) if '--levels' in args else None

PAPER_WHITE = np.array([243, 239, 229], np.float32) / 255    # exposed paper under dark ink
GRIME = np.array([118, 112, 102], np.float32) / 255          # how the same wear reads on light ink
WARM = np.array([1.0, .955, .86], np.float32)                # age tone on old light sleeves
BOARD = np.array([214, 200, 176], np.float32) / 255           # the card under a worn edge
BOARD_DIRTY = np.array([150, 138, 118], np.float32) / 255     # the same edge on a light sleeve


def fbm(rng, n, cell, octaves=3, gain=.5):
    """Smooth value noise in [0,1] at float precision."""
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


def uniform(x):
    """Rank-normalise to a uniform [0,1] field, so a density d switches on about d of the pixels."""
    flat = x.ravel(); idx = np.argsort(flat, kind='stable')
    out = np.empty_like(flat); out[idx] = np.linspace(0, 1, flat.size, dtype=np.float32)
    return out.reshape(x.shape)


def polar_noise(rng, r, ang, R0, cell_r, cell_t, octaves=3):
    """Value noise on a (radius, arc-length) lattice, periodic around the circle, so abrasion
    near the ring streaks along the direction the disc turns rather than in random blobs."""
    out = np.zeros(r.shape, np.float32); amp, tot = 1., 0.
    for _ in range(octaves):
        nv = max(4, int(round(2 * math.pi * R0 / cell_t))); nu = int(r.max() / cell_r) + 3
        G = rng.random((nu, nv)).astype(np.float32)
        u = r / cell_r; v = (ang + math.pi) / (2 * math.pi) * nv
        u0 = np.floor(u).astype(np.int32); v0 = np.floor(v).astype(np.int32)
        fu = u - u0; fv = v - v0; fu = fu * fu * (3 - 2 * fu); fv = fv * fv * (3 - 2 * fv)
        u1 = np.minimum(u0 + 1, nu - 1); u0 = np.minimum(u0, nu - 1); v0 %= nv; v1 = (v0 + 1) % nv
        out += (G[u0, v0] * (1 - fu) * (1 - fv) + G[u1, v0] * fu * (1 - fv) + G[u0, v1] * (1 - fu) * fv + G[u1, v1] * fu * fv) * amp
        tot += amp; amp *= .5; cell_r = max(1., cell_r / 2); cell_t = max(2., cell_t / 2)
    return out / tot


def aniso(rng, cell_x, cell_y, octaves=2):
    """Value noise stretched along one axis: streaks that run with the rubbing."""
    out = np.zeros((S, S), np.float32); amp, tot = 1., 0.
    for _ in range(octaves):
        gx, gy = max(2, int(S / cell_x) + 1), max(2, int(S / cell_y) + 1)
        out += np.asarray(Image.fromarray(rng.random((gy, gx)).astype(np.float32), 'F').resize((S, S), Image.BICUBIC)) * amp
        tot += amp; amp *= .5; cell_x = max(1.5, cell_x / 2); cell_y = max(1.5, cell_y / 2)
    return out / tot


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


def crease(d, rng, x, y, heading, length, bright, width, branch=True):
    """A fold crack: a thin line whose heading drifts gently, tapering at both ends, with the
    odd break and short side branch. Drawn on a 2x canvas."""
    step = 2.5; n = max(2, int(length / step)); turn = 0.0
    for i in range(n):
        turn = turn * .9 + rng.normal(0, .045)
        heading += turn * .35
        nx, ny = x + math.cos(heading) * step, y + math.sin(heading) * step
        t = i / n; env = min(1.0, t * 5 + .15, (1 - t) * 3 + .1)
        if rng.random() > .035:
            v = bright * env * (.6 + .4 * rng.random())
            d.line([(x * 2, y * 2), (nx * 2, ny * 2)], fill=int(255 * min(1.0, v)), width=width)
        if branch and rng.random() < .03:
            crease(d, rng, nx, ny, heading + rng.choice([-1, 1]) * rng.uniform(.45, 1.0),
                   length * rng.uniform(.06, .22), bright * .75, max(1, width - 1), False)
        x, y = nx, ny


# ── Shared paper stock (regenerate with --paper) ───────────────────────────
def paper_tile(T=512, seed=40):
    """A tileable card texture: soft tooth a few pixels across (not per-pixel noise) and short fibres."""
    rng = np.random.default_rng(seed)
    fy, fx = np.fft.fftfreq(T)[:, None], np.fft.fftfreq(T)[None, :]
    def band(sig):   # periodic gaussian-filtered noise, so the tile wraps seamlessly
        g = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((T, T))) * np.exp(-2 * (np.pi * sig) ** 2 * (fx ** 2 + fy ** 2))))
        return (g / g.std()).astype(np.float32)
    tooth = .55 * band(1.1) + .45 * band(3.0)
    def fibres(count, lo, hi):
        big = Image.new('L', (3 * T, 3 * T), 0); d = ImageDraw.Draw(big)
        for _ in range(count):
            x, y = T + rng.uniform(0, T), T + rng.uniform(0, T); a = rng.uniform(0, math.pi); L = rng.uniform(4, 18)
            d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=int(rng.uniform(lo, hi)), width=1)
        arr = np.asarray(big).astype(np.float32) / 255
        return np.clip(sum(arr[i * T:(i + 1) * T, j * T:(j + 1) * T] for i in range(3) for j in range(3)), 0, 1)
    fl, fd = fibres(T * T // 220, 40, 140), fibres(T * T // 260, 40, 130)
    white, dirt = np.array([246, 243, 236], np.float32), np.array([28, 26, 24], np.float32)
    lift = np.clip(.02 + np.clip(tooth, 0, None) * .026 + fl * .04, 0, 1)[..., None]
    dark = np.clip(np.clip(-tooth, 0, None) * .026 + fd * .04, 0, 1)[..., None]
    rgb = white * lift; a = lift[..., 0]
    rgb = rgb * (1 - dark) + dirt * dark; a = a * (1 - dark[..., 0]) + dark[..., 0]
    rgb = rgb / np.maximum(a[..., None], 1e-4)
    Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), (a * 255).astype(np.uint8)]), 'RGBA').save(PAPER_TILE, 'WEBP', quality=90, method=6)


# ── One record's wear ──────────────────────────────────────────────────────
def make_mask(slug, year, dens=1.0, edgek=1.0):
    """dens and edgek scale the amount of wear without moving any of it, so every level is the same sleeve."""
    rng = np.random.default_rng(int(hashlib.sha1(slug.encode()).hexdigest()[:8], 16))
    U = rng.uniform; P = lambda p: rng.random() < p
    age = (2026 - int(str(year)[:4])) if year else 20
    old = min(1.0, age / 30)
    life = float(np.clip(.5 + (age / 40) ** 1.3 * .85 + U(-.08, .08), .55, 1.35))   # floor: every record has been played
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    mask = np.zeros((S, S), np.float32)

    # Abrasion comes off in crisp, sponge-like flecks: a density field switches on a share of
    # a clumpy threshold texture, so denser wear means more (not blurrier) flecks.
    T = uniform(.45 * fbm(rng, S, 2.2, 2) + .35 * fbm(rng, S, 7, 2) + .2 * fbm(rng, S, 28, 2))
    tone = .75 + .25 * fbm(rng, S, 5, 2)
    grain = fbm(rng, S, 2, 2)
    # sparse wear reads as faint grey specks, dense wear as near-white abrasion
    fleck_on = lambda D, Tn: smooth(-.03, .03, D - Tn) * (.45 + .55 * np.clip(D / .6, 0, 1)) * tone
    flecks = lambda D: fleck_on(D, T)

    # 1. The cut edge: a hard, chipped line, width varying along each side, worse at the corners.
    def profile():
        n = S; t = np.arange(n, dtype=np.float32)
        base = S * U(.0014, .0026) * (.45 + life) * edgek
        prof = base * (.2 + 1.3 * noise1(rng, n, S * .07) ** 2)
        for _ in range(int(U(1, 4) * life)):
            c, w = U(0, n), U(S * .003, S * .02)
            prof += base * U(1, 2.2) * np.exp(-((t - c) / w) ** 2)
        if P(.22 * life):
            c, w = U(.2, .8) * n, U(.08, .25) * n
            prof += base * U(.5, 1.1) * np.exp(-((t - c) / w) ** 4)
        k = U(.4, 1.3)
        prof *= 1 + k * (np.exp(-t / (S * .03)) + np.exp(-(n - 1 - t) / (S * .03)))
        return prof
    shelf = U(1.1, 1.5) if P(.5) else 1.0
    top, bot, lef, rig = profile() * shelf, profile(), profile(), profile()
    xi = xx.astype(np.int32); yi = yy.astype(np.int32)
    edge = np.maximum.reduce([
        np.clip(top[xi] - yy + .5, 0, 1), np.clip(bot[xi] - (S - 1 - yy) + .5, 0, 1),
        np.clip(lef[yi] - xx + .5, 0, 1), np.clip(rig[yi] - (S - 1 - xx) + .5, 0, 1)])
    chips = np.clip((fbm(rng, S, 3, 2) - U(.28, .4)) * 7, 0, 1)
    outer = np.clip(1.6 - np.minimum.reduce([xx, yy, S - 1 - xx, S - 1 - yy]), 0, 1) * U(.55, .9)
    edge_mask = np.maximum(edge * chips, outer * min(1, .45 + life))          # the worn cut edge shows the card beneath

    # 2. Ring wear. No drawn outline: the circle is made of the abrasion itself.
    density = np.zeros((S, S), np.float32)
    ring_d = np.zeros((S, S), np.float32); haze = np.zeros((S, S), np.float32); Tr = T
    ring = P(.55 + .45 * old)
    if ring:
        cx, cy = S * U(.485, .515), S * U(.49, .52); R0 = S * U(.455, .478)
        r = np.hypot(xx - cx, yy - cy); ang = np.arctan2(yy - cy, xx - cx)
        R = R0 * (1 + U(.004, .012) * np.sin(ang + U(0, 6.28)) + U(.002, .006) * np.sin(2 * ang + U(0, 6.28)))
        rest = math.pi / 2 + U(-.5, .5) if P(.7) else U(0, 2 * math.pi)          # mostly low: gravity
        lb = (.5 + .5 * np.cos(ang - rest)) ** U(1, 2.5)
        lt = (.5 + .5 * np.cos(ang - rest - math.pi)) ** U(1.5, 3) * U(.3, .8)
        lobe = .2 + .8 * np.maximum(lb, lt)
        waves = [(k, U(.2, 1)) for k in (2, 3, 5, 8)]
        g = sum(w * (.5 + .5 * np.sin(k * ang + U(0, 6.28))) for k, w in waves) / sum(w for _, w in waves)
        cover = smooth(U(.2, .35), U(.5, .65), g)                                 # where it breaks up
        style = rng.random()                                                      # thin, broad, or both
        wt = S * U(.003, .006); a_thin = U(.5, .85) * (.45 if style > .7 else 1)
        thin = np.exp(-((r - R) / wt) ** 2)
        a_broad = U(.35, .7) * life * (.3 if style < .3 else 1)
        Rb = R - S * U(.003, .01); wb = S * U(.01, .03) * (.6 + .8 * (.5 + .5 * np.sin(2 * ang + U(0, 6.28))))
        dd = r - Rb
        broad = np.exp(-(dd / (wb * np.where(dd > 0, .7, 1.3))) ** 2)
        ring_d = np.maximum(thin * a_thin, broad * a_broad) * lobe * cover
        haze = np.maximum(thin, broad) * lobe * cover * U(.03, .065) * (.4 + .6 * grain)   # faint sheen: the circle reads from afar
        if P(.45 + .3 * old):                                                     # rub streak at the bottom tangent
            ax, ay = R0 * U(.22, .45), S * U(.01, .025)
            sx, sy = cx + R0 * U(-.08, .08), cy + R0 * U(.975, .995)
            e = ((xx - sx) / ax) ** 2 + ((yy - sy) / ay) ** 2
            ring_d = np.maximum(ring_d, np.exp(-e ** 1.5) * U(.5, .9) * life)
        if P(.3 + .35 * old):                                                     # and the top
            ax, ay = R0 * U(.18, .38), S * U(.008, .02)
            sx, sy = cx + R0 * U(-.08, .08), cy - R0 * U(.975, .995)
            e = ((xx - sx) / ax) ** 2 + ((yy - sy) / ay) ** 2
            ring_d = np.maximum(ring_d, np.exp(-e ** 1.5) * U(.4, .8) * life)
        if P(.12 + .25 * old):                                                    # a faint ring at the label's edge
            Rl, wl = S * U(.14, .17), S * U(.006, .012)
            lc = smooth(.4, .7, sum(.5 + .5 * np.sin(k * ang + U(0, 6.28)) for k in (1, 2, 3)) / 3)
            ring_d = np.maximum(ring_d, np.exp(-((r - Rl) / wl) ** 2) * lc * U(.05, .12) * life)
        # the threshold texture here streaks along the turn (about 4x longer than it is wide)
        Tr = uniform(.5 * polar_noise(rng, r, ang, R0, 1.6, 7) + .3 * polar_noise(rng, r, ang, R0, 5, 24, 2) + .2 * fbm(rng, S, 28, 2))
    # Shelf and hand wear: short streaks along the bottom edge where it slid on a shelf, and
    # abrasion along the side it is gripped by, both running parallel to the edge. Every sleeve without a ring gets some; a few ringed ones too.
    if not ring or P(.25):
        if P(.8):
            h = S * U(.018, .045); along = smooth(.4, .8, noise1(rng, S, S * .12))
            band = np.exp(-((S - 1 - yy) / h) ** 1.5) * along[xi]
            Tv = uniform(.6 * aniso(rng, 9, 1.8) + .4 * aniso(rng, 26, 5))     # streaks run along the edge, not up from it
            mask = np.maximum(mask, fleck_on(np.clip(band * U(.3, .55) * life * dens, 0, 1), Tv))
        if P(.55):
            w = S * U(.018, .045); dist = xx if P(.5) else S - 1 - xx
            along = smooth(.3, .7, noise1(rng, S, S * .12))
            band = np.exp(-(dist / w) ** 1.5) * along[yi]
            Th = uniform(.6 * aniso(rng, 1.8, 9) + .4 * aniso(rng, 5, 26))
            mask = np.maximum(mask, fleck_on(np.clip(band * U(.25, .45) * life * dens, 0, 1), Th))

    scuffs = []
    if not ring:
        # No ring: the wear is general handling, a few patches of fine rub strokes where hands and shelves rub.
        for _ in range(int(rng.integers(1, 4))):
            scuffs.append((S * U(.15, .85), S * U(.15, .85), U(0, math.pi), S * U(.06, .16), S * U(.02, .05), int(U(60, 140) * life)))

    # 3. Creases, scratches and scuffs, drawn at 2x for crisp anti-aliased lines.
    cv = Image.new('L', (S * 2, S * 2), 0); d = ImageDraw.Draw(cv)
    for (px, py, sx, sy) in [(0, 0, 1, 1), (S, 0, -1, 1), (0, S, 1, -1), (S, S, -1, -1)]:
        if not P(.12 + .38 * old):
            continue
        if P(.55):                                                                # dog-ear fold across the corner
            d1, d2 = S * U(.015, .05), S * U(.015, .05)
            x0, y0, x1, y1 = px + sx * d1, py + sy * 1.5, px + sx * 1.5, py + sy * d2
            crease(d, rng, x0, y0, math.atan2(y1 - y0, x1 - x0), math.hypot(x1 - x0, y1 - y0) * 1.02, U(.55, .9), 2, False)
            tip = (np.abs(xx - px) / d1 + np.abs(yy - py) / d2) < 1
            density = np.maximum(density, tip * U(.25, .55))
        for _ in range(int(U(0, 2.6) * life)):                                    # cracks running in from the corner
            along = S * U(0, .06)
            x0, y0 = (px + sx * along, py + sy * 2) if P(.5) else (px + sx * 2, py + sy * along)
            crease(d, rng, x0, y0, math.atan2(sy, sx) + U(-.45, .45), S * U(.05, .2) * min(1.2, life), U(.5, .85), int(rng.choice([2, 2, 3])))
    for _ in range(int(U(0, 2.4) * old * life) + (1 if P(.2 * old) else 0)):    # seam-side creases
        x0 = S * U(.008, .05); x0 = x0 if P(.5) else S - x0
        crease(d, rng, x0, S * U(.05, .6), math.pi / 2 + U(-.08, .08), S * U(.15, .55), U(.45, .8), 2)
    a0 = U(0, math.pi)                                                            # slide scratches: one prevailing direction
    for _ in range(int(U(0, 1) ** 1.6 * 26 * life)):
        L = S * math.exp(U(math.log(.015), math.log(.09))); a = a0 + rng.normal(0, .14)
        x0, y0 = U(.03, .97) * S, U(.03, .97) * S; x1, y1 = x0 + math.cos(a) * L, y0 + math.sin(a) * L
        bend = U(-.08, .08) * L; mx, my = (x0 + x1) / 2 - math.sin(a) * bend, (y0 + y1) / 2 + math.cos(a) * bend
        peak = U(70, 160) if P(.8) else U(160, 235)
        for i in range(14):
            t0, t1 = i / 14, (i + 1) / 14
            q = lambda t: ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1)
            p0, p1 = q(t0), q(t1)
            d.line([(p0[0] * 2, p0[1] * 2), (p1[0] * 2, p1[1] * 2)], fill=int(peak * math.sin(math.pi * (t0 + t1) / 2) ** .7), width=2)
    for _ in range(int(U(1, 6) * life)):                                          # hairline scratches
        L = S * math.exp(U(math.log(.03), math.log(.4))); a = U(0, math.pi)
        x0, y0 = U(0, S), U(0, S); x1, y1 = x0 + math.cos(a) * L, y0 + math.sin(a) * L
        bend = U(-.06, .06) * L; mx, my = (x0 + x1) / 2 - math.sin(a) * bend, (y0 + y1) / 2 + math.cos(a) * bend
        peak = U(60, 150) if P(.85) else U(150, 220)
        gaps = [(g0, g0 + U(.03, .12)) for g0 in rng.uniform(.1, .9, int(U(0, 3)))]
        for i in range(28):
            t0, t1 = i / 28, (i + 1) / 28
            if any(a0 < t0 < a1 for a0, a1 in gaps): continue
            q = lambda t: ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1)
            p0, p1 = q(t0), q(t1)
            d.line([(p0[0] * 2, p0[1] * 2), (p1[0] * 2, p1[1] * 2)], fill=int(peak * math.sin(math.pi * (t0 + t1) / 2) ** .5), width=2)
    scuffs += [(U(.1, .9) * S, U(.1, .9) * S, U(0, math.pi), S * U(.03, .09), S * U(.015, .04), int(U(15, 55))) for _ in range(int(U(0, 2.2) * life))]
    for cx2, cy2, a, rx, ry, n_strokes in scuffs:                                 # scuffs: parallel strokes in a patch
        for _k in range(n_strokes):
            t = U(0, 2 * math.pi); rr = math.sqrt(U(0, 1))
            px2 = cx2 + rr * rx * math.cos(t) * math.cos(a) - rr * ry * math.sin(t) * math.sin(a)
            py2 = cy2 + rr * rx * math.cos(t) * math.sin(a) + rr * ry * math.sin(t) * math.cos(a)
            L = U(4, 22); aa = a + U(-.05, .05)
            d.line([(px2 * 2, py2 * 2), ((px2 + math.cos(aa) * L) * 2, (py2 + math.sin(aa) * L) * 2)], fill=int(U(50, 140)), width=1)
    lines = np.asarray(cv.resize((S, S), Image.BOX)).astype(np.float32) / 255

    mask = np.maximum(mask, flecks(np.clip(density * dens, 0, 1)))
    mask = np.maximum(mask, fleck_on(np.clip(ring_d * dens, 0, 1), Tr))
    mask = np.maximum(mask, haze * min(1.3, dens))
    mask = np.maximum(mask, lines)

    # 4. On the oldest sleeves, a small tear at one edge, exposing the paper underneath.
    if age > 15 and P(.1 + .25 * old):
        side = int(rng.integers(0, 4)); pos = U(.15, .85) * S
        wa, dp = S * U(.02, .05), S * U(.01, .03)
        u, v = [(xx, yy), (xx, S - 1 - yy), (yy, xx), (yy, S - 1 - xx)][side]
        shape = np.exp(-((u - pos) / wa) ** 4 - (v / dp) ** 2)
        tear = smooth(.29, .33, shape - .45 * fbm(rng, S, 5, 3))
        edge_mask = np.maximum(edge_mask, tear * U(.8, .95))

    return np.stack([np.clip(mask, 0, 1), np.clip(edge_mask, 0, 1)], -1), life, age, ring


# ── Baking ─────────────────────────────────────────────────────────────────
_PAPER = None
def paper():
    global _PAPER
    if _PAPER is None: _PAPER = np.asarray(Image.open(PAPER_TILE).convert('RGBA')).astype(np.float32) / 255
    return _PAPER


def load_square(path, pad=False):
    im = Image.open(path).convert('RGB')
    if pad and abs(im.width - im.height) > 2:
        a = np.asarray(im); border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
        side = max(im.size); sq = Image.new('RGB', (side, side), tuple(int(v) for v in np.median(border, 0)))
        sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2)); im = sq
    return np.asarray(im.resize((S, S), Image.LANCZOS)).astype(np.float32) / 255


def bake(cov, mask, k, slug, age):
    rng = np.random.default_rng(int(hashlib.sha1((slug + ':bake').encode()).hexdigest()[:8], 16))
    Lum = cov @ np.array([.2126, .7152, .0722], np.float32)
    s = smooth(.55, .82, Lum)[..., None]                     # 0 over dark ink, 1 over light ink
    col = PAPER_WHITE * (1 - s) + GRIME * s
    a = np.clip(mask[..., 0] * k, 0, 1)[..., None] * (.82 + .18 * s) * (1 - .3 * s)   # a touch softer on black, grime a touch lighter
    out = cov * (1 - a) + col * a
    ae = np.clip(mask[..., 1] * k, 0, 1)[..., None] * .95
    out = out * (1 - ae) + (BOARD * (1 - s) + BOARD_DIRTY * s) * ae
    mean = float(Lum.mean())
    if mean > .62 and age > 30:                               # old light stock ages warm, more at the edges
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
        dmin = np.minimum.reduce([xx, yy, S - 1 - xx, S - 1 - yy])
        amt = (min(.35, (age - 30) / 60) + .25 * np.exp(-dmin / (S * .05)))[..., None]
        out = out * (1 - amt * (1 - WARM))
    th = rng.uniform(0, 2 * math.pi)                          # scanner-lamp falloff
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    u = (((xx - S / 2) * math.cos(th) + (yy - S / 2) * math.sin(th)) / (S * .72))[..., None]
    out = out + (1 - out) * np.clip(-u, 0, 1) ** 1.6 * rng.uniform(.02, .04)
    out = out * (1 - np.clip(u, 0, 1) ** 1.6 * rng.uniform(.035, .06))
    t = paper(); n = t.shape[0]; t = np.tile(t, (S // n + 1, S // n + 1, 1))[:S, :S]
    pa = t[:, :, 3:4] * (.9 if mean > .62 else .75 + .25 * mean)
    out = out * (1 - pa) + t[:, :, :3] * pa
    return Image.fromarray((np.clip(out, 0, 1) * 255 + .5).astype(np.uint8))


def job(a):
    slug = a['slug']
    level = (a.get('wear') or {}).get('level', 'med')
    level = level if level in LEVELS else 'med'
    masks = {}
    for lv in (LEVELS if LEVELS_DIR else [level]):
        dens, ek, _ = LEVELS[lv]
        masks[lv] = make_mask(slug, a.get('year'), dens, ek)
    mask, life, age, ring = masks[level]; k = LEVELS[level][2]
    MASKS.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([(mask * 255 + .5).astype(np.uint8), np.zeros((S, S), np.uint8)]), 'RGB').save(MASKS / f'{slug}.png')
    cov = load_square(ROOT / a['art'])
    bake(cov, mask, k, slug, age).save(WORN / f'{slug}.jpg', 'JPEG', quality=88, optimize=True, progressive=True)
    back = None
    if a.get('art_back') and (ROOT / a['art_back']).exists():
        bake(load_square(ROOT / a['art_back'], pad=True), mask[:, ::-1], k, slug + ':back', age) \
            .save(WORN / f'{slug}-back.jpg', 'JPEG', quality=86, optimize=True, progressive=True)
        back = f'assets/40/worn/{slug}-back.jpg'
    if LEVELS_DIR:
        (LEVELS_DIR / 'lv').mkdir(parents=True, exist_ok=True); (LEVELS_DIR / 'art').mkdir(parents=True, exist_ok=True)
        for lv, (m, _l, _a, _r) in masks.items():
            bake(cov, m, LEVELS[lv][2], slug, age).resize((1000, 1000), Image.LANCZOS).save(LEVELS_DIR / 'lv' / f'{slug}-{lv}.jpg', 'JPEG', quality=84, optimize=True, progressive=True)
        Image.open(ROOT / a['art']).convert('RGB').resize((1000, 1000), Image.LANCZOS).save(LEVELS_DIR / 'art' / f'{slug}.jpg', 'JPEG', quality=84, optimize=True, progressive=True)
    return slug, a.get('year'), round(life, 2), ring, back


if __name__ == '__main__':
    WORN.mkdir(parents=True, exist_ok=True)
    if '--paper' in args or not PAPER_TILE.exists():
        paper_tile(); print('paper tile', PAPER_TILE.stat().st_size // 1024, 'KB')
    data_path = ROOT / 'data/albums.json'
    albums = [a for a in json.loads(data_path.read_text())['albums'] if a.get('art') and (not ONLY or a['slug'] in ONLY)]
    with Pool(JOBS) as pool:
        results = pool.map(job, albums)
    backs = {}
    for slug, year, life, ring, back in results:
        backs[slug] = back
        print(f'{slug:52} {year} life={life:.2f} {"ring" if ring else "    "} {(WORN / (slug + ".jpg")).stat().st_size // 1024}KB')
    doc = json.loads(data_path.read_text())                   # re-read: don't clobber edits made meanwhile
    for a in doc['albums']:
        if a['slug'] in backs:
            a['art_worn'] = f"assets/40/worn/{a['slug']}.jpg"
            if backs[a['slug']]: a['art_back_worn'] = backs[a['slug']]
            a['wear'] = {'level': (a.get('wear') or {}).get('level', 'med')}
    data_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
