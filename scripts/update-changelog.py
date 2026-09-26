#!/usr/bin/env python3
"""
Write new changelog entries for the "Last touched" drawer in index.html.
Run by the .github/workflows/changelog.yml nightly cron.

One entry per day: every Denver day with at least one commit gets
exactly one entry, however small the day was, and a busy day's forty
commits become one entry too. Only finished days are written, so a
day is never split across two entries.

Reads the newest <time> in the changelog, collects the commits from
the days after it (skipping merges, bot refreshes and changelog
commits), and asks Claude for one entry per day in the drawer's
voice. The entries go in at the top of the list, newest first.

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

MODEL = "claude-opus-5"
TZ = ZoneInfo("America/Denver")   # a "day" is a day in Denver

# Commits that never make the changelog: the hourly life-log bot, the
# changelog's own commits, and merges (their branches' commits count).
SKIP_SUBJECT = re.compile(r"^(life-log: refresh|changelog:)", re.I)
SKIP_AUTHOR = re.compile(r"\[bot\]$")

# The life log's entries are content, not site changes: it updates
# itself, and new beers or books are it working as intended. Commits
# that only touch its data are skipped; a new category or a change to
# the /log page touches log.html, log.js or the fetcher, and counts.
LOG_DATA = re.compile(r"^data/(life-log\.json$|raw-songkick/)")

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
since the newest one, grouped by day. Write exactly one entry per day.

What the site is:
- / is the homepage (portrait, headline, clients chyron, work grid, colophon).
- /log.html is a quiet life log (films, records, shows, beers, books, runs) \
that refreshes itself from Letterboxd, Discogs, Untappd, Strava and GitHub. \
New entries in it are the log working, not changelog news; write about the \
log only when its page or its categories change.
- /40 is "40 albums, 40 days", a daily countdown of records before Drew turns 40.
- "stories:" and "build-story" commits are an offline renderer for Instagram \
story videos, "docs:" are internal notes, "make-wear"/"fetch-*" are asset \
scripts. They aren't the site itself, so lead with what changed on the site; \
on a day that only touched these, say briefly what the behind-the-scenes \
work was.

How to write:
- Match the voice of the existing entries: plain, specific, a little dry. \
Sentences, not bullet fragments. No trailing period. Say what changed and, \
when it matters, why. Name fonts, sizes and colours precisely; this is a \
designer's site.
- Exactly one entry per day given, never more, never fewer. A day with one \
small commit still gets a line (a short one is fine). A day with dozens \
gets one entry about what it added up to: fold fiddly iterations (tweak, \
revert, retune) into the result they led to, and lead with the biggest thing.
- Keep each entry under about 60 words.
- Never spoil what the site keeps hidden. On /40, name a record only if a \
commit publishes it or marks it live; commits often name upcoming days, and \
those stay secret. Easter eggs (hidden records, secret albums, where the log \
lives) can be hinted at, never revealed.
- Plain text only, except _italics_ for record, book and film titles.

For each entry return "date" (the day, YYYY-MM-DD, as given) and "text"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["date", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entries"],
    "additionalProperties": False,
}


def newest_entry_day(page: str) -> str:
    m = ENTRY.search(page)
    if not m:
        sys.exit("no changelog entries found in index.html")
    when = datetime.strptime(m.group("time"), TIME_FMT).replace(tzinfo=timezone.utc)
    return when.astimezone(TZ).date().isoformat()


def days_after(last_day: str) -> dict[str, list[dict]]:
    """Commits from the days after last_day up to yesterday, by Denver day."""
    today = datetime.now(TZ).date().isoformat()
    since = datetime.fromisoformat(last_day).replace(tzinfo=TZ) + timedelta(days=1)
    # %x1e/%x1f: record/unit separators, so bodies can hold anything.
    # --name-only lists each commit's files after its last field.
    out = subprocess.run(
        ["git", "log", "--no-merges", "--reverse",
         f"--since={since.isoformat()}",
         "--name-only", "--format=%x1e%h%x1f%aI%x1f%an%x1f%s%x1f%b%x1f"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    days: dict[str, list[dict]] = {}
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        sha, when, author, subject, body, names = rec.split("\x1f")
        files = names.split()
        when = datetime.fromisoformat(when)
        day = when.astimezone(TZ).date().isoformat()
        # Today isn't over yet; it waits for tomorrow night's run.
        if not (last_day < day < today):
            continue
        if SKIP_SUBJECT.match(subject) or SKIP_AUTHOR.search(author):
            continue
        if files and all(LOG_DATA.match(f) for f in files):
            continue
        # Drop attribution trailers; they're noise for the summary.
        body = "\n".join(
            l for l in body.splitlines()
            if not re.match(r"^(Co-Authored-By|Claude-Session|Signed-off-by):", l, re.I)
        ).strip()
        days.setdefault(day, []).append({
            "sha": sha, "when": when.astimezone(timezone.utc),
            "subject": subject, "body": body,
        })
    return dict(sorted(days.items()))


def ask_claude(existing: list[str], days: dict[str, list[dict]]) -> dict[str, str]:
    import anthropic

    log = "\n\n".join(
        f'<day date="{day}" commits="{len(commits)}">\n'
        + "\n".join(
            f"{c['sha']}  {c['subject']}" + (f"\n{c['body']}" if c["body"] else "")
            for c in commits
        )
        + "\n</day>"
        for day, commits in days.items()
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
    entries = {e["date"]: e["text"] for e in json.loads(text)["entries"]}
    if set(entries) != set(days):
        sys.exit(f"expected entries for {sorted(days)}, got {sorted(entries)}; nothing changed")
    return entries


def render(entries: dict[str, str], days: dict[str, list[dict]], indent: str) -> str:
    rows = []
    for day in sorted(days, reverse=True):   # newest first, like the list
        text = entries[day].strip().rstrip(".")
        # Stamped with the day's last commit.
        stamp = days[day][-1]["when"].strftime(TIME_FMT)
        msg = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", html.escape(text, quote=False))
        rows.append(f'{indent}  <li><time>{stamp}</time><span class="changelog__msg">{msg}</span></li>\n')
    return "".join(rows)


def main() -> None:
    dry = "--dry-run" in sys.argv
    page = INDEX.read_text()
    last_day = newest_entry_day(page)
    days = days_after(last_day)
    if not days:
        print(f"no finished days with commits after {last_day}")
        return
    for day, commits in days.items():
        print(f"{day}: {len(commits)} commits")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; skipping. Add it as a repo secret to turn this on.")
        return

    existing = [f"{m['time']}  {m['msg']}" for m in ENTRY.finditer(page)][:15]
    entries = ask_claude(existing, days)
    m = LIST_OPEN.search(page)
    rows = render(entries, days, m.group("indent"))
    print(rows)
    if dry:
        return
    INDEX.write_text(page[: m.end()] + rows + page[m.end():])


if __name__ == "__main__":
    main()
