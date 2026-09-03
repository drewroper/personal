// GET  /api/state[?since=N]  -> { version, state, calKey }  (or { version, unchanged: true })
// POST /api/state { patch }  -> { version, state }
import { readState, writePatch, validatePatch } from '../_lib/state.js';
import { calKey } from '../_lib/auth.js';

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });

export async function onRequestGet({ request, env }) {
  const since = Number(new URL(request.url).searchParams.get('since') || 0);
  try {
    const { version, state } = await readState(env.DB);
    if (since && since === version) return json({ version, unchanged: true });
    return json({ version, state, calKey: await calKey(env.FAMILY_PASSWORD) });
  } catch (err) {
    return json({ error: `database: ${err.message}` }, 500);
  }
}

export async function onRequestPost({ request, env }) {
  let body;
  try {
    const text = await request.text();
    if (text.length > 50_000) return json({ error: 'patch too large' }, 413);
    body = JSON.parse(text);
  } catch {
    return json({ error: 'bad json' }, 400);
  }
  const problem = validatePatch(body && body.patch);
  if (problem) return json({ error: problem }, 400);
  try {
    const { version, state } = await writePatch(env.DB, body.patch);
    return json({ version, state });
  } catch (err) {
    return json({ error: `database: ${err.message}` }, 500);
  }
}
