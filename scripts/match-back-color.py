#!/usr/bin/env python3
"""Match a back cover's flat ground colour to the front's (a scanned or photographed back runs darker,
shifted, or vignetted).

  scripts/match-back-color.py assets/40/<slug>-back.jpg 226,42,40     # then make-wear.py --only <slug>

Finds the ground (pixels close to the back's own ground colour), measures it locally so a vignette
or uneven light is flattened too, and moves it to the target. Type and art keep their colours; their
antialiased edges move only as far as they are made of the ground. Used for Run the Jewels 2
(its back measured 196,34,53 against the front's 226,42,40).
"""
import sys
import numpy as np
from PIL import Image


def box(x, r, ax):
    x = np.moveaxis(x, ax, 0)
    p = np.pad(x, ((r + 1, r),) + ((0, 0),) * (x.ndim - 1), mode="edge"); c = np.cumsum(p, 0)
    return np.moveaxis((c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1), 0, ax)


def blur(x, r):
    for _ in range(3): x = box(box(x, r, 0), r, 1)      # three box passes ≈ a Gaussian
    return x


def main():
    path, target = sys.argv[1], np.array([float(v) for v in sys.argv[2].split(",")], np.float32)
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    seed = np.median(a.reshape(-1, 3), 0)                 # the ground is most of a flat back
    ground = (np.linalg.norm(a - seed, axis=-1) < 60).astype(np.float32)
    den = blur(ground, 40) + 1e-4
    field = np.stack([blur(a[..., i] * ground, 40) / den for i in range(3)], -1)   # the ground, locally
    w = np.exp(-(np.linalg.norm(a - field, axis=-1) / 55) ** 2)[..., None]
    out = np.clip(a + w * (target - field), 0, 255).astype(np.uint8)
    Image.fromarray(out).save(path, quality=92, optimize=True)
    print(path, "ground", seed.round(), "->", target.round())


if __name__ == "__main__":
    main()
