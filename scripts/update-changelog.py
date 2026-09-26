#!/usr/bin/env python3
"""
Write new changelog entries for the "Last touched" drawer in index.html.
Run by the .github/workflows/changelog.yml nightly cron.

Reads the newest <time> in the changelog, collects every commit since
then (skipping merges, bot refreshes and changelog commits), and asks
Claude to roll them up into a few entries in the drawer's voice. The
entries go in at the top of the list, newest first. Nothing new, no
change.

Needs ANTHROPIC_API_KEY. Without it the script says so and exits 0,
so the workflow stays green until the key is added.

  python scripts/update-changelog.py            # write index.html
  python scripts/update-changelog.py --dry-run  # print, don't write
"""

import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

MODEL = "claude-opus-5"

# Commits that never make the changelog: the hourly life-log bot, the
# changelog's own commits, and merges (their branches' commits count).
SKIP_SUBJECT = re.compile(r"^(life-log: refresh|changelog:)", re.I)
SKIP_AUTHOR = re.compile(r"\[bot\]$")

LIST_OPEN = re.compile(r'^(?P<indent>[ \t]*)<ol class="changelog__list">[ \t]*\n', re.M)
ENTRY = re.compile(
    r'<li><time>(?P<time>[^<]+)</time><span class="changelog__msg">(?P<msg>.*?)</span></li>'
)
TIME_FMT = "%Y-%m-%d %H:%MZ"

SYSTEM = """\
You keep the changelog for drewroper.com, the personal site of Drew Roper, a \
graphic designer in Denver. The changelog is an easter egg: a drawer under \
"Last touched" in the site's footer, read by curious visitors.

You'll get the entries already in the drawer (for voice) and the git commits \
made since the newest one. Roll the commits up into new entries.

What the site is:
- / is the homepage (portrait, headline, clients chyron, work grid, colophon).
- /log.html is a quiet life log (films, records, shows, beers, books, runs) \
that refreshes itself from Letterboxd, Discogs, Untappd, Strava and GitHub.
- /40 is "40 albums, 40 days", a daily countdown of records before Drew turns 40.
- "stories:" and "build-story" commits are an offline renderer for Instagram \
story videos, "docs:" are internal notes, "make-wear"/"fetch-*" are asset \
scripts. They aren't the site; mention them only when the result shows up on \
the site, or as a light aside.

How to write:
- Match the voice of the existing entries: plain, specific, a little dry. \
Sentences, not bullet fragments. No trailing period. Say what changed and, \
when it matters, why. Name fonts, sizes and colours precisely; this is a \
designer's site.
- One entry per meaningful chunk of work, usually one per working day. Fold \
fiddly iterations (tweak, revert, retune) into the result they led to. \
Skip days that only touched tooling or data chores. Usually 1-4 entries; \
zero is fine if nothing is worth a line.
- Keep each entry under about 60 words.
- Never spoil what the site keeps hidden. On /40, name a record only if a \
commit publishes it or marks it live; commits often name upcoming days, and \
those stay secret. Easter eggs (hidden records, secret albums, where the log \
lives) can be hinted at, never revealed.
- Plain text only, except _italics_ for record, book and film titles.

For each entry return "through": the short hash of the newest commit it \
covers (its timestamp becomes the entry's time), and "text"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "through": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["through", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entries"],
    "additionalProperties": False,
}


def newest_entry_time(page: str) -> datetime:
    m = ENTRY.search(page)
    if not m:
        sys.exit("no changelog entries found in index.html")
    return datetime.strptime(m.group("time"), TIME_FMT).replace(tzinfo=timezone.utc)


def commits_since(since: datetime) -> list[dict]:
    # %x1f/%x1e: unit/record separators, so bodies can hold anything.
    out = subprocess.run(
        ["git", "log", "--no-merges", "--reverse",
         f"--since={since.isoformat()}",
         "--format=%h%x1f%aI%x1f%an%x1f%s%x1f%b%x1e"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    commits = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        sha, when, author, subject, body = rec.strip("\n").split("\x1f")
        when = datetime.fromisoformat(when).astimezone(timezone.utc)
        # Entry times are to the minute, so compare at that precision:
        # anything in the newest entry's minute is already covered.
        if when.replace(second=0, microsecond=0) <= since or SKIP_SUBJECT.match(subject) or SKIP_AUTHOR.search(author):
            continue
        # Drop attribution trailers; they're noise for the summary.
        body = "\n".join(
            l for l in body.splitlines()
            if not re.match(r"^(Co-Authored-By|Claude-Session|Signed-off-by):", l, re.I)
        ).strip()
        commits.append({"sha": sha, "when": when, "subject": subject, "body": body})
    return commits


def ask_claude(existing: list[str], commits: list[dict]) -> list[dict]:
    import anthropic

    log = "\n\n".join(
        f"{c['sha']}  {c['when'].strftime(TIME_FMT)}  {c['subject']}"
        + (f"\n{c['body']}" if c["body"] else "")
        for c in commits
    )
    prompt = (
        "<existing_entries>\n" + "\n".join(existing) + "\n</existing_entries>\n\n"
        "<commits oldest_first=\"true\">\n" + log + "\n</commits>"
    )

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        sys.exit("Claude declined to write the changelog; nothing changed")
    if response.stop_reason == "max_tokens":
        sys.exit("response hit max_tokens; nothing changed")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["entries"]


def render(entries: list[dict], commits: list[dict], indent: str) -> str:
    when_by_sha = {c["sha"]: c["when"] for c in commits}
    latest = commits[-1]["when"]
    rows = []
    for e in entries:
        text = e["text"].strip().rstrip(".")
        if not text:
            continue
        when = when_by_sha.get(e["through"].strip()[:len(commits[0]["sha"])], latest)
        stamp = when.strftime(TIME_FMT)
        msg = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", html.escape(text, quote=False))
        rows.append((when, stamp, msg))
    rows.sort(key=lambda r: r[0], reverse=True)  # newest first, like the list
    return "".join(
        f'{indent}  <li><time>{stamp}</time><span class="changelog__msg">{msg}</span></li>\n'
        for _, stamp, msg in rows
    )


def main() -> None:
    dry = "--dry-run" in sys.argv
    page = INDEX.read_text()
    since = newest_entry_time(page)
    commits = commits_since(since)
    if not commits:
        print(f"nothing since {since.strftime(TIME_FMT)}")
        return
    print(f"{len(commits)} commits since {since.strftime(TIME_FMT)}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; skipping. Add it as a repo secret to turn this on.")
        return

    existing = [f"{m['time']}  {m['msg']}" for m in ENTRY.finditer(page)][:15]
    entries = ask_claude(existing, commits)
    m = LIST_OPEN.search(page)
    rows = render(entries, commits, m.group("indent"))
    if not rows:
        print("nothing worth a line")
        return
    print(rows)
    if dry:
        return
    INDEX.write_text(page[: m.end()] + rows + page[m.end():])


if __name__ == "__main__":
    main()
