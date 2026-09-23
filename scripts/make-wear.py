#!/usr/bin/env python3
"""Sleeve wear, modelled on how a real sleeve wears, so the result reads like a flatbed scan
of a well-played record sleeve rather than a filter.

The physical model
  The printed ink sits on a coated card. Wear is ink breaking away: wherever the rubbing
  pressure on a spot beats how firmly the ink holds there, the ink comes off in a crisp,
  torn-edged flake and the pale paper fibres show. How firmly it holds (the "toughness")
  varies at every scale: per fibre (1-2px), per flake (3-6px), in clumps (15-40px) and in
  broad patches. So heavier pressure means MORE flakes, never a softer or greyer veil.
  The toughness field is rendered at 2x and averaged down, the way a scanner's sensor
  integrates the smallest flakes.

  Where the pressure comes from:
  - the disc's rim pressing through the sleeve: a thin, wobbling, broken ring, strongest at
    the bottom (where the record rests) and top. Two ways it shows, chosen per sleeve: torn
    flake clusters with a bevel rub inside them, or a thin chain of small chips broken into
    separate worn arcs (the oldest sleeves wear into flake clusters)
  - flat rub bars where the ring's top and bottom run along the straight edges and the
    sleeve is pinched between the record and the shelf: a near-solid core of round, powdery
    clumps whose depth wanders along the rub, in a frost that is greyer on some sleeves and
    whiter on others; the core's hard edge sits on the rim side, the inner side, or it is
    centred. Not on young sleeves, and a pair of bars is less common than one
  - shelf friction along the cut edges, and crushed corners whose flakes hug the outline; the
    hand that holds it by one side (and on a sleeve with no ring, the thumb's rub there)
  - grit dragged across the face (short parallel striations), and the label's edge
  - folds: the ink film splits along a hair-thin, nearly straight line broken into runs
  Separately: the cut edge itself is crushed to show the tan card, broken into runs with
  chips and dark crumbs; the record sliding in and out leaves fine scratches in one
  prevailing direction.

  The site rounds every sleeve's corners (2.8% of its width), so all edge wear is laid out on
  that rounded outline: distance to the edge is distance to the rounded rectangle, and corner
  chips, folds, crack fans and edge scuffs hug the arc instead of the square corner.

  Light covers: exposed paper is invisible on pale ink, so wear shows as what paper does
  there. Rubbed near-white ink scuffs a shade darker in its own hue, the rubbed fibres hold
  grime and grey grain (in small clumps, and only as the sleeve ages), the card's tooth shows,
  and cracks read as faint hairlines. The disc's rim leaves a thin, patchy impression line on
  neutral stock; on young or tinted-pale stock it is only a faint broken scuff in the ink's own
  hue. A younger pale sleeve's rub bars scuff rather than soil, and its cut edge is still pale
  card. Over dark or saturated ink, wear is near-white paper.

  Outside the rounded outline the art is left untouched, so an unclipped copy shows the art's
  square corner, not a wedge of card.

Older records carry more of all of it. The seed is the slug, so no two sleeves match. The back
shares the front's ring (the disc presses both faces, mirrored) but its own scratches, cracks,
scuffs, edges and corners (seeded by slug + ':back'). A shared paper-grain tile and a faint
scanner-lamp falloff finish it. No global lift or desaturation: art colour and blacks stay.

Outputs
  assets/40/worn/<slug>.jpg        the sleeve every surface uses (site, grid, stories): art_worn
  assets/40/worn/<slug>-back.jpg   the back, squared, with the ring mirrored: art_back_worn
Strength comes from the album's wear.level: low | med | high (default med).

Usage: scripts/make-wear.py [--only slug,slug] [--jobs 4] [--levels DIR] [--paper]
  --levels DIR   also bake low/med/high and the clean art at 1000px into DIR (for the picker)
  --paper        regenerate the shared paper tile
"""
import sys, math, json, hashlib
from multiprocessing import Pool
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MASKS = ROOT / 'out/wear-masks'           # build intermediates (gitignored)
WORN = ROOT / 'assets/40/worn'
PAPER_TILE = ROOT / 'assets/40/wear/paper.webp'
S = 1200
SS = 2                          # the flake field is rendered at 2x and averaged down
N = S * SS
RC = .028                       # the site's corner radius, as a share of the sleeve's width
LEVELS = {'low': (.6, .8, .9), 'med': (1.0, 1.0, 1.0), 'high': (1.45, 1.25, 1.0)}   # (pressure, edge width, line strength)
args = sys.argv[1:]
ONLY = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
JOBS = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4
LEVELS_DIR = Path(args[args.index('--levels') + 1]) if '--levels' in args else None

PAPER_WHITE = np.array([241, 237, 227], np.float32) / 255    # the paper under the ink
DIRT_TINT = np.array([.52, .51, .43], np.float32)             # multiply: grime held in rubbed fibres
LINE_TINT = np.array([.70, .69, .62], np.float32)             # multiply: the rim's impression line on neutral stock
SOIL = np.array([104, 99, 84], np.float32) / 255              # grey grain in rubbed white stock
WARM = np.array([1.0, .955, .86], np.float32)                 # age tone on old light sleeves
BOARD = np.array([205, 189, 162], np.float32) / 255           # the card under a crushed edge
BOARD_DIRTY = np.array([146, 134, 114], np.float32) / 255     # the same edge on a light sleeve


def seed(key):
    return np.random.default_rng(int(hashlib.sha1(key.encode()).hexdigest()[:8], 16))


# ── Noise ──────────────────────────────────────────────────────────────────
def _blur_wrap(a, sy, sx):
    """Periodic gaussian blur by FFT."""
    fy = np.fft.fftfreq(a.shape[0])[:, None]; fx = np.fft.rfftfreq(a.shape[1])[None, :]
    k = np.exp(-2 * math.pi ** 2 * ((sy * fy) ** 2 + (sx * fx) ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * k, s=a.shape).astype(np.float32)


def gnoise(rng, n, sigma, aspect=1.0):
    """Isotropic (or x-stretched) gaussian-filtered white noise, zero mean, unit std. Large scales
    are built on a coarse grid and upsampled, which is exact enough for a field that smooth."""
    f = max(1, int(min(sigma, sigma * aspect) / 2.5))
    m = int(math.ceil(n / f))
    g = _blur_wrap(rng.standard_normal((m, m)).astype(np.float32), sigma / f, sigma * aspect / f)
    if f > 1:
        g = np.asarray(Image.fromarray(g, 'F').resize((n, n), Image.BICUBIC))
    g = g - g.mean()
    return (g / (g.std() + 1e-8)).astype(np.float32)


def phi(z):
    """Standard normal CDF (Abramowitz-Stegun erf), so a gaussian field becomes uniform on [0,1]."""
    x = np.abs(z) / math.sqrt(2); t = 1 / (1 + .3275911 * x)
    e = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - .284496736) * t + .254829592) * t * np.exp(-x * x)
    return (.5 * (1 + np.sign(z) * e)).astype(np.float32)


def noise1(rng, n, cell, octaves=4, gain=.55):
    x = np.arange(n, dtype=np.float32); out = np.zeros(n, np.float32); amp, tot, c = 1., 0., cell
    for _ in range(octaves):
        k = int(n / c) + 2
        out += np.interp(x / c, np.arange(k), rng.random(k)) * amp; tot += amp; amp *= gain; c = max(2, c / 2)
    return out / tot


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


