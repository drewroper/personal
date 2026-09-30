#!/usr/bin/env python3
"""A week of Instagram stories side by side, playing in sync, on one 16:9 video (for Slack).

  scripts/build-week.py 2 8                  # days 02-08 -> out/stories/week/days-02-08.mp4 (+ a still)
  scripts/build-week.py 2 8 --stagger 0.5    # each story starts half a second after the one before

Reads the finished story videos in out/stories/instagram/ (story-day-NN-*.mp4; Day 01 is
story-3-day-01-*.mp4), scales each to a phone-shaped tile with the story's own rounded
corners and a hairline edge, and lays them in one row under a small header. Every story
starts on the same frame, so the build-ins and drifts line up and the system shows. With
--stagger, each phone waits dark for its turn, so the build-ins ripple left to right; the
video runs long enough for the last one to finish, and the early ones hold their last frame.
"""
import subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("bs", ROOT / "scripts" / "build-story.py")
bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)

W, H = 2560, 1440                       # 16:9, sharp enough to read the stories' type
SW, SH = 1080, 1920                     # a story
FPS, SECS = 30, 20
MARGIN, GAP = 96, 28
RULE = (42, 42, 44)                     # the hairline round each phone


def story_file(day):
    src = ROOT / "out" / "stories" / "instagram"
    hits = sorted(src.glob(f"story-day-{day:02d}-*.mp4")) or sorted(src.glob(f"story-3-day-{day:02d}-*.mp4"))
    if not hits:
        raise SystemExit(f"no story video for day {day:02d}")
    return hits[0]


def main():
    a, b = (int(x) for x in sys.argv[1:3])
    stagger = float(sys.argv[sys.argv.index("--stagger") + 1]) if "--stagger" in sys.argv else 0.0
    days = list(range(a, b + 1))
    n = len(days)
    tw = (W - 2 * MARGIN - (n - 1) * GAP) // n
    th = round(tw * SH / SW)
    tw -= tw % 2; th -= th % 2
    label_h = 44
    header_h = 190
    top = header_h + (H - header_h - th - label_h) // 2
    x0 = (W - (n * tw + (n - 1) * GAP)) // 2
    xs = [x0 + i * (tw + GAP) for i in range(n)]

    # The still parts: header, footer, day labels, hairlines.
    base = Image.new("RGB", (W, H), bs.BG)
    d = ImageDraw.Draw(base)
    m = bs.mono(26)
    bs.tracked(d, (MARGIN, MARGIN), f"INSTAGRAM STORIES / DAYS {a:02d}–{b:02d} OF 40", m, bs.ACCENT, .08)
    d.text((MARGIN - 4, MARGIN + 36), "40 albums, 40 days", font=bs.display(84), fill=bs.LIGHT)
    url = "DREWROPER.COM/40"
    bs.tracked(d, (W - MARGIN - bs.tracked_w(url, m, .08), MARGIN), url, m, bs.MUTED, .08)
    r = round(tw * 44 / SW) + 6                                  # the phone's corner
    for i, day in enumerate(days):
        lab = f"DAY {day:02d}"
        bs.tracked(d, (xs[i] + (tw - bs.tracked_w(lab, m, .08)) / 2, top + th + 16), lab, m, bs.MUTED, .08)
        d.rounded_rectangle((xs[i] - 1, top - 1, xs[i] + tw, top + th), r + 1, outline=RULE, width=1)
    frame0 = np.asarray(base).copy()
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw - 1, th - 1), r, fill=255)
    mk = (np.asarray(mask, dtype=np.float32) / 255)[..., None]

    ff = bs.ffmpeg_bin()
    readers = [subprocess.Popen([ff, "-loglevel", "error", "-i", str(story_file(day)),
                                 "-vf", f"scale={tw}:{th}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                stdout=subprocess.PIPE) for day in days]
    out = ROOT / "out" / "stories" / "week" / (f"days-{a:02d}-{b:02d}" + ("-staggered" if stagger else "") + ".mp4")
    delay = round(stagger * FPS)                                  # frames between one phone and the next
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-",
                            "-vf", "scale=out_color_matrix=bt709:out_range=tv,setsar=1",
                            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "18",
                            "-preset", "slow", "-tune", "animation",
                            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                            "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    bg = frame0[top:top + th].astype(np.float32)
    held = [None] * n                                             # each phone's latest frame
    last = None
    for f in range(FPS * SECS + delay * (n - 1)):
        frame = frame0.copy()
        for i, rd in enumerate(readers):
            if f < i * delay:
                continue                                          # not its turn yet: an empty, dark phone
            buf = rd.stdout.read(tw * th * 3)
            if len(buf) == tw * th * 3:
                tile = np.frombuffer(buf, np.uint8).reshape(th, tw, 3).astype(np.float32)
                held[i] = (tile * mk + bg[:, xs[i]:xs[i] + tw] * (1 - mk)).astype(np.uint8)
            if held[i] is not None:                               # finished: hold the last frame
                frame[top:top + th, xs[i]:xs[i] + tw] = held[i]
        enc.stdin.write(frame.tobytes()); last = frame
    enc.stdin.close(); enc.wait()
    for rd in readers: rd.wait()
    Image.fromarray(last).save(out.with_suffix(".png"))      # the held last frame, as a still
    print(out); print(out.with_suffix(".png"))


if __name__ == "__main__":
    main()
