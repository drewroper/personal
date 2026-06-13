#!/usr/bin/env python3
"""
Fetch life-log entries for drewroper.com — Letterboxd diary + Discogs
collection. Run by the .github/workflows/life-log.yml cron.

Merges into data/life-log.json, de-duped by source-specific id, sorted
newest-first. Letterboxd RSS is a rolling window (last ~50), so its
entries are merged into history. Discogs returns the full collection
paginated, so it gets a full refresh whenever its fetch succeeds.

Stdlib only — no pip install at runtime.
"""

import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "data" / "life-log.json"

LB_USER = "drewroper"
DC_USER = "drewroper"

UA = "drewroper-life-log/1.0 (+https://drewroper.com)"


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


# ----- Letterboxd ---------------------------------------------------

LB_NS = "{https://letterboxd.com}"


def rating_stars(value):
    """0.5–5.0 numeric → ★ glyph string, or None."""
    if value is None:
        return None
    full = int(value)
    half = (value - full) >= 0.5
    return "★" * full + ("½" if half else "") or None


def fetch_letterboxd():
    raw = fetch_bytes(f"https://letterboxd.com/{LB_USER}/rss/")
    root = ET.fromstring(raw)
    out = []
    for item in root.iter("item"):
        guid  = (item.findtext("guid")          or "").strip()
        date  = (item.findtext(LB_NS + "watchedDate") or "").strip()
        title = (item.findtext(LB_NS + "filmTitle")   or "").strip()
        year  = (item.findtext(LB_NS + "filmYear")    or "").strip()
        rewatch = (item.findtext(LB_NS + "rewatch") or "").strip() == "Yes"
        url   = (item.findtext("link") or "").strip()
        try:
            rating = float(item.findtext(LB_NS + "memberRating") or "")
        except ValueError:
            rating = None
        if not (guid and title and date):
            continue
        out.append({
            "source":  "letterboxd",
            "id":      guid,
            "date":    date,                 # YYYY-MM-DD
            "title":   title,
            "year":    year,
            "rating":  rating_stars(rating),
            "rewatch": rewatch,
            "url":     url,
        })
    return out


# ----- Discogs ------------------------------------------------------

def fetch_discogs():
    out = []
    url = (f"https://api.discogs.com/users/{DC_USER}/collection/folders/0/releases"
           f"?per_page=100&sort=added&sort_order=desc")
    while url:
        data = json.loads(fetch_bytes(url))
        for rel in data.get("releases", []):
            bi      = rel.get("basic_information", {}) or {}
            artists = bi.get("artists") or []
            artist  = " & ".join(a.get("name", "") for a in artists) or "Various"
            # Strip Discogs' "(2)" disambiguation suffix.
            artist  = re.sub(r"\s*\(\d+\)\s*$", "", artist)
            iid = rel.get("instance_id") or rel.get("id")
            date_added = (rel.get("date_added") or "")[:10]
            if not (iid and bi.get("title") and date_added):
                continue
            out.append({
                "source":  "discogs",
                "id":      f"discogs-{iid}",
                "date":    date_added,
                "title":   bi.get("title", ""),
                "artist":  artist,
                "year":    str(bi.get("year") or ""),
                "url":     f"https://www.discogs.com/release/{rel.get('id', '')}",
            })
        url = (data.get("pagination", {}).get("urls", {}) or {}).get("next")
        time.sleep(1)   # under 60 req/min unauthenticated cap
    return out


# ----- main ---------------------------------------------------------

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(OUT.read_text())
        if not isinstance(existing, list):
            existing = []
    except (FileNotFoundError, json.JSONDecodeError):
        existing = []

    by_id = {e.get("id"): e for e in existing if e.get("id")}

    # Letterboxd — merge into history (RSS is a rolling window).
    try:
        for e in fetch_letterboxd():
            by_id[e["id"]] = e
    except Exception as ex:
        print(f"WARN: Letterboxd fetch failed: {ex}", file=sys.stderr)

    # Discogs — full refresh (collection is paginated + complete).
    try:
        fresh = fetch_discogs()
        by_id = {k: v for k, v in by_id.items() if not k.startswith("discogs-")}
        for e in fresh:
            by_id[e["id"]] = e
    except Exception as ex:
        print(f"WARN: Discogs fetch failed: {ex}", file=sys.stderr)

    entries = list(by_id.values())
    entries.sort(key=lambda e: (e.get("date") or "", e.get("id") or ""), reverse=True)

    OUT.write_text(json.dumps(entries, separators=(",", ":")) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
