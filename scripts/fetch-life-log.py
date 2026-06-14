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
import os
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
GH_USER = "drewroper"

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


# ----- GitHub -------------------------------------------------------
#
# Public REST API, unauthenticated. Lists Drew's own (non-fork) public
# repos and records each repo's creation date as a "started building"
# entry. Unauth quota is 60 req/hr per IP — well above what one page
# of repos costs.

def fetch_github():
    out = []
    page = 1
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    while True:
        url = (f"https://api.github.com/users/{GH_USER}/repos"
               f"?per_page=100&type=owner&sort=created&direction=desc&page={page}")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
        if not batch:
            break
        for repo in batch:
            if repo.get("fork") or repo.get("private"):
                continue
            rid     = repo.get("id")
            name    = repo.get("name") or ""
            created = (repo.get("created_at") or "")[:10]
            html    = repo.get("html_url") or ""
            desc    = (repo.get("description") or "").strip()
            if not (rid and name and created):
                continue
            out.append({
                "source": "github",
                "id":     f"github-{rid}",
                "date":   created,
                "title":  name,
                "description": desc,
                "url":    html,
            })
        if len(batch) < 100:
            break
        page += 1
        time.sleep(1)
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
    # right before punctuation in the source HTML, and decode entities
    # like &#39; → '.
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s+([,.;:])', r'\1', s)
    return s


# Trailing-parenthetical disambiguators on artist names that Songkick
# inherits from MusicBrainz (e.g. "Automatic (band)", "Speed (AUS)",
# "The Smile (UK)"). Stripped entirely — they're never part of the
# brand a real fan would recognise.
DISAMBIG_RE = re.compile(
    r'\s*\(('
    r'band|group|the band|duo|trio|quartet|quintet|sextet|septet|'
    r'rapper|singer|producer|DJ|musician|artist|composer|orchestra|'
    r'[A-Z]{2,4}|'   # country codes — UK, US, USA, AUS, NZ, …
    r'\d+'           # numeric disambiguators — (2), (3), …
    r')\)\s*$',
    re.I,
)

def _strip_disambig(name):
    prev = None
    while name != prev:
        prev = name
        name = DISAMBIG_RE.sub('', name).strip()
    return name


# Anything matching this in the headliner string is treated as a
# festival — we surface only the festival name and skip listing every
# band on the bill. Drew's examples: Revolution Oktoberfest 2017,
# 312 Block Party 2017, Riot Fest Chicago 2016, Telluride Bluegrass
# Festival 2016.
FESTIVAL_RE = re.compile(
    r'\b('
    # Generic words found in festival names.
    r'festival|fest|oktoberfest|block\s*party|bluegrass|jamboree|carnival|rendezvous|'
    # Big-name festivals that don't carry "festival" in the brand.
    r'lollapalooza|coachella|bonnaroo|sxsw|south\s+by\s+southwest|'
    r'austin\s+city\s+limits|outside\s+lands|stagecoach|firefly|glastonbury|hangout|'
    r'governors\s+ball|warped\s+tour|wakarusa|electric\s+forest'
    r')\b',
    re.I,
)

def _looks_like_festival(s):
    """True if the headliner string reads like a festival name. We
    require an actual festival keyword — a trailing 4-digit year alone
    isn't enough (it false-positives on band names like Death from
    Above 1979)."""
    return bool(s and FESTIVAL_RE.search(s))


def _join_acts_oxford(parts):
    """Render a list of bands with proper Oxford-comma punctuation.
    De-duplicates (case-insensitive) while preserving first-seen order
    — Songkick sometimes lists the same support twice."""
    parts = [p for p in (p.strip() for p in parts) if p]
    seen, deduped = set(), []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(p)
    parts = deduped
    if not parts: return ''
    if len(parts) == 1: return parts[0]
    if len(parts) == 2: return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _normalize_lineup(artists_text):
    """Take a flat string of acts (potentially mixing commas and 'and')
    and re-emit it with disambiguators stripped + Oxford commas.

    Splits on the longest separator first ("X, and Y" is ONE split
    point, not two) to avoid the empty-band-named-"and" trap. """
    parts = re.split(r'\s*,\s*and\s+|\s*,\s*|\s+and\s+', artists_text)
    parts = [_strip_disambig(p) for p in parts if p and p.strip()]
    return _join_acts_oxford(parts)


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
    # as plain trailing text. We branch:
    #   - If the headliner looks festival-y, surface ONLY the festival
    #     name (skip listing every band on the bill).
    #   - Otherwise merge headliner + supports, strip disambiguators,
    #     and rejoin with Oxford-comma punctuation.
    m = re.search(r'<p[^>]*class="artists\s+summary"[^>]*>(.*?)</p>', chunk, re.S)
    artists_html = m.group(1) if m else ''
    m_strong = re.search(r'<strong[^>]*>(.*?)</strong>', artists_html, re.S)
    headliner = _strip_tags(m_strong.group(1)) if m_strong else ''

    if _looks_like_festival(headliner):
        artist = _strip_disambig(headliner)
    else:
        # Insert ", " at the </strong> boundary so headliner + supports
        # become one comma-separated list, then normalise to Oxford.
        merged_html = re.sub(r'</strong>(\s*)(?=\S)', r'</strong>, ', artists_html)
        merged = _strip_tags(merged_html)
        merged = re.sub(r'\s*,\s*$', '', merged)
        artist = _normalize_lineup(merged)

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

    # GitHub — full refresh of public, non-fork repos.
    try:
        fresh = fetch_github()
        if fresh:
            by_id = {k: v for k, v in by_id.items() if not k.startswith("github-")}
            for e in fresh:
                by_id[e["id"]] = e
    except Exception as ex:
        print(f"WARN: GitHub fetch failed: {ex}", file=sys.stderr)

    entries = list(by_id.values())
    entries.sort(key=lambda e: (e.get("date") or "", e.get("id") or ""), reverse=True)

    OUT.write_text(json.dumps(entries, separators=(",", ":")) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
