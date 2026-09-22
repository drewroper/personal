#!/usr/bin/env python3
"""Find back-cover art for each album via MusicBrainz + Cover Art Archive.

For every album in data/albums.json (or the file given as argv[1]) that has
no `art_back`, search MusicBrainz for the release group, walk its official
releases (US first), and take the squarest image typed "Back" from the
Cover Art Archive. Saved to assets/40/<slug>-back.jpg, kept at its real aspect ratio (jewel-case
spines trimmed) at up to 1200px, and recorded as `art_back` on the album.

Usage: scripts/fetch-backs.py [data/albums.json] [--force] [--only slug,slug]
"""
import io, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UA = 'drewroper-40/1.0 (drewroper@gmail.com)'
args = [a for a in sys.argv[1:] if not a.startswith('--')]
DATA = ROOT / (args[0] if args else 'data/albums.json')
FORCE = '--force' in sys.argv
ONLY = None
for a in sys.argv[1:]:
    if a.startswith('--only='): ONLY = set(a[7:].split(','))

def get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(2 + i); continue
        except Exception:
            time.sleep(1 + i)
    return None

def mb(path, **q):
    q['fmt'] = 'json'
    time.sleep(1.1)  # MusicBrainz: 1 req/s
    raw = get('https://musicbrainz.org/ws/2/' + path + '?' + urllib.parse.urlencode(q))
    return json.loads(raw) if raw else None

def caa(rid):
    raw = get(f'https://coverartarchive.org/release/{rid}')
    return json.loads(raw)['images'] if raw else []

def norm(s): return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

def find_group(a):
    titles = [a['title']]
    bare = re.sub(r'\s*[\(\[].*?[\)\]]', '', a['title']).strip()
    if bare and bare != a['title']: titles.append(bare)
    for t in titles:
        g = _find_group(a['artist'], t)
        if g: return g
    return None

def _find_group(artist, title):
    q = f'artist:"{artist}" AND releasegroup:"{title}"'
    res = mb('release-group/', query=q, limit=10) or {}
    want = norm(title)
    best = None
    for g in res.get('release-groups', []):
        if g.get('primary-type') not in (None, 'Album', 'EP'): continue
        if any(t in ('Compilation', 'Remix') for t in g.get('secondary-types', [])): continue
        t = norm(g['title'])
        score = (t == want, t.startswith(want) or want.startswith(t), g.get('score', 0))
        if best is None or score > best[0]: best = (score, g)
    return best[1] if best else None

def release_order(r):
    c = r.get('country') or ''
    return (r.get('status') != 'Official', c not in ('US', 'XW'), c not in ('GB', 'XE', 'CA'), r.get('date') or '9999')

def pick_back(images):
    backs = [i for i in images if 'Back' in i.get('types', []) and i.get('approved', True)]
    if not backs: return None
    # Prefer a plain back over back+spine+tray, then earlier uploads.
    backs.sort(key=lambda i: (len(i['types']), i.get('id', 0)))
    return backs[0]

def tidy(img):
    """Keep the real aspect ratio; only trim the two spines off a jewel-case back inlay (151x118mm, 6.5mm spines)."""
    w, h = img.size
    r = w / h
    if 1.22 <= r <= 1.34:
        sp = int(w * 6.5 / 151)
        img = img.crop((sp, 0, w - sp, h))
    return inset(img)

def inset(img, frac=0.015):
    """Trim the sliver of scanner bed / sleeve edge that rings most scans."""
    w, h = img.size
    dx, dy = int(w * frac), int(h * frac)
    return img.crop((dx, dy, w - dx, h - dy))

def fetch_image(i):
    url = (i.get('thumbnails') or {}).get('1200') or i['image']
    raw = get(url.replace('http://', 'https://'))
    if not raw: raw = get(i['image'].replace('http://', 'https://'))
    return Image.open(io.BytesIO(raw)).convert('RGB') if raw else None

doc = json.loads(DATA.read_text())
changed = False
for a in doc['albums']:
    if ONLY and a['slug'] not in ONLY: continue
    if a.get('art_back') and not FORCE: continue
    print(f'· {a["artist"]} — {a["title"]}', flush=True)
    g = find_group(a)
    if not g: print('   no release group'); continue
    rel = mb(f'release-group/{g["id"]}', inc='releases') or {}
    releases = sorted(rel.get('releases', []), key=release_order)
    hit = None
    for r in releases[:16]:
        imgs = caa(r['id'])
        b = pick_back(imgs)
        if b:
            im = fetch_image(b)
            if im is None: continue
            w, h = im.size
            ratio = max(w, h) / min(w, h)
            print(f'   {r.get("country")} {r.get("date")} back {w}x{h} {b["types"]}')
            # Score: square-ish beats wide, then plain "Back" beats back+spine, then bigger.
            score = (ratio < 1.12, ratio < 1.4, len(b['types']) == 1, min(w, h))
            if hit is None or score > hit[0]: hit = (score, im, r, b)
            if score[0] and score[2] and min(w, h) >= 1000: break
    if not hit: print('   no back cover found'); continue
    score, im, r, b = hit
    im = tidy(im)
    if max(im.size) > 1200:
        f = 1200 / max(im.size); im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    out = ROOT / 'assets/40' / f'{a["slug"]}-back.jpg'
    im.save(out, quality=88, optimize=True)
    a['art_back'] = f'assets/40/{a["slug"]}-back.jpg'
    a['art_back_src'] = b['image']
    changed = True
    print(f'   ✓ {out.name} ({im.width}x{im.height}, from {r.get("country")} {r.get("date")})')
    DATA.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
if not changed: print('nothing new')
