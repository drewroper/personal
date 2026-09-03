# Broncos tickets

A private, password-protected page where the family sees who has the
tickets to each Broncos home game, claims games, and marks the ones they
can't make. It runs on Cloudflare Pages (free) and lives in this folder.

Nobody installs anything. They open a link in their phone's browser, type
the family password once, pick their name once, and tap buttons.

## Setting it up (one time, about 15 minutes, $0)

You need a free Cloudflare account. It never asks for a credit card, and
this page uses a tiny fraction of the free plan.

### 1. Make the account

1. Go to https://dash.cloudflare.com/sign-up and sign up with your email.
2. Confirm the email they send you and log in.
3. You'll land on a dashboard. Ignore everything about "adding a domain"
   or "onboarding". You don't need any of that.

### 2. Create the site from this GitHub repo

1. In the left sidebar click **Compute (Workers)**, then **Workers & Pages**.
2. Click the blue **Create** button, then the **Pages** tab, then
   **Connect to Git** (or "Import an existing Git repository").
3. Click **Connect GitHub**. GitHub will ask you to install the Cloudflare
   app. Choose **Only select repositories** and pick **personal**. Approve.
4. Back in Cloudflare, select the **personal** repo and click
   **Begin setup**.
5. Fill in the form exactly like this:
   - **Project name:** `broncos` (this becomes the web address, so
     `broncos.pages.dev`; if that name is taken, try `broncos-tix` or
     similar)
   - **Production branch:** whatever branch this folder is merged into
     (your default branch)
   - **Framework preset:** None
   - **Build command:** leave empty
   - **Build output directory:** `public`
   - Click **Root directory (advanced)** and set it to `broncos`
6. Click **Save and Deploy**. Wait a minute. It will say the deployment
   succeeded, but the page will show "Not set up yet" until step 3 is done.

### 3. Add the password and the database

1. On the project page click **Settings** (top tabs).
2. Find **Variables and Secrets** → **Add**.
   - Type: **Secret**
   - Variable name: `FAMILY_PASSWORD`
   - Value: the password you want the family to use. Keep it simple enough
     to text to your dad. Something like `MileHigh2026`.
   - Save.
3. Find **Bindings** → **Add** → choose **D1 database**.
   - Variable name: `DB`
   - D1 database: click **Create new database** (or go make one first at
     Compute → D1 SQL Database → Create, named `broncos`), then pick it.
   - Save.
4. Go to the **Deployments** tab, click the **⋯** on the latest deployment,
   and choose **Retry deployment**. Settings only apply to new deployments.

### 4. Stop it from rebuilding every hour

This repo has a robot that commits every hour (the life log). Cloudflare's
free plan allows 500 builds a month, so tell it to only build when this
folder changes:

1. **Settings** → **Build** → **Build watch paths** (or "Builds & deployments").
2. Set **Include paths** to `broncos/*` and save.

### 5. Try it

Open `https://broncos.pages.dev` (or whatever name you chose). You should
see the password screen. Type the password, pick your name, and you're in.
Text the link and the password to the family.

That's it. There is nothing to maintain after this.

## Optional: a nicer address

`broncos.pages.dev` works fine. If you'd rather have `broncos.drewroper.com`:
in the project click **Custom domains** → **Set up a custom domain**, type
`broncos.drewroper.com`, and it will tell you a single CNAME record to add
wherever you manage drewroper.com's DNS. Takes a few minutes to go live.

## How the page works

- Eight home games, one card each. Anyone can **take** a game, **give it
  back**, or hand it to someone with the **Give to…** menu.
- Games nobody has taken default to whoever has **"Gets unclaimed games"**
  checked. Drew and Megan to start.
- Anyone can mark themselves **out** for a game. If every default holder is
  out on an unclaimed game, it flips to **"Needs a taker"**.
- **Manage people** at the bottom: add, rename, recolor, remove, and set who
  gets unclaimed games.
- **Calendars**: each person gets a subscribe link for their own games. Once
  subscribed, it updates itself when games change hands. There's also a feed
  of all eight games, and a Google Calendar link on every card.
- Changes from other people show up within a few seconds.
- Everyone with the password can edit everything. It's a family page.

## Maintenance

- **Change the password:** edit the `FAMILY_PASSWORD` secret in Settings and
  retry the deployment. Everyone gets logged out and re-enters it. Old
  calendar links stop working; re-subscribe from the page.
- **Kickoff time flexes / Week 18 time announced:** edit
  `public/schedule.js`, commit, push. Cloudflare redeploys on its own.
- **Playoff game:** append it to `GAMES` in `public/schedule.js` with a new
  `id`.
- **New season:** update `public/schedule.js`, change `SEASON_ID` in
  `functions/_lib/state.js`, and update `functions/_lib/seed.js` if the
  starting lineup of people changed.

## Files

| Path | What |
|------|------|
| `public/index.html` | The page and its styles |
| `public/app.js` | All the browser logic |
| `public/schedule.js` | The home schedule |
| `public/ics.js` | Calendar-file helpers, shared with the server |
| `functions/_middleware.js` | The password gate and login page |
| `functions/api/state.js` | Reads and writes the shared list |
| `functions/cal/[[path]].js` | The subscribable calendar feeds |
| `functions/_lib/` | Auth, database, seed data, server pages |

## Running it locally (developers)

```
npx wrangler pages dev public --d1 DB --binding FAMILY_PASSWORD=test
```

from inside the `broncos` folder, then open http://127.0.0.1:8788.
