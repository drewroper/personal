# Deploying drewroper.com

The site is GitHub Pages, published by the **Deploy site** workflow (`.github/workflows/pages.yml`)
from `claude/landing-page-redesign-5EUNV`. Settings → Pages → Source is "GitHub Actions".

- Every push to that branch deploys. The site updates about a minute after the run starts.
- life-log and changelog commit with GITHUB_TOKEN, which can't start a push-triggered run, so
  each dispatches Deploy site itself after it pushes.
- A push that doesn't start a run: start one by hand (Actions → Deploy site → Run workflow, or
  the API's workflow dispatch). No commit needed.

Why a workflow: Pages' own "deploy from a branch" build stopped picking up git pushes made from
Claude Code sessions on Oct 2, 2026 (GitHub logged the pushes; Pages never built them).

Check it landed: `curl -sI "https://drewroper.com/data/albums.json?x=$RANDOM" | grep -i last-modified`.
Check a day went live (`"live": true` on its record):
`curl -s "https://drewroper.com/data/albums.json?x=$RANDOM" | python3 -c "import json,sys; print(sum(1 for a in json.load(sys.stdin)['albums'] if a.get('live')))"`.

Everything is cached for 10 minutes (max-age=600). A photo replaced under the same name
(`assets/40/photos/…`) can take that long to show for anyone who already opened it. Sleeves don't
have this problem; `worn_v` busts their cache.
