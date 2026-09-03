// Password gate helpers. There is one family password (the FAMILY_PASSWORD
// environment variable). The auth cookie and the calendar key are both
// derived from it with HMAC, so changing the password logs everyone out and
// invalidates old calendar links — no extra secrets to manage.

export const COOKIE = 'broncos_auth';
const enc = new TextEncoder();

async function hmacHex(key, message) {
  const k = await crypto.subtle.importKey('raw', enc.encode(key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', k, enc.encode(message));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export const cookieValue = (password) => hmacHex(password, 'broncos:cookie:v1');
export const calKey = (password) => hmacHex(password, 'broncos:cal:v1').then((h) => h.slice(0, 32));

// Constant-time string compare.
export function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function passwordMatches(given, password) {
  // Compare HMACs rather than raw strings so lengths never leak.
  return safeEqual(await hmacHex(password, `check:${given}`), await hmacHex(password, `check:${password}`));
}

export function readCookie(request, name) {
  const header = request.headers.get('Cookie') || '';
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return v.join('=');
  }
  return null;
}

export async function isAuthed(request, env) {
  const got = readCookie(request, COOKIE);
  if (!got) return false;
  return safeEqual(got, await cookieValue(env.FAMILY_PASSWORD));
}

export const setCookie = (value) => `${COOKIE}=${value}; Path=/; Max-Age=31536000; HttpOnly; Secure; SameSite=Lax`;
export const clearCookie = () => `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
