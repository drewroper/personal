// Season state lives in one D1 row as JSON, with a version number for
// optimistic concurrency. Writes are "patches": a map of dotted paths to
// values, where null means delete. The client speaks the same language.
import { SEED } from './seed.js';

export const SEASON_ID = 'season-2026';
const TOP = new Set(['people', 'claims', 'unavailable', 'notes']);
const SEG = /^[A-Za-z0-9_]{1,40}$/;

let ready = null;
function ensureTable(db) {
  if (!ready) ready = db.prepare(
    'CREATE TABLE IF NOT EXISTS seasons (id TEXT PRIMARY KEY, version INTEGER NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL)'
  ).run().catch((e) => { ready = null; throw e; });
  return ready;
}

export function normalize(data) {
  const s = data && typeof data === 'object' ? data : {};
  return { people: s.people || {}, claims: s.claims || {}, unavailable: s.unavailable || {}, notes: s.notes || {} };
}

export async function readState(db) {
  await ensureTable(db);
  const row = await db.prepare('SELECT version, data FROM seasons WHERE id = ?').bind(SEASON_ID).first();
  if (row) return { version: row.version, state: normalize(JSON.parse(row.data)) };
  const seed = structuredClone(SEED);
  await db.prepare('INSERT OR IGNORE INTO seasons (id, version, data, updated_at) VALUES (?, 1, ?, ?)')
    .bind(SEASON_ID, JSON.stringify(seed), new Date().toISOString()).run();
  const again = await db.prepare('SELECT version, data FROM seasons WHERE id = ?').bind(SEASON_ID).first();
  return { version: again.version, state: normalize(JSON.parse(again.data)) };
}

function validValue(v, depth) {
  if (v === null) return true;
  if (typeof v === 'boolean' || typeof v === 'number') return true;
  if (typeof v === 'string') return v.length <= 300;
  if (typeof v === 'object' && depth === 2) {
    // a person record
    const keys = Object.keys(v);
    return keys.length <= 6 && keys.every((k) => SEG.test(k) && validValue(v[k], 3));
  }
  return false;
}

export function validatePatch(patch) {
  if (!patch || typeof patch !== 'object' || Array.isArray(patch)) return 'patch must be an object';
  const entries = Object.entries(patch);
  if (!entries.length || entries.length > 100) return 'patch is empty or too large';
  for (const [path, value] of entries) {
    const keys = path.split('.');
    if (keys.length < 2 || keys.length > 4) return `bad path: ${path}`;
    if (!TOP.has(keys[0])) return `bad path: ${path}`;
    if (!keys.slice(1).every((k) => SEG.test(k))) return `bad path: ${path}`;
    if (!validValue(value, keys.length)) return `bad value at ${path}`;
  }
  return null;
}

export function applyPatch(obj, patch) {
  for (const [path, value] of Object.entries(patch)) {
    const keys = path.split('.');
    let cur = obj;
    for (let i = 0; i < keys.length - 1; i++) {
      if (typeof cur[keys[i]] !== 'object' || cur[keys[i]] === null) cur[keys[i]] = {};
      cur = cur[keys[i]];
    }
    const last = keys[keys.length - 1];
    if (value === null) delete cur[last];
    else cur[last] = value;
  }
  return obj;
}

export async function writePatch(db, patch) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const { version, state } = await readState(db);
    const next = applyPatch(state, patch);
    const res = await db.prepare('UPDATE seasons SET version = ?, data = ?, updated_at = ? WHERE id = ? AND version = ?')
      .bind(version + 1, JSON.stringify(next), new Date().toISOString(), SEASON_ID, version).run();
    if (res.meta && res.meta.changes === 1) return { version: version + 1, state: next };
  }
  throw new Error('too many concurrent edits, try again');
}
