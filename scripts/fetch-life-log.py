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
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "data" / "life-log.json"
SK_DIR = ROOT / "data" / "raw-songkick"

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


# ----- Songkick (parsed from locally-saved HTML) --------------------
#
# Songkick blocks data-center IPs (every GitHub runner) so we can't
# scrape from the Action. Workflow: Drew saves gigography pages into
# data/raw-songkick/*.html and commits them; this parser walks the
# directory and pulls events out.

MONTHS_FULL = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _strip_tags(s):
    # Tags → space (so adjacent words don't fuse), collapse whitespace,
    # then close up the " ," / " ." artifacts produced when a tag sat
    # right before punctuation in the source HTML.
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s+([,.;:])', r'\1', s)
    return s


def parse_songkick_event(chunk):
    """Extract one Songkick event from a <li title="..."> block.

    Real-world structure (from drewroper's gigography pages, June 2026):

        <li title="Thursday 11 June 2026">
          <time datetime="2026-06-11T17:30:00-0600"></time>
          <a href="/concerts/43023656-metric-at-fillmore-auditorium" class="thumb">…</a>
          <p class="artists summary">
            <a href="/concerts/…"><span><strong>Metric, Broken Social Scene, and Stars</strong></span></a>
          </p>
          <p class="location">
            <span class="venue-name"><a>Fillmore Auditorium</a></span>,
            <span>
              <span>Denver, CO, US </span>
              <span class="street-address">…</span>
            </span>
          </p>
          …
        </li>
    """
    # ISO date — first <time datetime="…"> attribute in the chunk.
    m = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', chunk)
    date = m.group(1) if m else None

    # Event URL + numeric id (the first /concerts/<id>-slug link).
    m = re.search(r'href="(/concerts/(\d+)-[^"]+)"', chunk)
    href, event_id = (m.group(1), m.group(2)) if m else ('', '')
    url = f"https://www.songkick.com{href}" if href else ''

    # Artists: contents of <p class="artists summary">.
    # Songkick wraps the HEADLINER in <strong> and dumps supporting acts
    # as plain trailing text — insert a comma at the </strong> boundary
    # so they read cleanly as a comma-separated bill.
    m = re.search(r'<p[^>]*class="artists\s+summary"[^>]*>(.*?)</p>', chunk, re.S)
    artists_html = m.group(1) if m else ''
    artists_html = re.sub(r'</strong>(\s*)(?=\S)', r'</strong>, ', artists_html)
    artist = _strip_tags(artists_html)
    artist = re.sub(r'\s*,\s*$', '', artist)

    # Venue.
    m = re.search(r'<span[^>]*class="venue-name"[^>]*>(.*?)</span>', chunk, re.S)
    venue = _strip_tags(m.group(1) if m else '')

    # City — the bare <span>City, ST, CC </span> inside .location,
    # explicitly NOT the street-address span. The .location block
    # contains: venue-name span, comma text, outer <span> wrapping a
    # city <span> followed by a street-address <span>. We grab the
    # first <span> child of that outer wrapper that doesn't carry
    # class="street-address".
    city = ''
    loc = re.search(r'<p[^>]*class="location"[^>]*>(.*?)</p>', chunk, re.S)
    if loc:
        # find spans without a class attribute (or with no street-address class)
        for m2 in re.finditer(r'<span(\s+[^>]*)?>(.*?)</span>', loc.group(1), re.S):
            attrs = m2.group(1) or ''
            if 'street-address' in attrs or 'venue-name' in attrs:
                continue
            text = _strip_tags(m2.group(2))
            # Heuristic: a city line looks like "City, ST, CC".
            if ',' in text and len(text) < 80 and 'venue' not in text.lower():
                city = text
                break

    if not (artist and date):
        return None

    return {
        "source": "songkick",
        "id":     f"songkick-{event_id or href or artist + date}",
        "date":   date,
        "title":  artist,
        "venue":  venue,
        "city":   city,
        "url":    url,
    }


def parse_songkick_local():
    """Walk data/raw-songkick/*.html and return every parsed event."""
    out = []
    if not SK_DIR.is_dir():
        return out
    # Each event is a <li title="…">…</li> inside <ul class="event-listings">.
    # The date headings inside the same <ul> use <li class="with-date">,
    # which we skip because they don't carry a title attribute.
    listing_block_re = re.compile(r'<ul\s+class="event-listings\s*">(.*?)</ul>', re.S)
    event_li_re      = re.compile(r'<li\s+title="[^"]+">.*?</li>\s*(?=<li|</ul)', re.S)

    for path in sorted(SK_DIR.glob('*.html')):
        try:
            html = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        n_block = n_event = 0
        for block in listing_block_re.findall(html):
            n_block += 1
            for chunk in event_li_re.findall(block):
                ev = parse_songkick_event(chunk)
                if ev:
                    out.append(ev)
                    n_event += 1
        print(f"  songkick: {path.name} → {n_event} events from {n_block} list block(s)", file=sys.stderr)
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

    # Songkick — full refresh from locally-committed HTML pages. If
    # no pages are present, leaves any existing Songkick entries
    # alone (so a missing data/raw-songkick/ never wipes history).
    try:
        fresh = parse_songkick_local()
        if fresh:
            by_id = {k: v for k, v in by_id.items() if not k.startswith("songkick-")}
            for e in fresh:
                by_id[e["id"]] = e
    except Exception as ex:
        print(f"WARN: Songkick parse failed: {ex}", file=sys.stderr)

    entries = list(by_id.values())
    entries.sort(key=lambda e: (e.get("date") or "", e.get("id") or ""), reverse=True)

    OUT.write_text(json.dumps(entries, separators=(",", ":")) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
