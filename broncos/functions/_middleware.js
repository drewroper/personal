// Runs before every request. One family password gates the whole site.
//   POST /login   check the password, set a year-long cookie
//   GET  /logout  clear it
//   /cal/<key>/…  calendar feeds, allowed through with the key instead of a
//                 cookie (calendar apps can't log in)
// Everything else needs the cookie or gets the login page.
import { isAuthed, passwordMatches, cookieValue, calKey, safeEqual, setCookie, clearCookie } from './_lib/auth.js';
import { loginPage, setupPage } from './_lib/pages.js';

const html = (body, status = 200, headers = {}) =>
  new Response(body, { status, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', ...headers } });

export async function onRequest({ request, env, next }) {
  const url = new URL(request.url);
  const missing = [];
  if (!env.FAMILY_PASSWORD) missing.push('FAMILY_PASSWORD');
  if (!env.DB) missing.push('DB');
  if (missing.length) return html(setupPage(missing), 503);

  if (url.pathname === '/login' && request.method === 'POST') {
    const form = await request.formData().catch(() => null);
    const given = String(form?.get('password') || '');
    if (given && await passwordMatches(given, env.FAMILY_PASSWORD)) {
      return new Response(null, { status: 303, headers: { Location: '/', 'Set-Cookie': setCookie(await cookieValue(env.FAMILY_PASSWORD)) } });
    }
    return html(loginPage({ error: true }), 401);
  }
  if (url.pathname === '/logout') {
    return new Response(null, { status: 303, headers: { Location: '/', 'Set-Cookie': clearCookie() } });
  }

  if (url.pathname.startsWith('/cal/')) {
    const key = url.pathname.split('/')[2] || '';
    if (safeEqual(key, await calKey(env.FAMILY_PASSWORD))) return next();
    return new Response('Not found', { status: 404 });
  }

  if (await isAuthed(request, env)) {
    const res = await next();
    // Never let a browser or proxy cache the gated pages.
    const out = new Response(res.body, res);
    out.headers.set('Cache-Control', 'no-store');
    return out;
  }
  if (url.pathname.startsWith('/api/')) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
  }
  return html(loginPage(), 401);
}