def down(a):
    """Average a 2x field down to the sleeve: the scanner integrating sub-pixel flakes."""
    return a.reshape(S, SS, S, SS).mean((1, 3))


def up(a):
    return np.asarray(Image.fromarray(np.ascontiguousarray(a, np.float32), 'F').resize((N, N), Image.BILINEAR))


def flakes(P, T, e=.012):
    """Pressure (1x) against toughness (2x): 1 where the ink came off, averaged down to the sleeve."""
    return smooth(-e, e, up(P) - T)


def toughness(rng, aspect=1.0, wg=(.6, .32, .35, .18), fine=.75):
    """How firmly the ink holds, per spot (uniform 0..1). Fibre grain, flake, clump and patch scales,
    plus paper fibres along which the ink lifts first. The clump and patch weights are kept low, so
    flakes spread along a rub as a frost instead of balling into clusters."""
    z = (wg[0] * gnoise(rng, N, fine, aspect) + wg[1] * gnoise(rng, N, 2.3, aspect)
         + wg[2] * gnoise(rng, N, 10, aspect) + wg[3] * gnoise(rng, N, 40, aspect))
    t = phi(z / math.sqrt(sum(w * w for w in wg)))
    fib = Image.new('L', (N, N), 0); d = ImageDraw.Draw(fib)
    for _ in range(N * N // 700):
        x, y = rng.uniform(0, N), rng.uniform(0, N); a = rng.uniform(0, math.pi); L = rng.uniform(6, 22)
        d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=255, width=1)
    return np.clip(t - np.asarray(fib).astype(np.float32) / 255 * .14, .02, 1)   # no pressure, no wear


