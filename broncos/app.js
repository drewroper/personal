import { GAMES, SEED, SEASON, VENUE, VENUE_ADDRESS, TEAM } from './schedule.js';
import { config } from './config.js';
import { TZ, gameDate, gameEnd, icsUtc, icsDate, nextDay, buildIcs, gameDescription } from './ics.js';

const FIREBASE_CDN = 'https://www.gstatic.com/firebasejs/12.2.1';
const LS_STATE = `broncos-${SEASON}-state`;
const LS_ME = `broncos-${SEASON}-me`;
const PALETTE = ['#FFB000', '#FF6FA5', '#5AB4FF', '#7EE787', '#C792EA', '#FF8A5B', '#4DD0E1', '#F4E04D', '#A8E6CF', '#F28B82'];

// ----------------------------------------------------------------------------
// Store. One shared document: { people, claims, unavailable, notes }.
// Every mutation is a "patch": a map of dotted paths to values (or DELETE).
// The Firestore adapter forwards patches as field-path updates, so two people
// editing different games at the same moment never clobber each other. The
// local adapter applies the same patches to a copy in localStorage.
// ----------------------------------------------------------------------------
const DELETE = Symbol('delete');

function applyPatch(obj, patch) {
  for (const [path, value] of Object.entries(patch)) {
    const keys = path.split('.');
    let cur = obj;
    for (let i = 0; i < keys.length - 1; i++) {
      if (typeof cur[keys[i]] !== 'object' || cur[keys[i]] === null) cur[keys[i]] = {};
      cur = cur[keys[i]];
    }
    const last = keys[keys.length - 1];
    if (value === DELETE) delete cur[last];
    else cur[last] = value;
  }
  return obj;
}

function normalize(data) {
  const s = data && typeof data === 'object' ? data : {};
  return {
    people: s.people || {},
    claims: s.claims || {},
    unavailable: s.unavailable || {},
    notes: s.notes || {},
  };
}

function createLocalStore(onChange) {
  let data;
  try { data = JSON.parse(localStorage.getItem(LS_STATE)); } catch { data = null; }
  if (!data) data = structuredClone(SEED);
  const save = () => { try { localStorage.setItem(LS_STATE, JSON.stringify(data)); } catch {} };
  save();
  queueMicrotask(() => onChange(normalize(data)));
  return {
    mode: 'local',
    async patch(p) { applyPatch(data, p); save(); onChange(normalize(structuredClone(data))); },
  };
}

async function createFirestoreStore(onChange) {
  const [{ initializeApp }, fs] = await Promise.all([
    import(`${FIREBASE_CDN}/firebase-app.js`),
    import(`${FIREBASE_CDN}/firebase-firestore.js`),
  ]);
  const app = initializeApp(config.firebase);
  const db = fs.getFirestore(app);
  const ref = fs.doc(db, 'broncos', config.seasonDocId || `season-${SEASON}`);

  // First visitor ever creates the document from SEED. A transaction keeps two
  // simultaneous first visitors from both writing it.
  await fs.runTransaction(db, async (tx) => {
    const snap = await tx.get(ref);
    if (!snap.exists()) tx.set(ref, { ...structuredClone(SEED), createdAt: fs.serverTimestamp() });
  });

  await new Promise((resolve, reject) => {
    let first = true;
    fs.onSnapshot(ref, (snap) => {
      onChange(normalize(snap.data()));
      if (first) { first = false; resolve(); }
    }, (err) => { if (first) { first = false; reject(err); } else setStatus('error', 'Sync error'); });
  });

  return {
    mode: 'live',
    async patch(p) {
      const out = {};
      for (const [k, v] of Object.entries(p)) out[k] = v === DELETE ? fs.deleteField() : v;
      out.updatedAt = fs.serverTimestamp();
      await fs.updateDoc(ref, out);
    },
  };
}

// ----------------------------------------------------------------------------
// Derived data
// ----------------------------------------------------------------------------
let state = normalize(SEED);
let store = null;
let me = localStorage.getItem(LS_ME) || '';
let filter = 'all';

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function peopleSorted() {
  return Object.entries(state.people)
    .map(([id, p]) => ({ id, ...p }))
    .sort((a, b) => (a.order ?? 99) - (b.order ?? 99) || a.name.localeCompare(b.name));
}
const person = (id) => (id && state.people[id]) ? { id, ...state.people[id] } : null;
const isOut = (gameId, pid) => !!(state.unavailable[gameId] && state.unavailable[gameId][pid]);

