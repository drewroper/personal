/* drewroper.com — landing page interactions
   - Font cycling button (font registry lives in <head> for early load)
   - Live clock in topbar
   - Footer year stamp
   - Z-space parallax (mouse on desktop, scroll on touch)
   Vanilla JS. Respects prefers-reduced-motion. */

(() => {

  /* ============================================================
     1. FONT SWITCHER
     The picker in <head> already chose & loaded font #N for this
     load and stashed it on window.__FONT_INDEX__. Here we wire up
     the topbar button to cycle to the next entry.
     ============================================================ */
  const FONTS = window.__FONTS__ || [];
  const root        = document.documentElement;
  const switchBtn   = document.getElementById('js-fontswitch');
  const nameEl      = document.getElementById('js-fontname');
  const nameElFoot  = document.getElementById('js-fontname-foot');
  const loaded      = new Set();

  // Mark the head-injected font as already loaded so we don't double-add.
  document.querySelectorAll('link[data-font-id]').forEach(l => loaded.add(l.dataset.fontId));

  function ensureLoaded(font) {
    if (loaded.has(font.id) || !font.g) return;
    const link = document.createElement('link');
    link.rel  = 'stylesheet';
    link.href = `https://fonts.googleapis.com/css2?family=${font.g}&display=swap`;
    link.dataset.fontId = font.id;
    document.head.appendChild(link);
    loaded.add(font.id);
  }

  function applyFont(index, opts = {}) {
    const font = FONTS[index];
    if (!font) return;
    ensureLoaded(font);

    root.style.setProperty('--font-display', font.stack);
    if (nameEl)     nameEl.textContent     = font.name;
    if (nameElFoot) nameElFoot.textContent = font.name;
    if (switchBtn)  switchBtn.setAttribute('data-font-id', font.id);

    try { localStorage.setItem('dr.lastIndex', String(index)); } catch (_) {}

    if (opts.animate && switchBtn) {
      switchBtn.classList.remove('is-spinning');
      void switchBtn.offsetWidth; // restart animation
      switchBtn.classList.add('is-spinning');
    }
  }

  let current = (typeof window.__FONT_INDEX__ === 'number') ? window.__FONT_INDEX__ : 0;
  // Reflect the head-picked font in the UI without re-loading anything.
  if (FONTS[current]) {
    if (nameEl)     nameEl.textContent     = FONTS[current].name;
    if (nameElFoot) nameElFoot.textContent = FONTS[current].name;
    if (switchBtn)  switchBtn.setAttribute('data-font-id', FONTS[current].id);
  }

  if (switchBtn && FONTS.length) {
    switchBtn.addEventListener('click', () => {
      current = (current + 1) % FONTS.length;
      applyFont(current, { animate: true });
    });
    // Keyboard: F → next, Shift+F → previous (when not typing in a field)
    document.addEventListener('keydown', (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        current = (current + (e.shiftKey ? FONTS.length - 1 : 1)) % FONTS.length;
        applyFont(current, { animate: true });
      }
    });
  }

  /* ============================================================
     2. LIVE CLOCK
     ============================================================ */
  const clock = document.getElementById('js-clock');
  if (clock) {
    const tick = () => {
      const now = new Date();
      const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
      const tz   = now.toLocaleTimeString('en-US', { timeZoneName: 'short' }).split(' ').pop();
      clock.textContent = `${time} ${tz}`;
    };
    tick();
    setInterval(tick, 30 * 1000);
  }

  /* ============================================================
     3. FOOTER YEAR
     ============================================================ */
  const year = document.getElementById('js-year');
  if (year) year.textContent = String(new Date().getFullYear());

  /* ============================================================
     4. Z-SPACE PARALLAX
     ============================================================ */
  const stage  = document.getElementById('js-zstage');
  const camera = document.getElementById('js-zcamera');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine   = window.matchMedia('(pointer: fine)').matches;

  if (stage && camera && !reduce) {
    let raf = 0;
    let tx = 0, ty = 0; // target
    let cx = 0, cy = 0; // current

    const requestLoop = () => { if (!raf) raf = requestAnimationFrame(loop); };

    const loop = () => {
      cx += (tx - cx) * 0.08;
      cy += (ty - cy) * 0.08;
      stage.style.setProperty('--mx', cx.toFixed(3));
      stage.style.setProperty('--my', cy.toFixed(3));
      camera.style.transform = `rotateX(${6 - cy * 3}deg) rotateY(${cx * 4}deg)`;
      if (Math.abs(tx - cx) > 0.001 || Math.abs(ty - cy) > 0.001) {
        raf = requestAnimationFrame(loop);
      } else {
        raf = 0;
      }
    };

    if (fine) {
      stage.addEventListener('mousemove', (e) => {
        const rect = stage.getBoundingClientRect();
        tx = ((e.clientX - rect.left) / rect.width  - 0.5) * 2;
        ty = ((e.clientY - rect.top)  / rect.height - 0.5) * 2;
        requestLoop();
      }, { passive: true });
      stage.addEventListener('mouseleave', () => { tx = 0; ty = 0; requestLoop(); }, { passive: true });
    } else {
      // Touch / mobile: subtle scroll-driven parallax
      const onScroll = () => {
        const rect = stage.getBoundingClientRect();
        const vh = window.innerHeight || 1;
        const center = rect.top + rect.height / 2;
        const t = Math.max(-1, Math.min(1, (center - vh / 2) / (vh / 2)));
        ty = t * 0.6;
        requestLoop();
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }
  }

  /* ============================================================
     5. CONSOLE SIGNATURE
     ============================================================ */
  if (typeof console !== 'undefined' && console.log) {
    const css = 'font-family: serif; font-size: 14px; font-style: italic; color: #c8a978; padding: 4px 0';
    console.log('%cHello, curious one. — Drew', css);
  }
})();
