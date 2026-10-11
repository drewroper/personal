#!/usr/bin/env python3
"""Attach Apple's 30-second preview URL to every track in data/albums.json (and the test data).

Looks each album up on the iTunes lookup API by apple_id, orders its songs by disc and track,
and matches them to our tracklist by position, falling back to title when the counts differ.

A record Apple doesn't carry (no apple_id, e.g. Girl Talk's Feed the Animals) takes Spotify's
30-second clips instead, read from its album embed page (no key needed). Same matching rules;
a track Spotify has no clip for stays unplayable.

  scripts/fetch-previews.py
"""
import json, re, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
norm = lambda s: re.sub(r'[^a-z0-9]', '', re.sub(r'\(.*?\)|\[.*?\]', '', s.lower()))


def lookup(apple_id):
    url = f'https://itunes.apple.com/lookup?id={apple_id}&entity=song&limit=200'
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                res = json.load(r)['results']
            songs = [x for x in res if x.get('wrapperType') == 'track' and x.get('kind') == 'song']
            return sorted(songs, key=lambda x: (x.get('discNumber', 1), x.get('trackNumber', 0)))
        except Exception:
            time.sleep(2 ** i)
    return []


def spotify_songs(url):
    """The album's tracks from Spotify's embed page, shaped like iTunes results for attach()."""
    m = re.search(r'album/([A-Za-z0-9]+)', url or '')
    if not m:
        return []
    req = urllib.request.Request(f'https://open.spotify.com/embed/album/{m.group(1)}', headers={'User-Agent': 'Mozilla/5.0'})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                page = r.read().decode()
            data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S).group(1))
            tracks = data['props']['pageProps']['state']['data']['entity']['trackList']
            return [{'trackName': t['title'], 'previewUrl': (t.get('audioPreview') or {}).get('url')} for t in tracks]
        except Exception:
            time.sleep(2 ** i)
    return []


def attach(album, songs):
    tracks = album.get('tracks') or []
    if not tracks or not songs:
        return 0
    by_title = {norm(s['trackName']): s for s in songs}
    n = 0
    for i, t in enumerate(tracks):
        s = songs[i] if len(songs) == len(tracks) else by_title.get(norm(t['title']))
        if s and s.get('previewUrl'):
            t['preview'] = s['previewUrl']; n += 1
        else:
            t.pop('preview', None)
    return n


if __name__ == '__main__':
    main_path = ROOT / 'data/albums.json'
    doc = json.loads(main_path.read_text())
    got = {}
    for a in doc['albums']:
        if a.get('apple_id'):
            songs = lookup(a['apple_id'])
        elif (a.get('links') or {}).get('spotify'):
            songs = spotify_songs(a['links']['spotify'])
        else:
            continue
        n = attach(a, songs)
        got[a['slug']] = [t.get('preview') for t in a.get('tracks') or []]
        print(f"{a['slug']:52} {n}/{len(a.get('tracks') or [])}")
        time.sleep(.3)
    main_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    test_path = ROOT / 'data/albums.test.json'
    test = json.loads(test_path.read_text())
    for a in test['albums']:
        urls = got.get(re.sub(r'-40$', '', a['slug']))
        if urls and len(urls) == len(a.get('tracks') or []):
            for t, u in zip(a['tracks'], urls):
                if u: t['preview'] = u
                else: t.pop('preview', None)
    test_path.write_text(json.dumps(test, indent=2, ensure_ascii=False) + '\n')