// Who has the tickets for a game.
//   claimed: someone took it.  default: unclaimed, defaults to available default holders.
//   open: unclaimed and every default holder is out (or there are none).
function holdersFor(game) {
  const claimant = person(state.claims[game.id]);
  if (claimant) return { kind: 'claimed', people: [claimant], warn: isOut(game.id, claimant.id) };
  const defaults = peopleSorted().filter((p) => p.defaultHolder && !isOut(game.id, p.id));
  if (defaults.length) return { kind: 'default', people: defaults, warn: false };
  return { kind: 'open', people: [], warn: false };
}

function isPast(g) { return gameEnd(g) < new Date(); }
function nextGame() { return GAMES.find((g) => !isPast(g)); }

const fmtDay = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric' });
const fmtTime = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' });
function whenText(g) {
  const d = gameDate(g);
  const day = fmtDay.format(d);
  const time = g.kickoff ? `${fmtTime.format(d)} MT` : 'Time TBA';
  return { day, time };
}

// ----------------------------------------------------------------------------
// Rendering
// ----------------------------------------------------------------------------
function setStatus(kind, text) {
  const el = $('#status');
  el.className = `topbar__status mono is-${kind}`;
  el.querySelector('.txt').textContent = text;
}

function showBanner(kind, html) {
  const el = $('#banner');
  el.hidden = false;
  el.className = `banner is-${kind}`;
  el.innerHTML = html;
}

let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('is-on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-on'), 2200);
}

function renderMe() {
  const sel = $('#me');
  const cur = me;
  sel.innerHTML = '<option value="">Pick your name…</option>' +
    peopleSorted().map((p) => `<option value="${esc(p.id)}"${p.id === cur ? ' selected' : ''}>${esc(p.name)}</option>`).join('');
  if (me && !state.people[me]) { me = ''; localStorage.removeItem(LS_ME); }
  $('#me-hint').textContent = me ? 'Remembered on this device.' : 'Pick yourself to claim games and mark when you can’t go.';
}

function renderSummary() {
  const counts = {};
  for (const p of peopleSorted()) counts[p.id] = 0;
  let open = 0;
  for (const g of GAMES) {
    const h = holdersFor(g);
    if (h.kind === 'open') open++;
    for (const p of h.people) counts[p.id]++;
  }
  $('#chips').innerHTML = peopleSorted().map((p) => `
    <button class="chip${p.id === me ? ' is-me' : ''}" data-me="${esc(p.id)}" style="--c:${esc(p.color)}" title="Set yourself as ${esc(p.name)}">
      <span class="swatch"></span>${esc(p.name)}<span class="count">${counts[p.id]}</span>
    </button>`).join('');
  $('#summary-sub').textContent = open ? `${open} game${open === 1 ? '' : 's'} need${open === 1 ? 's' : ''} a taker` : 'Every game is covered';
}

