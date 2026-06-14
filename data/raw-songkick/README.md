# Songkick raw pages

Drop saved gigography HTML pages from
`https://www.songkick.com/users/drewroper/gigography` (and the
paginated `?page=2..5` variants) here as `page-1.html` … `page-5.html`.

The next time the **Life log refresh** GitHub Action runs (hourly, or
manually from the Actions tab), the parser in
`scripts/fetch-life-log.py` will walk this directory, extract each
attended event, and merge it into `data/life-log.json`.

## Workflow

1. Open the gigography in your browser, logged in (or not — it's
   public).
2. Save the page source (`Cmd+S` → "Web Page, Source") or copy
   `View Source` into a new file via the GitHub web UI.
3. Commit as `data/raw-songkick/page-1.html` (etc.).
4. Wait for the next Action run, or manually trigger it.

The Action uses the GitHub runner's IP, which Songkick blocks
outright — that's why this is a local-export pipeline rather than
an HTTP scraper. Once an event is captured in `life-log.json`, the
HTML file can be deleted or kept for future re-parsing.
