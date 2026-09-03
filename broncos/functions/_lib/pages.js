// The two server-rendered pages: login and "not set up yet".
const shell = (title, body) => `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title><meta name="robots" content="noindex">
<style>
  :root{--bg:#0c0c0d;--raised:#131315;--rule:#262628;--text:#f4f1ec;--muted:#8c8a86;--faint:#56544f;--accent:#fb4f14}
  *{box-sizing:border-box}html,body{margin:0;background:var(--bg)}
  body{color:var(--muted);font:15px/1.5 Geist,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;min-height:100vh;display:grid;place-items:center;padding:24px}
  .card{width:100%;max-width:380px}
  .eyebrow{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
  h1{color:var(--text);font-size:34px;line-height:1;letter-spacing:-.02em;margin:8px 0 10px}
  p{margin:0 0 20px}
  input{width:100%;font:inherit;font-size:17px;color:var(--text);background:var(--raised);border:1px solid var(--rule);border-radius:10px;padding:14px 16px;margin-bottom:10px}
  input:focus{outline:2px solid var(--accent);outline-offset:1px}
  button{width:100%;font:inherit;font-weight:500;font-size:16px;color:var(--bg);background:var(--accent);border:0;border-radius:10px;padding:14px;cursor:pointer}
  button:hover{background:#ff6a36}
  .err{color:#ffb000;margin:0 0 12px}
  code{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--text)}
  ol{padding-left:20px}li{margin-bottom:8px}
</style></head><body><main class="card">${body}</main></body></html>`;

export const loginPage = ({ error = false } = {}) => shell('Broncos tickets', `
  <div class="eyebrow">2026 season</div>
  <h1>Broncos tickets</h1>
  <p>Family only. Enter the password once and this phone will remember it.</p>
  ${error ? '<p class="err">That’s not it. Try again.</p>' : ''}
  <form method="post" action="/login">
    <input type="password" name="password" placeholder="Family password" autocomplete="current-password" autofocus required>
    <button type="submit">Let me in</button>
  </form>`);

export const setupPage = (missing) => shell('Broncos tickets — setup', `
  <div class="eyebrow">Almost there</div>
  <h1>Not set up yet</h1>
  <p>The site is deployed but is missing: <code>${missing.join('</code>, <code>')}</code>.</p>
  <ol>
    <li>In Cloudflare, open this Pages project → <b>Settings</b>.</li>
    <li>Under <b>Variables and Secrets</b>, add <code>FAMILY_PASSWORD</code> (as a Secret).</li>
    <li>Under <b>Bindings</b>, add a <b>D1 database</b> with variable name <code>DB</code>.</li>
    <li>Redeploy (Deployments → ⋯ → Retry deployment), then reload this page.</li>
  </ol>
  <p>Full walkthrough in the README.</p>`);
