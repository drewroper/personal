// 2026 Denver Broncos HOME schedule — Empower Field at Mile High.
// Verified against denverbroncos.com, nfl.com and cbssports.com on 2026-09-02.
//
// Kickoffs are ISO strings with the Mountain offset baked in (-06:00 before
// Nov 1, -07:00 after). The app always displays them in America/Denver, so
// family members in other time zones see the real local kickoff.
//
// To fix a flexed game: edit `kickoff` here and push. To add a playoff game
// later, append an entry with a new `id` — claims/availability key on `id`,
// so keep existing ids stable.

export const SEASON = 2026;
export const VENUE = 'Empower Field at Mile High';
export const VENUE_ADDRESS = '1701 Bryant St, Denver, CO 80204';
export const TEAM = 'Denver Broncos';

export const GAMES = [
  { id: 'wk02', week: 2,  opponent: 'Jacksonville Jaguars', short: 'Jaguars',  kickoff: '2026-09-20T14:05:00-06:00', tv: 'CBS' },
  { id: 'wk03', week: 3,  opponent: 'Los Angeles Rams',     short: 'Rams',     kickoff: '2026-09-27T18:20:00-06:00', tv: 'NBC',         tag: 'Sunday Night Football' },
  { id: 'wk06', week: 6,  opponent: 'Seattle Seahawks',     short: 'Seahawks', kickoff: '2026-10-15T18:15:00-06:00', tv: 'Prime Video', tag: 'Thursday Night Football' },
  { id: 'wk08', week: 8,  opponent: 'Kansas City Chiefs',   short: 'Chiefs',   kickoff: '2026-11-01T14:25:00-07:00', tv: 'CBS' },
  { id: 'wk11', week: 11, opponent: 'Las Vegas Raiders',    short: 'Raiders',  kickoff: '2026-11-22T14:25:00-07:00', tv: 'CBS' },
  { id: 'wk13', week: 13, opponent: 'Miami Dolphins',       short: 'Dolphins', kickoff: '2026-12-06T14:05:00-07:00', tv: 'FOX' },
  { id: 'wk16', week: 16, opponent: 'Buffalo Bills',        short: 'Bills',    kickoff: '2026-12-25T14:30:00-07:00', tv: 'Netflix',     tag: 'Christmas Day' },
  // Week 18 date is set; the league announces the kickoff time late in the season.
  { id: 'wk18', week: 18, opponent: 'Los Angeles Chargers', short: 'Chargers', kickoff: null, date: '2027-01-10',   tv: 'TBA',         tag: 'Kickoff TBA' },
];
