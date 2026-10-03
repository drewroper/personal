# Deploying drewroper.com

The site is GitHub Pages, built from `claude/landing-page-redesign-5EUNV`. A push usually starts
"pages build and deployment" within seconds and the site updates in about a minute
(`data/albums.json` is cached for 10 minutes).

Check it landed: `curl -sI "https://drewroper.com/data/albums.json?x=$RANDOM" | grep -i last-modified`.
Check a day went live (`"live": true` on its record):
`curl -s "https://drewroper.com/data/albums.json?x=$RANDOM" | python3 -c "import json,sys; print(sum(1 for a in json.load(sys.stdin)['albums'] if a.get('live')))"`.

A photo replaced under the same name (`assets/40/photos/…`) can take up to 10 minutes to show for
anyone who already opened it: Pages caches everything for 600 seconds. Sleeves don't have this
problem; `worn_v` busts their cache.

Pages sometimes skips the build for a git push (seen Oct 2, 2026: every git push from the Claude Code
session that afternoon, no GitHub incident). A commit made through the GitHub API (the contents
endpoint, or the web editor) starts a build when a push didn't. Re-saving the source branch under
Settings → Pages also forces one.

## Kick log

Builds started with an API commit to this file, after a git push didn't deploy:

- 2026-10-02 19:31 UTC: Day 10 swap, RTJ2 blurb and chart
- 2026-10-02 23:00 UTC: Day 10, "[timing TBD]" removed
- 2026-10-02 23:03 UTC: Day 10, "ridiculous" to "wild"
- 2026-10-02 23:05 UTC: Day 10 live
- 2026-10-03 00:10 UTC: Last.fm chart title
- 2026-10-03 00:14 UTC: Day 10, Killer Mike and the features merged into one paragraph
