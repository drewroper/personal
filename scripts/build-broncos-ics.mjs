// Regenerates broncos/broncos-home-2026.ics from broncos/schedule.js.
// Run after editing the schedule:  node scripts/build-broncos-ics.mjs
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { GAMES, SEASON } from '../broncos/schedule.js';
import { buildIcs, gameDescription } from '../broncos/ics.js';

const dir = dirname(fileURLToPath(import.meta.url));
const out = join(dir, '..', 'broncos', `broncos-home-${SEASON}.ics`);
// Fixed stamp so the file only changes when the schedule does.
const stamp = new Date('2026-09-02T00:00:00Z');
const ics = buildIcs(
  GAMES,
  (g) => ({ summary: `Broncos vs ${g.short}`, description: `${gameDescription(g)}\nWho has tickets: https://drewroper.com/broncos` }),
  { name: `Broncos home games ${SEASON}`, stamp },
);
writeFileSync(out, ics);
console.log(`wrote ${out} (${GAMES.length} games)`);