function gameCard(g, next) {
  const h = holdersFor(g);
  const past = isPast(g);
  const { day, time } = whenText(g);
  const mine = !!me && h.people.some((p) => p.id === me);
  const claimedByMe = state.claims[g.id] === me;
  const iAmOut = !!me && isOut(g.id, me);
  const note = state.notes[g.id] || '';

  const holderWho = h.kind === 'open'
    ? `<span class="who">Needs a taker</span>`
    : h.people.map((p) => `<span class="who" style="--c:${esc(p.color)}"><span class="swatch"></span>${esc(p.name)}</span>`).join('<span class="k">&amp;</span>');
  const holderNote = h.kind === 'default' ? `<span class="note">default</span>`
    : h.warn ? `<span class="note" style="color:var(--warn)">but marked out</span>` : '';

  const assign = `<span class="assign"><select data-assign="${esc(g.id)}" aria-label="Give these tickets to">
      <option value="">Give to…</option>
      ${peopleSorted().map((p) => `<option value="${esc(p.id)}"${state.claims[g.id] === p.id ? ' selected' : ''}>${esc(p.name)}</option>`).join('')}
      ${state.claims[g.id] ? '<option value="__release">Back to default</option>' : ''}
    </select></span>`;

  let actions = '';
  if (me && !past) {
    if (claimedByMe) actions += `<button class="btn" data-release="${esc(g.id)}">Give these back</button>`;
    else if (mine) actions += `<button class="btn is-quiet" disabled>Yours by default</button>`;
    else actions += `<button class="btn is-primary" data-claim="${esc(g.id)}">I’ll take these</button>`;
    actions += iAmOut
      ? `<button class="btn is-out" data-avail="${esc(g.id)}">I’m out — mark me available</button>`
      : `<button class="btn" data-out="${esc(g.id)}">Can’t make it</button>`;
  }
  actions += `<button class="btn is-link" data-note="${esc(g.id)}">${note ? 'Edit note' : 'Add note'}</button>`;
  actions += `<a class="btn is-link" href="${gcalLink(g, h)}" target="_blank" rel="noopener">Google Cal ↗</a>`;

  const pills = peopleSorted().map((p) => {
    const out = isOut(g.id, p.id);
    const holder = h.people.some((x) => x.id === p.id);
    return `<button class="pill${holder ? ' is-holder' : ''}${out ? ' is-out' : ''}" style="--c:${esc(p.color)}" data-toggle-out="${esc(g.id)}" data-pid="${esc(p.id)}" title="${esc(p.name)}: ${out ? 'out — tap to mark available' : 'available — tap to mark out'}"><span class="swatch"></span>${esc(p.name)}</button>`;
  }).join('');

  const tags = [];
  if (past) tags.push('<span class="tag" style="color:var(--text-faint)">Played</span>');
  else if (next && next.id === g.id) tags.push('<span class="tag is-next">Next up</span>');
  if (g.tag) tags.push(`<span class="tag">${esc(g.tag)}</span>`);

  return `
  <article class="game${past ? ' is-past' : ''}${next && next.id === g.id && !past ? ' is-next' : ''}${h.kind === 'open' && !past ? ' is-open' : ''}${mine ? ' is-mine' : ''}" id="game-${esc(g.id)}">
    <div class="game__meta mono">
      <span class="week">Week ${g.week}</span><span>${esc(g.tv)}</span>${tags.join('')}
    </div>
    <div class="game__title">
      <h3><span class="vs">vs</span>${esc(g.short)}</h3>
      <span class="game__when">${esc(day)} · <span class="time">${esc(time)}</span></span>
    </div>
    <div class="holder${h.kind === 'open' ? ' is-open' : ''}">
      <span class="k mono">Tickets</span>${holderWho}${holderNote}${assign}
    </div>
    ${note ? `<div class="holder" style="border:0;background:none;padding:6px 2px 0;color:var(--text-muted)">“${esc(note)}”</div>` : ''}
    <div class="actions">${actions}</div>
    <div class="avail">
      <span class="lbl mono">Availability · tap a name to toggle</span>${pills}
    </div>
  </article>`;
}

function renderGames() {
  const next = nextGame();
  let list = GAMES;
  if (filter === 'mine') list = GAMES.filter((g) => me && holdersFor(g).people.some((p) => p.id === me));
  if (filter === 'open') list = GAMES.filter((g) => holdersFor(g).kind === 'open' && !isPast(g));
  const counts = {
    all: GAMES.length,
    mine: me ? GAMES.filter((g) => holdersFor(g).people.some((p) => p.id === me)).length : 0,
    open: GAMES.filter((g) => holdersFor(g).kind === 'open' && !isPast(g)).length,
  };
  for (const b of document.querySelectorAll('#filters button')) {
    const f = b.dataset.filter;
    b.classList.toggle('is-on', f === filter);
    const label = { all: 'All', mine: 'Mine', open: 'Needs a taker' }[f];
    b.innerHTML = `${label}<span class="n">${counts[f]}</span>`;
  }
  $('#games').innerHTML = list.length
    ? list.map((g) => gameCard(g, next)).join('')
    : `<p style="color:var(--text-faint);padding:12px 4px">${filter === 'mine' && !me ? 'Pick your name above first.' : 'Nothing here.'}</p>`;
}

function renderCal() {
  const base = `${location.origin}${location.pathname.replace(/[^/]*$/, '')}`;
  const icsUrl = `${base}broncos-home-${SEASON}.ics`;
  const webcal = icsUrl.replace(/^https?:/, 'webcal:');
  const mine = me ? person(me) : null;
  $('#cal').innerHTML = `
    <div class="cal__row">
      <span class="t">${mine ? `${esc(mine.name)}’s games` : 'My games'} (.ics)</span>
      <button class="btn" data-ics="mine"${mine ? '' : ' disabled'}>Download</button>
      <span class="d">Only the games ${mine ? esc(mine.name) : 'you'} currently hold${mine ? '' : ' — pick your name first'}. Re-download if things change.</span>
    </div>
    <div class="cal__row">
      <span class="t">All eight home games (.ics)</span>
      <button class="btn" data-ics="all">Download</button>
      <span class="d">Every home game, no names. Or subscribe so it stays updated: <code>${esc(webcal)}</code></span>
    </div>`;
}

