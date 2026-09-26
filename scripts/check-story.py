#!/usr/bin/env python3
"""Check a story video before it goes to Drew: every frame, not a sample.

  scripts/check-story.py out/stories/instagram/story-day-04-....mp4

Fails if any frame shows a dead strip where the art slid off the canvas: a margin column that
is flat from the top of the frame to the bottom (left/right of the cover), or a margin row flat
across the full width (top/bottom), 24+ px wide. Dark art dithers dark too, but never flat edge
to edge like an empty canvas. Also fails if the background ever stops moving between frames."""
import subprocess, sys
import numpy as np
import imageio_ffmpeg

W, H = 1080, 1920
EDGE = 80                             # the margins outside the cover (cover spans x 84-996)


def longest_flat(arr):
    run = best = 0
    for v in arr:
        run = run + 1 if v < 8 else 0
        best = max(best, run)
    return best


def check(path):
    p = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-loglevel', 'error', '-i', path,
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    n, worst, still, prev = 0, (0, -1), [], None
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H:
            break
        g = np.frombuffer(b, np.uint8).reshape(H, W).astype(np.int16)
        cols = g.max(0) - g.min(0)                         # flat top to bottom?
        rows = g.max(1) - g.min(1)                         # flat side to side?
        m = max(longest_flat(cols[:EDGE]), longest_flat(cols[-EDGE:][::-1]),
                longest_flat(rows[:240]), longest_flat(rows[-240:][::-1]))
        if m > worst[0]:
            worst = (m, n)
        band = g[1480:1900]
        if prev is not None and np.array_equal(band, prev):
            still.append(n)
        prev = band.copy(); n += 1
    ok = worst[0] <= 24 and not still
    print(f"{path}: {n} frames, longest flat strip {worst[0]}px (frame {worst[1]}), "
          f"frames where the ground stood still: {len(still)} -> {'OK' if ok else 'FAIL'}")
    return ok


if __name__ == '__main__':
    sys.exit(0 if all(check(f) for f in sys.argv[1:]) else 1)
