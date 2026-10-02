#!/usr/bin/env python3
"""WebP copies of the worn sleeves, for the page (the JPEGs stay the masters: stories and wear read them).

  scripts/make-webp.py            # only sleeves whose JPEG is newer than its WebP
  scripts/make-webp.py --force    # all of them

For every assets/40/worn/<name>.jpg writes assets/40/worn/webp/<name>.webp (full 1200px, for desktop
and Retina), <name>-800.webp (phones) and <name>-360.webp (the Index grid). Quality 82 holds the
wear's grain and scratches; at 2x zoom it is indistinguishable from the JPEG. Run it after make-wear.py.
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "40" / "worn"
OUT = SRC / "webp"
SIZES = ((None, 82), (800, 82), (360, 80))          # (width or full, quality)
FORCE = "--force" in sys.argv


def main():
    OUT.mkdir(exist_ok=True)
    made = 0
    for jpg in sorted(SRC.glob("*.jpg")):
        targets = [OUT / (jpg.stem + (f"-{w}" if w else "") + ".webp") for w, _ in SIZES]
        if not FORCE and all(t.exists() and t.stat().st_mtime >= jpg.stat().st_mtime for t in targets):
            continue
        im = Image.open(jpg).convert("RGB")
        for (w, q), t in zip(SIZES, targets):
            out = im if not w or w >= im.width else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            out.save(t, "WEBP", quality=q, method=6)
        made += 1
        print(jpg.name)
    print(f"{made} sleeve(s) written")


if __name__ == "__main__":
    main()