function renderPeople() {
  $('#people-list').innerHTML = peopleSorted().map((p) => `
    <div class="person" style="--c:${esc(p.color)}">
      <button class="swatch" data-recolor="${esc(p.id)}" title="Change color" aria-label="Change ${esc(p.name)}'s color"></button>
      <div>
        <button class="name" data-rename="${esc(p.id)}" title="Rename">${esc(p.name)}</button><br />
        <label class="default"><input type="checkbox" data-default="${esc(p.id)}"${p.defaultHolder ? ' checked' : ''} /> Gets unclaimed games</label>
      </div>
      <div class="tools">
        <button class="btn is-quiet" data-remove="${esc(p.id)}">Remove</button>
      </div>
    </div>`).join('');
}

function render() {
  renderMe();
  renderSummary();
  renderGames();
  renderCal();
  renderPeople();
}

// ----------------------------------------------------------------------------
// Calendar export
// ----------------------------------------------------------------------------
function download(name, text) {
  const blob = new Blob([text], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function gcalLink(g, h) {
  const holders = h.kind === 'open' ? 'Needs a taker' : h.people.map((p) => p.name).join(' & ');
  const p = new URLSearchParams({
    action: 'TEMPLATE',
    text: `Broncos vs ${g.short} (tickets: ${holders})`,
    location: `${VENUE}, ${VENUE_ADDRESS}`,
    details: `${gameDescription(g)}\n${location.href}`,
    dates: g.kickoff ? `${icsUtc(gameDate(g))}/${icsUtc(gameEnd(g))}` : `${icsDate(g.date)}/${icsDate(nextDay(g.date))}`,
  });
  return `https://calendar.google.com/calendar/render?${p}`;
}

// ----------------------------------------------------------------------------
// Actions
// ----------------------------------------------------------------------------
async function commit(patch, msg) {
  try {
    await store.patch(patch);
    if (msg) toast(msg);
  } catch (err) {
    console.error(err);
    toast(`Couldn’t save: ${err.message || err}`);
  }
}

function slug(name) {
  const base = name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'person';
  let id = base, n = 2;
  while (state.people[id]) id = `${base}_${n++}`;
  return id;
}

function needMe() {
  if (me) return true;
  toast('Pick your name first');
  $('#me').focus();
  return false;
}

function setMe(id) {
  me = id || '';
  if (me) localStorage.setItem(LS_ME, me); else localStorage.removeItem(LS_ME);
  render();
}

document.addEventListener('click', async (e) => {
  const t = e.target.closest('[data-me],[data-claim],[data-release],[data-out],[data-avail],[data-toggle-out],[data-note],[data-ics],[data-remove],[data-rename],[data-recolor]');
  if (!t) return;
  const d = t.dataset;
  const g = (id) => GAMES.find((x) => x.id === id);

  if (d.me !== undefined) return setMe(d.me);

  if (d.claim) {
    if (!needMe()) return;
    const cur = person(state.claims[d.claim]);
    if (cur && cur.id !== me && !confirm(`${cur.name} has these. Take them?`)) return;
    return commit({ [`claims.${d.claim}`]: me, [`unavailable.${d.claim}.${me}`]: DELETE }, `You’ve got the ${g(d.claim).short} game`);
  }
  if (d.release) return commit({ [`claims.${d.release}`]: DELETE }, 'Given back');
  if (d.out) { if (!needMe()) return; return commit({ [`unavailable.${d.out}.${me}`]: true }, `Marked out for ${g(d.out).short}`); }
  if (d.avail) { if (!needMe()) return; return commit({ [`unavailable.${d.avail}.${me}`]: DELETE }, 'Marked available'); }
  if (d.toggleOut) {
    const out = isOut(d.toggleOut, d.pid);
    return commit({ [`unavailable.${d.toggleOut}.${d.pid}`]: out ? DELETE : true });
  }
  if (d.note) {
    const cur = state.notes[d.note] || '';
    const v = prompt('Note for this game (who’s going, seats, whatever):', cur);
    if (v === null) return;
    return commit({ [`notes.${d.note}`]: v.trim() ? v.trim().slice(0, 200) : DELETE });
  }
  if (d.ics === 'all') {
    return download(`broncos-home-${SEASON}.ics`, buildIcs(GAMES, (gm) => ({ summary: `Broncos vs ${gm.short}`, description: gameDescription(gm) })));
  }
  if (d.ics === 'mine') {
    if (!needMe()) return;
    const p = person(me);
    const games = GAMES.filter((gm) => holdersFor(gm).people.some((x) => x.id === me));
    if (!games.length) return toast('You don’t hold any games yet');
    return download(`broncos-${p.name.toLowerCase()}-${SEASON}.ics`, buildIcs(games, (gm) => {
      const h = holdersFor(gm);
      return { summary: `Broncos vs ${gm.short} 🎟`, description: `${gameDescription(gm)}\nTickets: ${h.people.map((x) => x.name).join(' & ')}\n${location.href}` };
    }));
  }
  if (d.remove) {
    const p = person(d.remove);
    if (!p || !confirm(`Remove ${p.name}? Any games they hold go back to default.`)) return;
    const patch = { [`people.${d.remove}`]: DELETE };
    for (const [gid, pid] of Object.entries(state.claims)) if (pid === d.remove) patch[`claims.${gid}`] = DELETE;
    for (const [gid, m] of Object.entries(state.unavailable)) if (m && m[d.remove]) patch[`unavailable.${gid}.${d.remove}`] = DELETE;
    if (me === d.remove) setMe('');
    return commit(patch, `Removed ${p.name}`);
  }
  if (d.rename) {
    const p = person(d.rename);
    const v = prompt('Name:', p.name);
    if (v === null || !v.trim()) return;
    return commit({ [`people.${d.rename}.name`]: v.trim().slice(0, 32) });
  }
  if (d.recolor) {
    const p = person(d.recolor);
    const i = PALETTE.findIndex((c) => c.toLowerCase() === (p.color || '').toLowerCase());
    return commit({ [`people.${d.recolor}.color`]: PALETTE[(i + 1) % PALETTE.length] });
  }
});

document.addEventListener('change', (e) => {
  const t = e.target;
  if (t.id === 'me') return setMe(t.value);
  if (t.dataset.assign) {
    const gid = t.dataset.assign, v = t.value;
    if (!v) return;
    if (v === '__release') return commit({ [`claims.${gid}`]: DELETE }, 'Back to default');
    const p = person(v);
    return commit({ [`claims.${gid}`]: v, [`unavailable.${gid}.${v}`]: DELETE }, `${p.name} has the ${GAMES.find((x) => x.id === gid).short} game`);
  }
  if (t.dataset.default) return commit({ [`people.${t.dataset.default}.defaultHolder`]: t.checked });
});

$('#filters').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-filter]');
  if (!b) return;
  filter = b.dataset.filter;
  renderGames();
});

