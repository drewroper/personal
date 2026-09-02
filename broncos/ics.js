// Calendar helpers shared by the app (browser) and scripts/build-broncos-ics.mjs (node).
import { SEASON, VENUE, VENUE_ADDRESS } from './schedule.js';

export const TZ = 'America/Denver';
export const GAME_HOURS = 3.5;

export function gameDate(g) { return g.kickoff ? new Date(g.kickoff) : new Date(`${g.date}T12:00:00-07:00`); }
export function gameEnd(g) { return new Date(gameDate(g).getTime() + GAME_HOURS * 3600 * 1000); }

const pad = (n) => String(n).padStart(2, '0');
export function icsUtc(d) {
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`;
}
export function icsDate(str) { return str.replace(/-/g, ''); }
export function nextDay(str) { const d = new Date(`${str}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10); }
export function icsText(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');
}
// RFC 5545 folds lines at 75 octets.
function fold(line) {
  const out = [];
  let s = line;
  while (s.length > 74) { out.push(s.slice(0, 74)); s = ' ' + s.slice(74); }
  out.push(s);
  return out;
}

export function icsEvent(g, summary, description, stamp = new Date()) {
  const lines = ['BEGIN:VEVENT', `UID:broncos-${SEASON}-${g.id}@drewroper.com`, `DTSTAMP:${icsUtc(stamp)}`];
  if (g.kickoff) lines.push(`DTSTART:${icsUtc(gameDate(g))}`, `DTEND:${icsUtc(gameEnd(g))}`);
  else lines.push(`DTSTART;VALUE=DATE:${icsDate(g.date)}`, `DTEND;VALUE=DATE:${icsDate(nextDay(g.date))}`);
  lines.push(`SUMMARY:${icsText(summary)}`, `LOCATION:${icsText(`${VENUE}, ${VENUE_ADDRESS}`)}`, `DESCRIPTION:${icsText(description)}`, 'END:VEVENT');
  return lines;
}

export function buildIcs(games, labelFor, { name = `Broncos ${SEASON}`, stamp = new Date() } = {}) {
  const out = ['BEGIN:VCALENDAR', 'VERSION:2.0', `PRODID:-//drewroper.com//Broncos ${SEASON}//EN`, 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', `X-WR-CALNAME:${icsText(name)}`, `X-WR-TIMEZONE:${TZ}`];
  for (const g of games) {
    const { summary, description } = labelFor(g);
    out.push(...icsEvent(g, summary, description, stamp));
  }
  out.push('END:VCALENDAR');
  return out.flatMap(fold).join('\r\n') + '\r\n';
}

export function gameDescription(g) { return `Week ${g.week} · ${g.tv}${g.tag ? ` · ${g.tag}` : ''}`; }
