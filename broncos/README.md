# Broncos tickets

Who's got the Broncos home-game tickets this season. Lives at
**https://drewroper.com/broncos** — it's just static files in this folder,
deployed by GitHub Pages like the rest of the site.

## How it works

- Eight home games, one card each. Anyone can **take** a game, **give it
  back**, or hand it to someone else with the "Give to…" menu.
- Games nobody has taken default to whoever has **"Gets unclaimed games"**
  checked (Drew and Megan to start).
- Anyone can mark themselves **out** for a game. If every default holder is
  out on an unclaimed game, it flips to **"Needs a taker"** and shows up in
  that filter.
- Pick your name once and the page remembers you on that device. There's no
  login — it's a family page.
- **Manage people** at the bottom: add, rename, recolor, remove, and set who
  gets the unclaimed games.
- **Calendars**: download your games as an `.ics`, or subscribe to the
  all-home-games feed at `webcal://drewroper.com/broncos/broncos-home-2026.ics`.
  Each card also has a Google Calendar link.

## Connect the shared database (5 minutes, one time)

Until this is done the page runs in **"This device only"** mode: it works,
but nothing is shared between people. Firebase's free tier is more than
enough for this, and it needs no server.

1. Go to https://console.firebase.google.com and **Add project** (call it
   anything, e.g. `broncos-tix`). Turn off Google Analytics when asked.
2. In the left nav, **Build → Firestore Database → Create database**.
   Pick a US region, choose **Start in production mode**, Create.
3. Open the **Rules** tab and replace everything with this, then Publish:

   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /broncos/{doc} {
         allow read, write: if true;
       }
     }
   }
   ```

   This makes the `broncos` collection editable by anyone who has the URL,
   which is the point. Nothing else in the project is reachable.
4. Back on **Project Overview**, click the **`</>`** (web) icon to register
   a web app. Name it anything, skip hosting, and copy the
   `firebaseConfig = { ... }` object it shows you.
5. Paste that object into [`config.js`](./config.js) as the `firebase`
   value, commit, push. Done — the status dot in the top-right turns green
   and says **Live**.

The first person to open the page creates the season record with the five
of us and Mason on the Raiders game. After that, everything is edited in
the app.

## Maintenance

- **Kickoff time flexes / Week 18 time announced:** edit
  [`schedule.js`](./schedule.js), run `node scripts/build-broncos-ics.mjs`
  to refresh the subscribable calendar, push.
- **Playoff game:** append it to `GAMES` in `schedule.js` with a new `id`.
- **New season:** update `schedule.js` and set a new `seasonDocId` in
  `config.js` (e.g. `season-2027`). The old season's data stays in Firestore.

## Files

| File | What |
|------|------|
| `index.html` | Page + styles |
| `app.js` | All the logic: shared store, rendering, calendar export |
| `schedule.js` | The home schedule and the first-run people list |
| `ics.js` | Calendar helpers, shared with the build script |
| `config.js` | Firebase config (the only thing you need to touch) |
| `broncos-home-2026.ics` | Generated; the subscribable all-games calendar |
