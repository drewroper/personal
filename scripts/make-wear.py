#!/usr/bin/env python3
"""Procedural record-sleeve wear: ring wear, rubbed edges and corners, scratches,
scuffs, grain and grime. Writes two RGBA layers to assets/40/wear/:
  wear-light.png  white fibre exposure, to screen over a cover
  wear-dark.png   grime and edge shadow, to multiply over a cover
Deterministic per seed so the site and the story renderer agree."""
import sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = int(sys.argv[1]) if len(sys.argv) > 1 else 1400
rng = np.random.default_rng(40)

def blur(a, r):
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255

def noise(scale, octaves=3, gain=.5):
    out = np.zeros((S, S), np.float32); amp = 1; tot = 0
    for o in range(octaves):
        n = rng.random((max(2, S // scale), max(2, S // scale))).astype(np.float32)
        n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)).astype(np.float32) / 255
        out += n * amp; tot += amp; amp *= gain; scale = max(2, scale // 2)
    return out / tot

yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
cx, cy = S * .505, S * .49
r = np.hypot(xx - cx, yy - cy)

# 1. Ring wear: the record's edge rubbing through the sleeve. A noisy band, heavier top-right.
R = S * .455
band = np.exp(-((r - R) / (S * .022)) ** 2)
angle = np.arctan2(yy - cy, xx - cx)
lobe = .55 + .45 * np.cos(angle - .8) ** 2
ring = band * lobe * (0.35 + noise(40) * .9) * (noise(6, 2) > .28)
ring = blur(ring, 1.2) * 1.15
# faint inner ring from the label area
label = np.exp(-((r - S * .17) / (S * .012)) ** 2) * noise(30) * .35

# 2. Edge and corner wear: rubbed bands along the edges, corners hit hardest.
d = np.minimum(np.minimum(xx, S - 1 - xx), np.minimum(yy, S - 1 - yy))
edge = np.exp(-d / (S * .018)) * (0.4 + noise(24) * 1.0)
corner = np.zeros_like(edge)
for (px, py) in [(0, 0), (S, 0), (0, S), (S, S)]:
    corner += np.exp(-np.hypot(xx - px, yy - py) / (S * .07))
edge = np.clip(edge + corner * (.5 + noise(20) * .8) * .9, 0, 1.4)
edge = edge * (noise(5, 2) > .22)
edge = blur(edge, 1.0)

# 3. Scratches: thin bright hairlines, a few long.
scr = Image.new('L', (S, S), 0); dr = ImageDraw.Draw(scr)
for _ in range(70):
    L = rng.uniform(S * .05, S * .55); a = rng.uniform(0, math.pi)
    x0 = rng.uniform(0, S); y0 = rng.uniform(0, S)
    x1 = x0 + math.cos(a) * L; y1 = y0 + math.sin(a) * L
    w = int(rng.choice([1, 1, 1, 2])); v = int(rng.uniform(90, 230))
    dr.line([(x0, y0), (x1, y1)], fill=v, width=w)
scratch = np.asarray(scr).astype(np.float32) / 255
scratch = blur(scratch, .5)

# 4. Scuffs: soft pale patches, and fine speckle.
scuff = np.zeros((S, S), np.float32)
for _ in range(9):
    px, py = rng.uniform(0, S), rng.uniform(0, S); rad = rng.uniform(S * .06, S * .2)
    scuff += np.exp(-np.hypot(xx - px, yy - py) / rad) * rng.uniform(.15, .45)
scuff = scuff * noise(12) * 1.2
speck = (rng.random((S, S)) > .9975).astype(np.float32)
speck = blur(speck, .6) * 2.2

light = np.clip(ring * .9 + label + edge * .75 + scratch * .9 + scuff + speck, 0, 1)
light = light * (0.75 + noise(3, 1) * .25)   # paper grain modulation

# 5. Grime: dark, in the ring's shadow, the corners and a few smudges.
grime = np.exp(-((r - R * 1.03) / (S * .03)) ** 2) * .35 * (.5 + noise(50) * .8)
grime += corner * .35 * (0.5 + noise(28) * .6)
for _ in range(5):
    px, py = rng.uniform(0, S), rng.uniform(0, S); rad = rng.uniform(S * .08, S * .25)
    grime += np.exp(-np.hypot(xx - px, yy - py) / rad) * rng.uniform(.06, .16) * noise(16)
grime += (rng.random((S, S)) > .9992).astype(np.float32) * .9   # dirt specks
grime = np.clip(blur(grime, .8), 0, 1)

out = ROOT / 'assets/40/wear'; out.mkdir(parents=True, exist_ok=True)
Image.fromarray(np.dstack([np.full((S, S), 255, np.uint8)] * 3 + [(light * 255).astype(np.uint8)]), 'RGBA').save(out / 'wear-light.png', optimize=True)
Image.fromarray(np.dstack([np.zeros((S, S), np.uint8)] * 3 + [(grime * 255).astype(np.uint8)]), 'RGBA').save(out / 'wear-dark.png', optimize=True)
print('wrote', out / 'wear-light.png', out / 'wear-dark.png', S)
