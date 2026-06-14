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


class SongkickListingParser(HTMLParser):
    """Walks a Songkick gigography page and pulls out every event
    listing element. Songkick's gigography uses <li class="event-listings-element">
    blocks (or .event-listings li with various inner shapes); we
    collect each one as a chunk of inner HTML for downstream regex
    extraction so we're tolerant of small markup drift."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # >0 while inside a listing element
        self.depth_at_start = 0
        self.buf = []
        self.items = []

    def _is_listing(self, attrs):
        cls = dict(attrs).get('class', '') or ''
        return 'event-listings-element' in cls or 'event-listing' in cls.split()

    def handle_starttag(self, tag, attrs):
        if self.depth == 0 and tag == 'li' and self._is_listing(attrs):
            self.depth = 1
            self.depth_at_start = 1
            self.buf = []
            return
        if self.depth:
            if tag == 'li':
                self.depth += 1
            attr_str = ''.join(f' {k}="{(v or "")}"' for k, v in attrs)
            self.buf.append(f'<{tag}{attr_str}>')

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == 'li':
            self.depth -= 1
            if self.depth == 0:
                self.items.append(''.join(self.buf))
                self.buf = []
                return
        self.buf.append(f'</{tag}>')

    def handle_data(self, data):
        if self.depth:
            self.buf.append(data)


def _first_match(pattern, html, flags=re.S | re.I):
    m = re.search(pattern, html, flags)
    return (m.group(1).strip() if m else None) if m else None


def _strip_tags(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


def parse_songkick_event(html):
    """Extract one event from a listing HTML chunk. Defensive — tries
    several known Songkick markup shapes."""
    # ISO date — usually inside <time datetime="2026-06-11"> or similar.
    date = _first_match(r'<time[^>]*datetime="([0-9]{4}-[0-9]{2}-[0-9]{2})', html)
    if not date:
        # Fallback: "Thursday, June 11, 2026" → ISO
        m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', html, re.I)
        if m:
            mo = MONTHS_FULL[m.group(1).lower()]
            date = f"{m.group(3)}-{mo:02d}-{int(m.group(2)):02d}"

    # Artist / headliner — Songkick's primary heading inside each listing.
    artist = (
        _first_match(r'<p[^>]*class="[^"]*artists[^"]*"[^>]*>(.*?)</p>', html) or
        _first_match(r'<strong[^>]*class="[^"]*primary-detail[^"]*"[^>]*>(.*?)</strong>', html) or
        _first_match(r'<a[^>]*class="[^"]*summary[^"]*"[^>]*>(.*?)</a>', html) or
        _first_match(r'<span[^>]*itemprop="name"[^>]*>(.*?)</span>', html)
    )
    artist = _strip_tags(artist or '')
    # Strip leading "with " on supporting acts, drop trailing "at <venue>".
    artist = re.sub(r'\s+at\s+.+$', '', artist).strip()

    # Venue + city.
    venue = _strip_tags(
        _first_match(r'<[^>]*class="[^"]*venue-name[^"]*"[^>]*>(.*?)</[^>]+>', html) or
        _first_match(r'<[^>]*itemprop="location"[^>]*>(.*?)</[^>]+>', html) or
        ''
    )
    city = _strip_tags(
        _first_match(r'<[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</[^>]+>', html) or
        _first_match(r'<[^>]*class="[^"]*city[^"]*"[^>]*>(.*?)</[^>]+>', html) or
        ''
    )

    # Event URL.
    href = _first_match(r'<a[^>]*class="[^"]*(?:summary|event-link)[^"]*"[^>]*href="([^"]+)"', html)
    if not href:
        href = _first_match(r'href="(/concerts/[^"]+)"', html)
    url = f"https://www.songkick.com{href}" if href and href.startswith('/') else href

    # ID — last numeric run in the URL is the Songkick event id.
    event_id = ''
    if href:
        m = re.search(r'/(\d+)-', href)
        event_id = m.group(1) if m else ''

    if not (artist and date):
        return None

    return {
        "source": "songkick",
        "id":     f"songkick-{event_id or href or artist + date}",
        "date":   date,
        "title":  artist,
        "venue":  venue,
        "city":   city,
        "url":    url or "",
    }


def parse_songkick_local():
    """Walk data/raw-songkick/*.html and return every parsed event."""
    out = []
    if not SK_DIR.is_dir():
        return out
    for path in sorted(SK_DIR.glob('*.html')):
        try:
            html = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        parser = SongkickListingParser()
        try:
            parser.feed(html)
        except Exception as ex:
            print(f"WARN: parsing {path.name}: {ex}", file=sys.stderr)
            continue
        for chunk in parser.items:
            ev = parse_songkick_event(chunk)
            if ev:
                out.append(ev)
        print(f"  songkick: {path.name} → {len(parser.items)} listings parsed", file=sys.stderr)
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
