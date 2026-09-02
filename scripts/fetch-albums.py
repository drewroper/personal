"""
Fill in album metadata for the /40 countdown.

Reads data/albums.json, and for every album with an `apple_id` pulls the
record from Apple's public lookup API (no key needed): release date, label,
tracklist + runtimes, genre, and the 1800px cover, which is saved to
assets/40/<slug>.jpg.

Albums without an `apple_id` are searched by artist + title. An exact
(case-insensitive) match is taken automatically; anything fuzzier is
printed as candidates and left alone, because the first search hit is
often wrong (a live album, a deluxe reissue, a different band).

Hand-written fields are never touched: no, slug, artist, title, blurb,
discovered, any `label` you set yourself, and `links` — an optional
{spotify, youtubeMusic, tidal, bandcamp} of direct album URLs. Without
them the page falls back to per-service search links, and album.link
resolves the record across every service from the Apple ID alone. Post dates are derived from
`no` and meta.start so nothing has to be typed twice.

Run: python3 scripts/fetch-albums.py                        # fill missing fields
     python3 scripts/fetch-albums.py --refresh               # re-pull everything
     python3 scripts/fetch-albums.py data/albums.test.json   # another file
"""

import difflib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
DATA = Path(ARGS[0]).resolve() if ARGS else ROOT / "data" / "albums.json"
ART  = ROOT / "assets" / "40"

LOOKUP = "https://itunes.apple.com/lookup?id={id}&entity=song&country=us"
SEARCH = "https://itunes.apple.com/search?term={q}&entity=album&country=us&limit=25"

# Fields the fetcher owns. Everything else in an entry is yours.
FETCHED = ("apple_url", "released", "year", "copyright", "genre",
           "track_count", "runtime_ms", "tracks", "art_remote", "art")

REFRESH = "--refresh" in sys.argv


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "drewroper.com/40"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def label_from_copyright(text):
    """'℗ 2016 Geffen Records' -> 'Geffen Records'. Best effort; override
    with a hand-set `label` when Apple's string is junk."""
    if not text:
        return ""
    s = re.sub(r"^(this compilation\s*)?[℗©]\s*(\d{4})?\s*", "", text, flags=re.I)
    s = re.split(r",? (under exclusive licen[cs]e|distributed by|marketed by)", s, flags=re.I)[0]
    return s.strip(" .,")


def hi_res(url):
    return re.sub(r"/\d+x\d+bb\.(jpg|png)$", "/1800x1800bb.jpg", url)


def find_album(album):
    """Search by artist + title; only trust an exact name match."""
    q = urllib.parse.quote(f'{album["artist"]} {album["title"]}')
    hits = [h for h in get_json(SEARCH.format(q=q))["results"]
            if h.get("collectionType") == "Album"]
    want_artist = album["artist"].strip().lower()
    want_title  = album["title"].strip().lower()
    exact = [h for h in hits
             if h["artistName"].strip().lower() == want_artist
             and h["collectionName"].strip().lower() == want_title]
    if len(exact) == 1:
        return exact[0]["collectionId"]
    print(f'  ? no exact match for {album["artist"]} — {album["title"]}. Candidates:')
    for h in hits[:8]:
        print(f'      {h["collectionId"]}  {h["artistName"]} — {h["collectionName"]} '
              f'({h.get("releaseDate", "")[:4]}, {h.get("trackCount")} tracks)')
    print("    set apple_id by hand, or apple_id: 0 if it isn't on Apple Music.")
    return None


def fetch(album):
    res = get_json(LOOKUP.format(id=album["apple_id"]))["results"]
    coll = next((r for r in res if r.get("wrapperType") == "collection"), None)
    if not coll:
        print(f'  ! apple_id {album["apple_id"]} returned nothing')
        return
    tracks = sorted((r for r in res if r.get("wrapperType") == "track"),
                    key=lambda r: (r.get("discNumber", 1), r.get("trackNumber", 0)))

    album["apple_url"]   = coll["collectionViewUrl"].split("?")[0]
    album["released"]    = coll.get("releaseDate", "")[:10]
    album["year"]        = album["released"][:4]
    album["copyright"]   = coll.get("copyright", "")
    album["genre"]       = coll.get("primaryGenreName", "")
    album["track_count"] = coll.get("trackCount", len(tracks))
    album["runtime_ms"]  = sum(t.get("trackTimeMillis", 0) for t in tracks)
    album["tracks"]      = [{"n": i + 1, "title": t["trackName"],
                             "ms": t.get("trackTimeMillis", 0)} for i, t in enumerate(tracks)]
    album["art_remote"]  = hi_res(coll["artworkUrl100"])
    if not album.get("label"):
        album["label"] = label_from_copyright(album["copyright"])

    ART.mkdir(parents=True, exist_ok=True)
    out = ART / f'{album["slug"]}.jpg'
    if REFRESH or not out.exists():
        urllib.request.urlretrieve(album["art_remote"], out)
    album["art"] = f'assets/40/{album["slug"]}.jpg'


def check_spotify(album):
    """Spotify's oEmbed needs no key and returns the linked album's title —
    enough to catch a pasted link that points at the wrong record."""
    url = (album.get("links") or {}).get("spotify")
    if not url:
        return
    try:
        title = get_json("https://open.spotify.com/oembed?url=" + urllib.parse.quote(url, safe=""))["title"]
    except Exception as e:  # noqa: BLE001
        print(f"  ! spotify link unreachable: {e}")
        return
    norm = lambda t: re.sub(r"\b(the|a|an|album|deluxe|edition|remaster(ed)?)\b|[^a-z0-9 ]", "", t.lower()).split()
    want, got = norm(album["title"]), norm(title)
    ratio = difflib.SequenceMatcher(None, " ".join(want), " ".join(got)).ratio()
    if ratio < 0.6:
        print(f'  ! spotify link says "{title}", album is "{album["title"]}" — check it')
    else:
        print(f"  spotify ✓ {title}")


def main():
    data  = json.loads(DATA.read_text())
    start = date.fromisoformat(data["meta"]["start"])

    for album in data["albums"]:
        tag = f'{album["artist"]} — {album["title"]}'

        # Post date follows the slot number; unslotted albums have none.
        if album.get("no"):
            album["date"] = (start + timedelta(days=album["no"] - 1)).isoformat()
        else:
            album.pop("date", None)

        if album.get("apple_id") is None:
            print(f"· {tag}: searching")
            album["apple_id"] = find_album(album)
            if album["apple_id"] is None:
                continue

        if album["apple_id"] == 0:
            print(f"· {tag}: not on Apple Music, skipping fetch")
            continue

        if REFRESH or not all(album.get(k) for k in FETCHED):
            print(f'· {tag}: fetching {album["apple_id"]}')
            fetch(album)
        else:
            print(f"· {tag}: ok")
        check_spotify(album)

    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
