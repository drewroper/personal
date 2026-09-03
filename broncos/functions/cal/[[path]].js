// Calendar feeds. The middleware has already checked the key in the URL.
//   /cal/<key>/all.ics        every home game
//   /cal/<key>/<personId>.ics the games that person currently holds
// Subscribe once and it stays current as claims change.
import { GAMES, SEASON } from '../../public/schedule.js';
import { buildIcs, gameDescription } from '../../public/ics.js';
import { readState } from '../_lib/state.js';

function holdersFor(state, game) {
  const claimant = state.claims[game.id] && state.people[state.claims[game.id]];
  if (claimant) return [{ id: state.claims[game.id], ...claimant }];
  return Object.entries(state.people)
    .map(([id, p]) => ({ id, ...p }))
    .filter((p) => p.defaultHolder && !(state.unavailable[game.id] && state.unavailable[game.id][p.id]))
    .sort((a, b) => (a.order ?? 99) - (b.order ?? 99));
}

export async function onRequestGet({ request, env, params }) {
  const parts = params.path || [];
  const file = parts[1] || '';
  if (parts.length !== 2 || !file.endsWith('.ics')) return new Response('Not found', { status: 404 });
  const who = file.slice(0, -4);
  const { state } = await readState(env.DB);
  const site = new URL(request.url).origin;

  let games, name, label;
  if (who === 'all') {
    games = GAMES;
    name = `Broncos home games ${SEASON}`;
    label = (g) => {
      const h = holdersFor(state, g);
      return { summary: `Broncos vs ${g.short}`, description: `${gameDescription(g)}\nTickets: ${h.length ? h.map((p) => p.name).join(' & ') : 'needs a taker'}\n${site}` };
    };
  } else {
    const p = state.people[who];
    if (!p) return new Response('Not found', { status: 404 });
    games = GAMES.filter((g) => holdersFor(state, g).some((x) => x.id === who));
    name = `Broncos — ${p.name}'s games`;
    label = (g) => ({ summary: `Broncos vs ${g.short} 🎟`, description: `${gameDescription(g)}\nTickets: ${holdersFor(state, g).map((x) => x.name).join(' & ')}\n${site}` });
  }
  return new Response(buildIcs(games, label, { name }), {
    headers: {
      'Content-Type': 'text/calendar; charset=utf-8',
      'Content-Disposition': `inline; filename="broncos-${who}-${SEASON}.ics"`,
      'Cache-Control': 'no-cache',
    },
  });
}