def skip_toughness(rng, aspect=1.0, fine=.75):
    """Consume exactly the random draws toughness() would, without building the field."""
    for sigma in (fine, 2.3, 10, 40):
        f = max(1, int(min(sigma, sigma * aspect) / 2.5))
        rng.standard_normal((int(math.ceil(N / f)),) * 2)
    rng.random(4 * (N * N // 700))


def rub_toughness(rng):
    """The rub bars' toughness. The flakes stay roughly round (powdery clumps, e4904, 51656); the
    streaking along the rub is only in how densely they gather, at the clump scale."""
    wg = (.36, .28, .22, .22)
    z = (wg[0] * gnoise(rng, N, 1.0, 1.3) + wg[1] * gnoise(rng, N, 1.6)
         + wg[2] * gnoise(rng, N, 3.5, 1.5) + wg[3] * gnoise(rng, N, 14, 44 / 14))
    return np.clip(phi(z / math.sqrt(sum(w * w for w in wg))), .02, 1)


def skip_rub(rng):
    """Consume the draws of the retired streaky rub field, so the rub stream's later draws (the
    ring's style, the bar decisions) stay where they were."""
    for sigma, aspect in ((1.2, 3.4 / 1.2), (1.3, 1.0), (4, 3.0), (14, 44 / 14)):
        f = max(1, int(min(sigma, sigma * aspect) / 2.5))
        rng.standard_normal((int(math.ceil(N / f)),) * 2)


def clump_field(rng):
    """A clumpier threshold for grime and soil: grain gathers in small clusters that follow the
    tooth, not as isolated single-pixel pepper."""
    wg = (.4, .45, .45, .2)
    z = (wg[0] * gnoise(rng, N, .75) + wg[1] * gnoise(rng, N, 2.3)
         + wg[2] * gnoise(rng, N, 9) + wg[3] * gnoise(rng, N, 30))
    return np.clip(phi(z / math.sqrt(sum(w * w for w in wg))), .02, 1)


def rrect():
    """Distance in from the sleeve's rounded outline (the site's 2.8% corner radius), and the
    distance to the square edge. Outside the rounded corner it goes negative: clipped away."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    rc = RC * S
    dx = np.maximum(np.maximum(rc - xx, xx - (S - 1 - rc)), 0)
    dy = np.maximum(np.maximum(rc - yy, yy - (S - 1 - rc)), 0)
    dsq = np.minimum.reduce([xx, yy, S - 1 - xx, S - 1 - yy])
    return np.where((dx > 0) & (dy > 0), rc - np.hypot(dx, dy), dsq).astype(np.float32), dsq


def inset(t):
    """How far the rounded outline sits in from the square edge, t px along from a corner."""
    rc = RC * S
    return rc - math.sqrt(max(0.0, rc * rc - (rc - t) ** 2)) if t < rc else 0.0


def crack(d, rng, x, y, heading, length, bright, width=2, depth=0):
    """A fold crack: the ink film splits along a hair-thin, nearly straight line that breaks into
    runs (e4904, 51656), with the odd gentle kink and a rare short fork. Drawn on a 2x canvas."""
    h0 = heading; travelled = 0.0; skip = 0
    while travelled < length:
        step = rng.uniform(1.2, 3.2)
        heading += rng.normal(0, .3) if rng.random() < .1 else rng.normal(0, .05)
        heading += (h0 - heading) * .08
        nx, ny = x + math.cos(heading) * step, y + math.sin(heading) * step
        t = travelled / length; env = min(1.0, t * 6 + .2, (1 - t) * 4 + .1)
        if skip > 0:                                 # a break in the run
            skip -= 1
        elif rng.random() < .08:
            skip = int(rng.integers(2, 6))
        else:
            v = bright * env * (.65 + .35 * rng.random())
            d.line([(x * 2, y * 2), (nx * 2, ny * 2)], fill=int(255 * min(1.0, v)), width=width)
        if depth < 1 and rng.random() < .015:
            crack(d, rng, nx, ny, heading + rng.choice([-1, 1]) * rng.uniform(.3, .8),
                  length * rng.uniform(.12, .35) * (1 - t) + 4, bright * .8, 1, depth + 1)
        x, y = nx, ny; travelled += step


def bezier_line(d, x0, y0, x1, y1, bend, peak, segs, power, width=2, gaps=()):
    mx, my = (x0 + x1) / 2 - math.sin(math.atan2(y1 - y0, x1 - x0)) * bend, (y0 + y1) / 2 + math.cos(math.atan2(y1 - y0, x1 - x0)) * bend
    q = lambda t: ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1)
    for i in range(segs):
        t0, t1 = i / segs, (i + 1) / segs
        if any(g0 < t0 < g1 for g0, g1 in gaps): continue
        p0, p1 = q(t0), q(t1)
        d.line([(p0[0] * 2, p0[1] * 2), (p1[0] * 2, p1[1] * 2)], fill=int(peak * math.sin(math.pi * (t0 + t1) / 2) ** power), width=width)


# ── Shared paper stock (regenerate with --paper) ───────────────────────────
def paper_tile(T=512, seed=40):
    """A tileable card texture: fine 1-2px tooth (fine band dominant) and short pale and dark fibres."""
    rng = np.random.default_rng(seed)
    fy, fx = np.fft.fftfreq(T)[:, None], np.fft.fftfreq(T)[None, :]
    def band(sig):   # periodic gaussian-filtered noise, so the tile wraps seamlessly
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
    white, dirt = np.array([246, 243, 236], np.float32), np.array([28, 26, 24], np.float32)
    lift = np.clip(.024 + np.clip(grain, 0, None) * .036 + fl * .05, 0, 1)[..., None]
    dark = np.clip(np.clip(-grain, 0, None) * .036 + fd * .05, 0, 1)[..., None]
    rgb = white * lift; a = lift[..., 0]
    rgb = rgb * (1 - dark) + dirt * dark; a = a * (1 - dark[..., 0]) + dark[..., 0]
    rgb = rgb / np.maximum(a[..., None], 1e-4)
    Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), (a * 255).astype(np.uint8)]), 'RGBA').save(PAPER_TILE, 'WEBP', quality=90, method=6)


# ── One record's wear ──────────────────────────────────────────────────────
def age_of(year):
    return (2026 - int(str(year)[:4])) if year else 20


_RING, _SURF = {}, {}


def ring_layer(slug, year):
    """What the disc did, shared by both faces: the ink's toughness, the ring, its impression line,
    and the rub bars. Seeded by the slug."""
    key = (slug, year)
    if key in _RING:
        return _RING[key]
    rng = seed(slug)
    U = rng.uniform; P = lambda p: rng.random() < p
    age = age_of(year)
    old = min(1.0, age / 30)
    life = float(np.clip(.28 + (age / 40) ** 1.3 + U(-.08, .08), .3, 1.4))
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    xi = xx.astype(np.int32)
    # (the draws up to the ring's shape keep their order, so every sleeve keeps the ring it had)
    front = dict(fine=rng.random((S, S)).astype(np.float32), crumbs=rng.random((S, S)) > .9)   # the front face's own
    T = toughness(rng)                               # isotropic: ring arcs, edges, corners, cracks
    skip_toughness(rng, U(1.6, 2.4) if P(.6) else U(.4, .65), .55)   # (a retired streaky field: its draws, not its cost)
    V = .66 + .3 * phi(gnoise(rng, N, 1.1))          # how clean each flake is (a little ink may cling)
    front['gfield'] = rng.random((S, S)).astype(np.float32); front['gp'] = U(.45, .65)
    ring = P(.55 + .45 * old)                        # not every sleeve has one
    rr = seed(slug + ':rub')
    skip_rub(rr)                                     # (the retired streaky rub field: its draws only)
    Vb = .55 + .3 * phi(gnoise(rr, N, 1.1))          # a rub bar's frost is a little greyer
    rub_tone = rr.uniform(.6, 1.0)                   # and some rubs burnish grey, others go white
    chain = rr.random() < .35 - .015 * max(0, age - 20)   # the ring as a thin chain of chips; the oldest wear into flake clusters
    bars = (rr.random() < .5 + .35 * old and age > 10, rr.random() < .45 + .35 * old and age > 10)   # rub bars at the ring's bottom and top
    if bars[0] and bars[1] and rr.random() < .35:    # a pair is less common than a single bar
        bars = (True, False) if rr.random() < .5 else (False, True)
    bprof = [rr.random() for _ in range(2)]          # each bar's profile: rim-hard, inner-hard or centred
    rt = seed(slug + ':rubT')
    Trub = rub_toughness(rt)                         # the rub bars' flakes: round, gathered in streaks
    Vbc = .75 + .2 * phi(gnoise(rt, N, 1.1))         # a bar's worn-through core is brighter than its frost
    Tc = clump_field(seed(slug + ':soil'))           # grime and soil gather in clumps

    Pi = np.zeros((S, S), np.float32)                # pressure read against T
    Pb = np.zeros((S, S), np.float32)                # pressure read against Trub: a bar's frost
    Pbc = np.zeros((S, S), np.float32)               # and its near-solid core
    Dl = np.zeros((S, S), np.float32)                # the rim's impression line (neutral pale stock)
    Ds = np.zeros((S, S), np.float32)                # the rim's stipple (young or tinted pale stock)
    soil = np.zeros((S, S), np.float32)              # grey grain the rub leaves in white stock

    style = ''
    th = np.linspace(-math.pi, math.pi, 4096, endpoint=False).astype(np.float32)
    def per(kmax, beta):                             # periodic noise around the circle, 0..1
        z = sum(rng.normal() / k ** beta * np.cos(k * th + U(0, 6.283)) for k in range(1, kmax + 1))
        return phi(z / (z.std() + 1e-6))
    angd = lambda c: np.abs(((th - c + math.pi) % (2 * math.pi)) - math.pi)
    if ring:
        cx, cy = S * (.5 + U(-.012, .012)), S * (.5 + U(-.006, .016))   # the record sags a touch low
        R0 = S * U(.458, .476)
        r = np.hypot(xx - cx, yy - cy); ang = np.arctan2(yy - cy, xx - cx)
        ai = (((ang + math.pi) / (2 * math.pi)) * 4096).astype(np.int32) % 4096
        Rt = R0 * (1 + U(.003, .008) * np.sin(th + U(0, 6.283)) + U(.0015, .004) * np.sin(2 * th + U(0, 6.283)) + .004 * (per(12, 1.2) - .5))
        wt = S * U(.0035, .0065) * (.55 + .9 * per(6, 1.0))
        bot = np.exp(-(angd(math.pi / 2 + U(-.25, .25)) / U(.28, .55)) ** 2) * U(.15, .38)
        top = np.exp(-(angd(-math.pi / 2 + U(-.25, .25)) / U(.22, .45)) ** 2) * U(.1, .35) * (1 if P(.75) else .2)
        rest = np.exp(-(angd(U(0, 6.283)) / U(.4, .9)) ** 2) * U(0, .18)
        A = (U(.11, .2) if age >= 20 else U(.08, .17)) + bot + top + rest    # old sleeves: legible all round
        A = A * life
        c0 = U(.15, .35) if old > .8 else U(.2, .42)                          # and in longer arcs
        cover = smooth(c0, c0 + U(.18, .35), per(9, .8))
        d = r - Rt[ai]
        if chain:
            # a thin chain of small chips (50fd7484): a narrow core, heavy lobes where it rested, 1-3
            # side arcs that happened to rub, and breaks all round
            style = 'chain'
            wc = S * U(.0026, .0042) * (.8 + .4 * per(5, 1.0))
            lob = lambda c, p: (.5 + .5 * np.cos(th - c)) ** p
            aw = np.maximum(U(.75, 1) * lob(math.pi / 2 + U(-.3, .3), U(2, 6)), U(.45, .95) * lob(-math.pi / 2 + U(-.3, .3), U(2, 6)))
            for _ in range(int(rng.integers(1, 4))):
                aw = np.maximum(aw, U(.3, .75) * lob(U(0, 6.283), U(4, 14)))
            fl = .07 if age >= 20 else .04            # it breaks every 10-30 degrees: worn arcs, not a circle
            aw = (fl + (1 - fl) * aw) * smooth(.42, .64, .35 * per(8, .5) + .65 * per(24, .1))
            amp = U(.6, .9) * aw * min(1.25, life) * (.7 + .3 * old)
            core = np.exp(-(d / wc[ai]) ** 2) * amp[ai]
            wf = S * U(.007, .016) * (.7 + .45 * min(life, 1.3))
            band = np.exp(-(d / np.where(d < 0, wf, wf * .45)) ** 2) * (amp * U(.15, .3))[ai]   # a sparse fringe inside it
            Aline = amp
        else:
            # torn flake clusters: a sharp outer edge where the rim is, a softer inner falloff
            style = 'flake'
            w = wt[ai]
            prof = np.where(d > 0, np.exp(-(d / (.45 * w)) ** 2), np.exp(-(np.maximum(-d, 0) / w) ** 1.5))
            core = prof * (A * cover)[ai]
            # the bevel inside the rim rubs a wider, sparser band: thin rings keep it faint, broad ones strong
            halo = U(.55, .9) if P(.4 + .2 * old) else U(.2, .45)
            wb = S * U(.008, .017) * (.6 + .8 * per(5, 1.0)); Rb = Rt - wb * U(.5, .9)
            band = np.exp(-((r - Rb[ai]) / wb[ai]) ** 2) * (A * cover)[ai] * halo
            Aline = A * cover
        Pi = np.maximum(Pi, np.maximum(core, band))
        soil = np.maximum(soil, np.minimum(np.maximum(core * .7, band * 1.3), .4) * smooth(.25, .6, per(6, .8))[ai])   # grime gathers in patches
        # the rim's impression line, which catches grime on neutral pale stock: faint on a young
        # sleeve, fading in and out along the turn rather than dashing
        c1 = .4 + .1 * (1 - min(1.0, life))          # even a 40-year-old line fades out every 30-60 degrees
        lc = smooth(c1, c1 + .35, per(5, 1.0)) * (.3 + .7 * per(14, .5)) * smooth(.02, .5, Aline / (Aline.max() + 1e-6)) ** .6
        wl = S * U(.0009, .0016) * (.6 + .8 * per(5, 1.0))
        Dl = np.maximum(Dl, np.exp(-(d / wl[ai]) ** 2) * (np.minimum(lc * U(1.0, 1.3), 1.0) * (.12 + .88 * old))[ai])
        # the same rim on young or tinted stock: a faint scuff in the ink's own hue, a few px wide and broken
        ws = S * U(.004, .007) * (.6 + .8 * per(6, 1.0))
        cs = smooth(.4, .75, per(8, .8)) * smooth(.02, .5, Aline / (Aline.max() + 1e-6)) ** .5
        Ds = np.maximum(Ds, np.clip(1 - np.abs(d) / ws[ai], 0, 1) ** U(.6, 1.2) * (cs * U(.3, .45) * (.6 + .4 * old))[ai])
        if P(.05 + .15 * old):                       # the label's edge
            Rl = S * U(.152, .172); wl2 = S * U(.004, .007)
            Pi = np.maximum(Pi, np.exp(-((r - Rl) / wl2) ** 2) * (smooth(.4, .65, per(4, 1.0)) * U(.03, .06) * life)[ai])
        # flat rub bars where the ring's bottom and top run along the straight edges: a near-solid
        # core of powdery clumps at the rim with a frost around it. The core's hard edge is on the
        # rim side (most), the inner side (51656), or the core sits centred with frost both sides (e4904)
        def bar(yrim, bottom, amp, prof):
            sx = cx + R0 * U(-.15, .15); ax = R0 * (U(.2, .42) if bottom else U(.16, .36))
            h = S * U(.011, .018) * (1.15 if bottom else 1); hc = S * U(.005, .009)
            brk = .35 + .65 * smooth(.25, .6, noise1(rng, S, S * .03))                 # it breaks along its length
            ex = np.exp(-(np.abs(xx - sx) / ax) ** 2.4) * brk[xi]
            v = (yrim - yy) if bottom else (yy - yrim)                                  # inward from the rim
            if prof < .4:
                v = -v                                                                  # hard edge inside, frost toward the edge
            elif prof >= .7:
                v = np.abs(v)                                                           # centred
            vp = np.maximum(v, 0); hard = np.exp(-(v / 2.0) ** 2)
            frost = np.where(v >= 0, np.exp(-(vp / h) ** 1.8), hard)
            ck = 1.8 * max(amp, .3 + .2 * old) / max(amp, 1e-3)                         # where it exists, the core is near-solid
            hx = (hc * (.75 + 1.1 * noise1(rt, S, S * .04)))[xi]                        # its depth wanders along the rub (5-20px)
            cg = (.25 + .75 * smooth(.3, .6, noise1(rt, S, S * .05)))[xi]               # and it thins to frost in places
            core = np.where(v >= 0, np.exp(-(vp / hx) ** 3), hard) * ck * cg
            return np.minimum(ex * frost * amp, .95), ex * core * amp
        ka = .8 + .2 * old
        if bars[0]:
            f_, c_ = bar(min(cy + Rt[3072], S - 2.0), True, U(.28, .52) * life * ka, bprof[0])
            Pb = np.maximum(Pb, f_); Pbc = np.maximum(Pbc, c_)
        if bars[1]:
            f_, c_ = bar(max(cy - Rt[1024], 1.0), False, U(.4, .65) * life * ka, bprof[1])
            Pb = np.maximum(Pb, f_); Pbc = np.maximum(Pbc, c_)

    lay = dict(age=age, old=old, life=life, ring=ring, style=style, bars=bars if ring else (False, False), T=T, Trub=Trub, V=V, Vb=Vb, Vbc=Vbc,
               rub_tone=rub_tone, Tc=Tc, Pi=Pi, Pb=Pb, Pbc=Pbc, Dl=Dl, Ds=Ds, soil=soil, front=front)
    _RING.clear(); _RING[key] = lay
    return lay


def surface_layer(slug, year, face='', mean=.5, edgew=1.0):
    """What happened to one face: its cut edges and corners, shelf scuffs, the hand that held it,
    cracks, scratches and grit. The front and the back ('' / ':back') each have their own."""
    key = (slug, year, face, round(mean, 3), edgew)
    if key in _SURF:
        return _SURF[key]
    R = ring_layer(slug, year)
    age, old, life, ring = R['age'], R['old'], R['life'], R['ring']
    rng = seed(slug + (face or ':face'))
    U = rng.uniform; P = lambda p: rng.random() < p
    light_old = mean > .62 and age > 40              # the oldest pale sleeves are the most handled
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    xi = xx.astype(np.int32); yi = yy.astype(np.int32)
    if face:
        fine = rng.random((S, S)).astype(np.float32); crumbs = (rng.random((S, S)) > .9).astype(np.float32)
        gp, gfield = U(.45, .65), rng.random((S, S)).astype(np.float32)
    else:
        f = R['front']; fine, crumbs, gp, gfield = f['fine'], f['crumbs'].astype(np.float32), f['gp'], f['gfield']
    if light_old:
        gp = .65 + (gp - .45) * .75                  # U(.45,.65) -> U(.65,.8)
    g = _blur_wrap(gfield - .5, 1.1, 1.1)            # dirt lodges in small clumps, not single pixels
    grime = (phi(g / (g.std() + 1e-6)) < gp).astype(np.float32)   # which rubbed fibres held dirt
    hr = seed(slug + (face or ':face') + ':hand')    # the hand and the ringless sleeve's own marks (a separate stream)
    ringless_worn = not ring and age > 20
    Drr, dsq = rrect()
    corr = Drr - dsq                                 # <= 0: how much nearer the rounded outline is
    dist = [yy + corr, S - 1 - yy + corr, xx + corr, S - 1 - xx + corr]    # top, bottom, left, right
    alongidx = [xi, xi, yi, yi]
    opening = 2 if face else 3                       # the open side: right on the front, left seen from the back
    Pi = np.zeros((S, S), np.float32)
    Pb = np.zeros((S, S), np.float32)
    esoil = np.zeros((S, S), np.float32)

    # 1. Shelf friction along the cut edges, and the crushed cut edge itself.
    shelf = U(1.2, 1.7) if P(.5) else 1.0            # the top edge takes the shelf
    profs, gaps = [], []
    for s in range(4):
        t = np.arange(S, dtype=np.float32)
        base = S * U(.0016, .003) * (.45 + .6 * life) * (shelf if s == 0 else 1)
        prof = base * (.35 + 1.3 * noise1(rng, S, S * .05) ** 2)
        g0 = U(.28, .38); gap = smooth(g0, g0 + .06, noise1(rng, S, S * .03, 3))    # runs where the edge is intact
        prof *= gap; gaps.append(gap)
        for _ in range(int(U(1, 5) * life) + (1 if P(.5) else 0)):                    # solid chips
            c, w = U(0, S), U(4, 16) * (.6 + .5 * life); depth = U(3, 9) * (.5 + .6 * life)
            bite = np.sqrt(np.clip(1 - ((t - c) / w) ** 2, 0, 1)) * (.6 + .4 * noise1(rng, S, 3, 2))
            prof = np.maximum(prof, depth * bite)
        prof *= 1 + U(.5, 1.8) * (np.exp(-t / (S * .02)) + np.exp(-(S - 1 - t) / (S * .02)))
        profs.append(prof)
        amp = U(.08, .3) * life * (shelf if s == 0 else 1) * (1.3 if s == 1 else 1) * (1.3 if light_old and s == opening else 1)
        e = S * U(.002, .0045)
        amp, e = min(.95, amp * edgew), e * (1 + 1.1 * (edgew - 1))   # per-record edge wear (wear.edge): stronger, wider frost
        Pi = np.maximum(Pi, amp * np.exp(-np.maximum(dist[s], 0) / e) * (.25 + .75 * noise1(rng, S, S * .06))[alongidx[s]])
    if edgew > 1:                                    # wear.edge: a broad, patchy rub along every edge, heaviest near the
        er = seed(slug + (face or ':face') + ':edgewide')   # corners, for art that hides wear in the middle
        k = min(1.0, (edgew - 1) / 3)
        for s in range(4):
            t = np.arange(S, dtype=np.float32)
            wide = S * er.uniform(.012, .028) * (.6 + .4 * k)
            patch = smooth(.25, .7, noise1(er, S, S * .04, 3)) * (.55 + .45 * noise1(er, S, S * .012, 2))
            patch *= 1 + .8 * (np.exp(-t / (S * .06)) + np.exp(-(S - 1 - t) / (S * .06)))     # corners take more
            amp = er.uniform(.35, .6) * k * (1.25 if s == 1 else 1)
            Pi = np.maximum(Pi, np.clip(amp * patch[alongidx[s]], 0, .95) * np.exp(-(np.maximum(dist[s], 0) / wide) ** 1.3))
    if light_old:                                    # a faint soiled band along the opening, where hands go in
        along = smooth(.3, .7, noise1(rng, S, S * .06))
        esoil = np.exp(-np.maximum(dist[opening], 0) / (S * U(.006, .012))) * along[alongidx[opening]] * U(.3, .45) * 1.3
    elif ringless_worn and mean > .55:               # an old pale sleeve with no ring was still handled there
        along = smooth(.3, .7, noise1(hr, S, S * .06))
        esoil = np.exp(-np.maximum(dist[opening], 0) / (S * hr.uniform(.006, .012))) * along[alongidx[opening]] * hr.uniform(.3, .45)
    if not ring and P(.9):                           # no ring: the bottom edge took the shelf instead
        along = smooth(.35, .7, noise1(rng, S, S * .08))
        Pb = np.maximum(Pb, np.exp(-np.maximum(dist[1], 0) / (S * U(.008, .016))) * along[xi] * U(.45, .7) * max(life, .7))
    # the hand that holds it: sparse chips near one side (every ringless sleeve, some others)
    if P(.95 if not ring else .25 + .3 * old):
        side = 2 if P(.5) else 3; w = S * (U(.03, .07) if ring else U(.05, .09))
        hd = U(.03, .07) if ring else U(.09, .14)
        Pi = np.maximum(Pi, np.exp(-np.maximum(dist[side], 0) / w) * smooth(.45, .8, noise1(rng, S, S * .1))[yi] * hd * max(life, .8))
        if not ring:                                 # and the thumb that rubs the same side: a crisp patch of flakes
            du = dist[side] - S * hr.uniform(.03, .06); dv = yy - S * hr.uniform(.35, .65)
            Pi = np.maximum(Pi, hr.uniform(.12, .2) * max(life, .8) * np.exp(-(du / (S * .04)) ** 2 - (dv / (S * .1)) ** 2))

    # 2. Corners. The outline is rounded, so a bumped corner crushes the arc: a torn bite of card that
    #    hugs the curve, deepest near its middle, with flakes spreading in from it.
    rc = RC * S
    CORNERS = [(0, 0, 1, 1), (S - 1, 0, -1, 1), (0, S - 1, 1, -1), (S - 1, S - 1, -1, -1)]
    corners = []
    for (px, py, sx_, sy_) in CORNERS:
        if not P(.35 + .5 * old):
            continue
        ccx, ccy = px + sx_ * rc, py + sy_ * rc                         # the arc's centre
        mx, my = ccx - sx_ * rc / math.sqrt(2), ccy - sy_ * rc / math.sqrt(2)   # its midpoint on the outline
        W = int(rc + 34)
        ys = slice(0, W) if sy_ > 0 else slice(S - W, S); xs = slice(0, W) if sx_ > 0 else slice(S - W, S)
        wx, wy = xx[ys, xs] - ccx, yy[ys, xs] - ccy
        ux, uy = -sx_ / math.sqrt(2), -sy_ / math.sqrt(2)               # outward along the diagonal
        a = rc * np.arctan2(wx * uy - wy * ux, wx * ux + wy * uy)       # signed length along the outline
        dep = U(2.5, 7) * (.6 + .5 * life)
        span = U(9, 24) * (.7 + .4 * life)
        a0 = U(-.35, .35) * rc * math.pi / 4
        nz = .7 + .6 * noise1(rng, 512, U(2.5, 5), 3)                  # the bite's depth wanders along the edge
        corners.append((ys, xs, a.astype(np.float32), dep, span, a0, nz))
        # the flakes hug the crushed outline, a few px in, not a round cloud spreading into the face
        amp_c, dec = U(.1, .28) * life, S * U(.005, .012)
        Pi[ys, xs] = np.maximum(Pi[ys, xs], amp_c * np.exp(-np.maximum(Drr[ys, xs], 0) / dec) * np.exp(-((a - a0) / (1.6 * span)) ** 2))
    jag = (fine - .5) * 1.4

    # 3. Cracks, scratches and striations, drawn at 2x.
    cr = Image.new('L', (N, N), 0); dcr = ImageDraw.Draw(cr)
    ck = seed(slug + (face or ':face') + ':crack')   # each crack's own walk (so the draws after it stay put)
    for (px, py, sx_, sy_) in CORNERS:
        if not P(.2 + .45 * old):
            continue
        if P(.3):                                    # dog-ear fold across the rounded corner
            d1, d2 = S * U(.032, .06), S * U(.032, .06)
            x0, y0, x1, y1 = px + sx_ * d1, py + sy_ * (inset(d1) + 1.5), px + sx_ * (inset(d2) + 1.5), py + sy_ * d2
            crack(dcr, ck, x0, y0, math.atan2(y1 - y0, x1 - x0), math.hypot(x1 - x0, y1 - y0), U(.6, .95), 2)
            Pi = np.maximum(Pi, ((np.abs(xx - px) / d1 + np.abs(yy - py) / d2) < 1) * U(.18, .4) * life)
        fan = math.atan2(sy_, sx_) + ck.uniform(-.35, .35)   # a fan of long, nearly parallel hairlines in from the arc
        for _ in range(int(U(1.5, 5.5) * life)):
            along = S * U(0, .05); off = inset(along) + 1.5
            x0, y0 = (px + sx_ * along, py + sy_ * off) if P(.5) else (px + sx_ * off, py + sy_ * along)
            crack(dcr, ck, x0, y0, fan + U(-.6, .6) * .25, S * U(.02, .07) * (.75 + .35 * life), U(.6, .95), int(rng.choice([1, 2, 2])))
    for _ in range(int(U(2, 9) * old * life)):      # short hairline cracks in from an edge
        s = int(rng.integers(0, 4)); pos = U(.05, .95) * S
        x0, y0, hd = [(pos, 1, math.pi / 2), (pos, S - 2, -math.pi / 2), (1, pos, 0), (S - 2, pos, math.pi)][s]
        crack(dcr, ck, x0, y0, hd + U(-.5, .5), S * U(.01, .045), U(.55, .9), int(ck.choice([1, 2, 2])))
    if P(.35 * old) or ringless_worn:                # long fold cracks down the seam or opening side
        for _ in range(int(rng.integers(1, 3))):
            x0 = S * U(.01, .07); x0 = x0 if P(.5) else S - x0
            crack(dcr, ck, x0, S * U(.05, .5), math.pi / 2 + U(-.1, .1), S * U(.1, .3), U(.45, .75), 2)
    crs = cr.resize((S, S), Image.BOX)
    cracks = np.asarray(crs).astype(np.float32) / 255
    flake = np.asarray(crs.filter(ImageFilter.GaussianBlur(.8))).astype(np.float32) / 255
    Pi = np.maximum(Pi, np.clip(flake * 2.2, 0, 1) * U(.1, .22))     # the ink flakes just beside a crack

    sc = Image.new('L', (N, N), 0); dsc = ImageDraw.Draw(sc)
    a0 = U(0, math.pi)                               # slide scratches: one prevailing direction
    ks = 1 if ring else 1.5                          # no ring: more slides
    for _ in range(int(U(0, 1) ** 1.4 * 22 * life * ks) + int(U(1, 4) * ks)):
        L = S * math.exp(U(math.log(.015), math.log(.09))); a = a0 + rng.normal(0, .14)
        x0, y0 = U(.03, .97) * S, U(.03, .97) * S
        bezier_line(dsc, x0, y0, x0 + math.cos(a) * L, y0 + math.sin(a) * L, U(-.08, .08) * L,
                    U(80, 170) if P(.8) else U(170, 240), 14, .7)
    for _ in range(int(U(0, 3) * life)):            # the odd longer hairline
        L = S * math.exp(U(math.log(.03), math.log(.15))); a = U(0, math.pi)
        x0, y0 = U(0, S), U(0, S)
        bezier_line(dsc, x0, y0, x0 + math.cos(a) * L, y0 + math.sin(a) * L, U(-.06, .06) * L,
                    U(60, 150), 28, .5, gaps=[(g0, g0 + U(.03, .12)) for g0 in rng.uniform(.1, .9, int(U(0, 3)))])
    tk = Image.new('L', (N, N), 0); dtk = ImageDraw.Draw(tk)
    for s in range(4):                               # shelf scuffs: short ticks in from the edge, in bunches
        dens_al = smooth(.45, .8, noise1(rng, S, S * .05))
        for _ in range(int(U(8, 40) * life * (1 + old) * (shelf if s == 0 else 1) * (1.5 if light_old else 1))):
            pos = U(0, S)
            if rng.random() > dens_al[int(pos)] * .9 + .1: continue
            L = U(2, 11) * (.6 + .4 * life); off = U(0, 1.5) + inset(min(pos, S - 1 - pos))
            a = [math.pi / 2, -math.pi / 2, 0, math.pi][s] + rng.normal(0, .22)
            x0, y0 = [(pos, off), (pos, S - 1 - off), (off, pos), (S - 1 - off, pos)][s]
            dtk.line([(x0 * 2, y0 * 2), ((x0 + math.cos(a) * L) * 2, (y0 + math.sin(a) * L) * 2)], fill=int(U(110, 230)), width=2)
    st = Image.new('L', (N, N), 0); dst = ImageDraw.Draw(st)
    n_stri = int(U(0, 1.6) * old + (U(.6, 2.2) if not ring else 0))
    if mean > .62 and age <= 40:                     # on pale stock grit reads as pencil hatching: only the oldest
        n_stri = 0
    for _ in range(n_stri):                          # grit dragged across the face
        pcx, pcy = S * U(.15, .85), S * U(.1, .9); pa = a0 + rng.normal(0, .25)
        Lp, Wp = S * U(.08, .22), S * U(.02, .05)
        for _k in range(int(U(25, 70) * max(.5, life))):
            u, v = rng.normal(0, .45), rng.normal(0, .45)
            px2 = pcx + u * Lp * math.cos(pa) - v * Wp * math.sin(pa); py2 = pcy + u * Lp * math.sin(pa) + v * Wp * math.cos(pa)
            L = U(8, 45); aa = pa + rng.normal(0, .04)
            dst.line([(px2 * 2, py2 * 2), ((px2 + math.cos(aa) * L) * 2, (py2 + math.sin(aa) * L) * 2)], fill=int(U(140, 255)), width=2)
    stri = np.asarray(st.resize((S, S), Image.BOX)).astype(np.float32) / 255
    Pi = np.maximum(Pi, stri * U(.2, .4) * life)
    scratches = np.maximum(np.asarray(sc.resize((S, S), Image.BOX)).astype(np.float32) / 255, stri * .16)
    ticks = np.asarray(tk.resize((S, S), Image.BOX)).astype(np.float32) / 255

    # 4. On the oldest sleeves, a small tear at one edge, showing the card.
    tear = np.zeros((S, S), np.float32)
    if age > 15 and P(.1 + .25 * old):
        side = int(rng.integers(0, 4)); pos = U(.15, .85) * S
        wa, dp = S * U(.012, .03), S * U(.006, .016)
        u, v = [(xx, dist[0]), (xx, dist[1]), (yy, dist[2]), (yy, dist[3])][side]
        shape = np.exp(-((u - pos) / wa) ** 4 - (v / dp) ** 2)
        tear = (shape - .35 * rng.random((S, S)) - .25 * noise1(rng, S, 6)[np.clip(u, 0, S - 1).astype(np.int32)] > .45).astype(np.float32)

    lay = dict(stri=stri, ticks=ticks, grime=grime, Pi=Pi, Pb=Pb, esoil=esoil, Drr=Drr,
               profs=profs, gaps=gaps, dist=dist, alongidx=alongidx, jag=jag, corners=corners, crumbs=crumbs,
               cracks=cracks, scratches=scratches, tear=tear)
    _SURF.clear(); _SURF[key] = lay
    return lay


def make_mask(slug, year, dens=1.0, edgek=1.0, face='', mean=.5, edgew=1.0):
    """dens and edgek scale the amount of wear without moving any of it, so every level is the same sleeve.
    face '' is the front, ':back' the back (the ring mirrored, everything else its own). mean is the
    cover's mean luminance (pale stock is handled differently).
    Returns channels: 0 abrasion (exposed paper), 1 crushed edge (card), 2 dirt (shows on light ink),
    3 the rim's impression line, 4 the rim's stipple, 5 grey grain in rubbed white stock."""
    R = ring_layer(slug, year)
    L = surface_layer(slug, year, face, mean, edgew)
    edgek = edgek * (1 + .3 * (edgew - 1))          # and a somewhat wider crushed strip and corners
    fl = (lambda a: a[:, ::-1]) if face else (lambda a: a)      # the disc presses both faces, mirrored
    T, Trub, V, Vb, Tc = fl(R['T']), fl(R['Trub']), fl(R['V']), fl(R['Vb']), fl(R['Tc'])
    Pi = np.maximum(fl(R['Pi']), L['Pi'])
    Pb = np.maximum(fl(R['Pb']), L['Pb'])
    Pbc = fl(R['Pbc'])
    light = mean > .62
    light_old = light and R['age'] > 40
    scuff = light and not light_old                  # young and mid-aged pale stock: a bar scuffs rather than soils
    ab_i = down(flakes(Pi * dens, T) * V)
    ab_b = np.maximum(down(flakes(Pb * dens, Trub) * Vb) * R['rub_tone'],       # a bar's frost, grey or white per sleeve
                      down(flakes(Pbc * dens, Trub) * fl(R['Vbc'])))            # and its bright core
    ab = np.maximum(ab_i, ab_b)
    lk = min(1.0, .6 + .4 * dens)
    lines = np.maximum.reduce([L['cracks'], L['scratches'], L['ticks']]) * lk
    mask = np.maximum(ab, lines)

    # the crushed strip: solid at the very edge, flaking (holes where the ink held) further in
    band = np.zeros((S, S), np.float32); core = np.zeros((S, S), np.float32)
    for prof, dist, idx in zip(L['profs'], L['dist'], L['alongidx']):
        pr = prof[idx] * edgek; dj = dist + L['jag']
        band = np.maximum(band, np.clip(pr - dj + .5, 0, 1))
        core = np.maximum(core, np.clip(np.minimum(pr, 1.2 + .25 * pr) - dj + .5, 0, 1))
    edge = np.maximum(core, band * down(smooth(-.012, .012, .8 - T)))
    for ys, xs, a, dep, span, a0, nz in L['corners']:           # crushed corners, torn along the arc
        depth = dep * edgek * nz[np.clip(a + 256, 0, 511).astype(np.int32)] * np.sqrt(np.clip(1 - ((a - a0) / span) ** 2, 0, 1))
        edge[ys, xs] = np.maximum(edge[ys, xs], np.clip(depth - (L['Drr'][ys, xs] + L['jag'][ys, xs] * 1.5) + .5, 0, 1))
    gf = .1 if light else .3                         # on pale stock the cut line breaks fully in its gaps and is lighter
    cut = np.maximum.reduce([np.clip(1.3 - dist, 0, 1) * (gf + (1 - gf) * g[idx]) for dist, g, idx in zip(L['dist'], L['gaps'], L['alongidx'])])
    edge = np.maximum(edge, cut * (.45 if light else .6))                              # the cut itself
    edge = np.maximum(edge, L['tear'])
    edge *= 1 - L['crumbs'] * .6                                                        # dark crumbs along the crushed line

    Pall = np.maximum.reduce([Pi, Pb, Pbc]) * dens
    dense = smooth(.06, .22, Pall) if light else smooth(.12, .35, Pall)             # only a real rub holds grime
    kg = (.8 if light else .7) * (.3 + .7 * float(smooth(10, 25, R['age'])))      # and a young sleeve has gathered little
    kr = 1 if light_old else (.7 if scuff else 1) * (1 - .45 * smooth(.1, .3, fl(R['Pi'])))   # a ring's core on pale ink: scuffed, not pencilled
    dirt = np.maximum(ab_i * kg * kr, ab_b * kg * (.35 / .8 if scuff else 1)) * L['grime'] * dense
    dirt = np.maximum(dirt, L['cracks'] * (.45 if light else .8) * lk)             # (on white a crack is a hairline, not a vein)
    dirt = np.maximum(dirt, L['scratches'] * .25 * lk)
    dirt = np.maximum(dirt, L['ticks'] * .6 * lk)
    dirt = np.maximum(dirt, down(flakes(L['stri'] * .8 * dens, T)) * .1)
    if L['esoil'].any():
        dirt = np.maximum(dirt, down(flakes(L['esoil'] * dens, Tc[::-1])) * .55)
    Tf = np.clip((V - .66) / .3, .03, 1)                                                # fibre-fine: the line breaks into grain, not dashes
    dline = down(flakes(fl(R['Dl']) * (.45 + .55 * dens), Tf))
    dst = down(flakes(fl(R['Ds']) * dens, Tc))
    rub = np.minimum(np.maximum(fl(R['Pb']), .6 * Pbc), 1)                           # the rub bars leave grey grain too,
    soil = np.maximum(fl(R['soil']), rub * (.12 if scuff else .3))                  # but only a little on a younger pale sleeve
    dsoil = down(flakes(soil * dens, Tc))
    out = np.stack([mask, edge, dirt, dline, dst, dsoil], -1)
    out *= (L['Drr'] >= -1.5)[..., None]             # outside the rounded outline: the art, untouched (if anything shows it unclipped)
    return np.clip(out, 0, 1), R['life'], R['age'], R['ring']


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


def lum_of(cov):
    return cov @ np.array([.2126, .7152, .0722], np.float32)


def bake(cov, mask, k, slug, age):
    rng = seed(slug + ':bake')
    Lum = lum_of(cov)
    mean = float(Lum.mean())
    chroma = cov.max(-1) - cov.min(-1)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    if mean > .62 and age > 30:                               # old light stock has aged warm; fresh fibres rubbed bare have not
        Drr, _ = rrect()
        amt = (min(.35, (age - 30) / 60) + .12 * np.exp(-np.maximum(Drr, 0) / (S * .05)))[..., None]
        cov = cov * (1 - amt * (1 - WARM))
    ch = lambda i: np.clip(mask[..., i] * k, 0, 1)[..., None]
    # worn-through ink shows the paper; over near-white ink the coating only scuffs darker in its own hue
    s = smooth(.8, .93, Lum)[..., None]
    a = ch(0) * (1 - .35 * s)
    col = PAPER_WHITE * (1 - s) + cov * (.86 if mean > .62 else .92) * s
    out = cov * (1 - a) + col * a
    pale = smooth(.72, .9, Lum)[..., None]                    # only on pale ink can you see grime
    lowc = smooth(.14, .05, chroma)[..., None]                # and a line only on neutral pale ink, not pastel
    out = out * (1 - ch(2) * pale * .85 * (.6 + .4 * lowc) * (1 - DIRT_TINT))
    lineness = lowc * float(smooth(12, 18, age))              # a young sleeve has no impression line yet
    out = out * (1 - ch(3) * pale * lineness * .9 * (1 - LINE_TINT))
    ast = ch(4) * pale * (1 - lineness) * .42 * (1 - .6 * ch(0))   # instead, a faint broken scuff in the ink's own hue
    out = out * (1 - ast * .32)                               # (not stacked on a flake that already scuffed)
    so = ch(5) * s * .4 * float(smooth(12, 35, age)) * (1 - .6 * ch(2) * pale)   # rubbed white stock holds grey grain
    out = out * (1 - so) + SOIL * so                          # (where grime did not already take the spot)
    ae = np.clip(mask[..., 1], 0, 1)[..., None]
    se = smooth(.6, .85, Lum)[..., None] * float(smooth(8, 30, age))   # a young pale sleeve's cut is still pale card
    fray = smooth(-.8, .8, gnoise(seed(slug + ':fray'), S, .9))[..., None]   # and the grime sits in its fibres, not as a flat fill
    se = se * (.45 + .55 * fray)
    ecol = (BOARD * (1 - se) + BOARD_DIRTY * se) * (.9 + .2 * rng.random((S, S), np.float32))[..., None]
    out = out * (1 - ae) + ecol * ae
    tooth = gnoise(rng, S, .6) * .65 + gnoise(rng, S, 1.8) * .35                # the card's tooth shows on light stock
    kt = .016 if age > 40 else .011
    out = out * (1 - (smooth(.6, .9, Lum) * kt * (1 + .5 * min(1, age / 30)) * np.clip(tooth, -2.5, 2.5))[..., None])
    th = rng.uniform(0, 2 * math.pi)                          # scanner-lamp falloff
    u = (((xx - S / 2) * math.cos(th) + (yy - S / 2) * math.sin(th)) / (S * .72))[..., None]
    out = out + (1 - out) * np.clip(-u, 0, 1) ** 1.6 * rng.uniform(.02, .04)
    out = out * (1 - np.clip(u, 0, 1) ** 1.6 * rng.uniform(.035, .06))
    t = paper(); n = t.shape[0]
    t = np.roll(np.tile(t, (S // n + 2, S // n + 2, 1)), (-int(rng.integers(0, n)), -int(rng.integers(0, n))), (0, 1))[:S, :S]
    pa = t[:, :, 3:4] * (.85 if mean > .62 else .8 + .2 * mean)
    out = out * (1 - pa) + t[:, :, :3] * pa
    return Image.fromarray((np.clip(out, 0, 1) * 255 + .5).astype(np.uint8))


def job(a):
    slug = a['slug']
    level = (a.get('wear') or {}).get('level', 'med')
    level = level if level in LEVELS else 'med'
    edgew = float((a.get('wear') or {}).get('edge', 1.0))   # per-record: more edge wear where the art hides the rest
    cov = load_square(ROOT / a['art'])
    lum = float(lum_of(cov).mean())
    tone = 1 + .3 * float(smooth(.6, .85, lum))           # light covers carry heavier wear
    masks = {}
    for lv in (LEVELS if LEVELS_DIR else [level]):
        dens, ek, _ = LEVELS[lv]
        masks[lv] = make_mask(slug, a.get('year'), dens * tone, ek, '', lum, edgew)
    mask, life, age, ring = masks[level]; k = LEVELS[level][2]
    MASKS.mkdir(parents=True, exist_ok=True)
    Image.fromarray((mask[..., :3] * 255 + .5).astype(np.uint8), 'RGB').save(MASKS / f'{slug}.png')
    bake(cov, mask, k, slug, age).save(WORN / f'{slug}.jpg', 'JPEG', quality=88, optimize=True, progressive=True)
    back = None
    if a.get('art_back') and (ROOT / a['art_back']).exists():
        covb = load_square(ROOT / a['art_back'], pad=True)
        lumb = float(lum_of(covb).mean())
        dens, ek, _ = LEVELS[level]
        mb = make_mask(slug, a.get('year'), dens * (1 + .3 * float(smooth(.6, .85, lumb))), ek, ':back', lumb, edgew)[0]
        bake(covb, mb, k, slug + ':back', age).save(WORN / f'{slug}-back.jpg', 'JPEG', quality=86, optimize=True, progressive=True)
        back = f'assets/40/worn/{slug}-back.jpg'
    if LEVELS_DIR:
        (LEVELS_DIR / 'lv').mkdir(parents=True, exist_ok=True); (LEVELS_DIR / 'art').mkdir(parents=True, exist_ok=True)
        for lv, (m, _l, _a, _r) in masks.items():
            bake(cov, m, LEVELS[lv][2], slug, age).resize((1000, 1000), Image.LANCZOS).save(LEVELS_DIR / 'lv' / f'{slug}-{lv}.jpg', 'JPEG', quality=84, optimize=True, progressive=True)
        Image.open(ROOT / a['art']).convert('RGB').resize((1000, 1000), Image.LANCZOS).save(LEVELS_DIR / 'art' / f'{slug}.jpg', 'JPEG', quality=84, optimize=True, progressive=True)
    _RING.clear(); _SURF.clear()
    return slug, a.get('year'), round(life, 2), ring, back


if __name__ == '__main__':
    WORN.mkdir(parents=True, exist_ok=True)
    if '--paper' in args or not PAPER_TILE.exists():
        paper_tile(); print('paper tile', PAPER_TILE.stat().st_size // 1024, 'KB')
    data_path = ROOT / 'data/albums.json'
    # Only records that are definitely on the site: the numbered days and the bonus. A record gets its
    # sleeve when it is given a day (or name it with --only).
    albums = [a for a in json.loads(data_path.read_text())['albums']
              if a.get('art') and (a['slug'] in ONLY if ONLY else (a.get('no') or a.get('bonus')))]
    with Pool(JOBS) as pool:
        results = pool.map(job, albums, chunksize=1)
    backs = {}
    for slug, year, life, ring, back in results:
        backs[slug] = back
        print(f'{slug:52} {year} life={life:.2f} {"ring" if ring else "    "} {(WORN / (slug + ".jpg")).stat().st_size // 1024}KB')
    doc = json.loads(data_path.read_text())                   # re-read: don't clobber edits made meanwhile
    for a in doc['albums']:
        if a['slug'] in backs:
            a['art_worn'] = f"assets/40/worn/{a['slug']}.jpg"
            if backs[a['slug']]: a['art_back_worn'] = backs[a['slug']]
            a['wear'] = {**(a.get('wear') or {}), 'level': (a.get('wear') or {}).get('level', 'med')}
    data_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
