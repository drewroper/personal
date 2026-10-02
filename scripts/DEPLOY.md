# Deploying drewroper.com

The site is GitHub Pages, built from `claude/landing-page-redesign-5EUNV`. A push usually starts
"pages build and deployment" within seconds and the site updates in about a minute
(`data/albums.json` is cached for 10 minutes).

Check it landed: `curl -sI "https://drewroper.com/data/albums.json?x=$RANDOM" | grep -i last-modified`.
Check a day went live (`"live": true` on its record):
`curl -s "https://drewroper.com/data/albums.json?x=$RANDOM" | python3 -c "import json,sys; print(sum(1 for a in json.load(sys.stdin)['albums'] if a.get('live')))"`.

Pages sometimes skips the build for a git push (seen Oct 2, 2026: every git push from the Claude Code
session that afternoon, no GitHub incident). A commit made through the GitHub API (the contents
endpoint, or the web editor) starts a build when a push didn't. Re-saving the source branch under
Settings → Pages also forces one.