$('#person-add').addEventListener('submit', (e) => {
  e.preventDefault();
  const input = e.target.elements.name;
  const name = input.value.trim().slice(0, 32);
  if (!name) return;
  const id = slug(name);
  const used = new Set(peopleSorted().map((p) => (p.color || '').toLowerCase()));
  const color = PALETTE.find((c) => !used.has(c.toLowerCase())) || PALETTE[Object.keys(state.people).length % PALETTE.length];
  const order = Math.max(0, ...peopleSorted().map((p) => p.order ?? 0)) + 1;
  input.value = '';
  commit({ [`people.${id}`]: { name, color, order, defaultHolder: false } }, `Added ${name}`);
});

// ----------------------------------------------------------------------------
// Boot
// ----------------------------------------------------------------------------
function onChange(next) { state = next; render(); }

(async () => {
  setStatus('local', 'Connecting');
  if (config.firebase && config.firebase.projectId) {
    try {
      store = await createFirestoreStore(onChange);
      setStatus('live', 'Live');
    } catch (err) {
      console.error(err);
      showBanner('error', `<span>⚠️</span><div><strong>Couldn’t reach the shared database</strong> (${esc(err.code || err.message || err)}). Running on this device only — check the Firestore rules and the config in <code>config.js</code>.</div>`);
      store = createLocalStore(onChange);
      setStatus('error', 'Offline');
    }
  } else {
    store = createLocalStore(onChange);
    setStatus('local', 'This device only');
    showBanner('warn', `<span>⚠️</span><div><strong>Not connected to a shared database yet.</strong> Everything works, but changes stay on this device. See <a href="https://github.com/drewroper/personal/blob/HEAD/broncos/README.md" target="_blank" rel="noopener">README</a> for the 5-minute Firebase setup.</div>`);
  }
})();
