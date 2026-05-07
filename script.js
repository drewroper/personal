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
  const root         = document.documentElement;
  const switchBtn    = document.getElementById('js-fontswitch');
  const nameEl       = document.getElementById('js-fontname');
  const nameElFoot   = document.getElementById('js-fontname-foot');
  const linkEl       = document.getElementById('js-fontlink');
  const positionEl   = document.getElementById('js-fontposition');
  const loaded       = new Set();

  const slugOf = (font) => (font.g || '').split(':')[0] || encodeURIComponent(font.name);
  const specimenUrl = (font) => `https://fonts.google.com/specimen/${slugOf(font)}`;

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
    if (linkEl)     linkEl.href            = specimenUrl(font);
    if (positionEl) positionEl.textContent = `${index + 1} of ${FONTS.length}`;
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
    const f = FONTS[current];
    if (nameEl)     nameEl.textContent     = f.name;
    if (nameElFoot) nameElFoot.textContent = f.name;
    if (linkEl)     linkEl.href            = specimenUrl(f);
    if (positionEl) positionEl.textContent = `${current + 1} of ${FONTS.length}`;
    if (switchBtn)  switchBtn.setAttribute('data-font-id', f.id);
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
     2. DENVER CLOCK
     Always Mountain Time, regardless of the visitor's location.
     A subtle tell that Drew is based in Denver. Click toggles a
     reveal that says so.
     ============================================================ */
  const clock     = document.getElementById('js-clock');
  const clockTime = document.getElementById('js-clock-time');
  if (clock && clockTime) {
    const tick = () => {
      const now = new Date();
      const time = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'America/Denver'
      });
      // Resolve MST or MDT depending on DST.
      const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Denver',
        timeZoneName: 'short'
      }).formatToParts(now);
      const tz = (parts.find(p => p.type === 'timeZoneName') || {}).value || 'MT';
      clockTime.textContent = `${time} ${tz}`;
    };
    tick();
    setInterval(tick, 30 * 1000);

    // Click toggles a "Denver" reveal for ~3 seconds.
    let revealTimer = 0;
    clock.addEventListener('click', () => {
      clock.classList.add('is-locating');
      clearTimeout(revealTimer);
      revealTimer = setTimeout(() => clock.classList.remove('is-locating'), 3000);
    });
  }

  /* ============================================================
     3. FOOTER YEAR + LAST TOUCHED
     ============================================================ */
  const year = document.getElementById('js-year');
  if (year) year.textContent = String(new Date().getFullYear());

  const lastMod = document.getElementById('js-lastmod');
  if (lastMod) {
    const d = new Date(document.lastModified || Date.now());
    const fmt = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
    const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    lastMod.textContent = `${fmt} · ${time}`;
  }

  /* ============================================================
     3b. EDITABLE HEADLINE — easter egg
     The hero h1 is contenteditable; visitors can type whatever
     they want. Doesn't persist across reloads.
     ============================================================ */
  const headline = document.getElementById('hero-name');
  if (headline) {
    let firstFocus = true;
    headline.addEventListener('focus', () => {
      // Drop any existing selection and put caret at the end on first focus
      // so typing extends rather than replaces. Holds for visitors who just
      // want to add a flourish.
      if (firstFocus) {
        const range = document.createRange();
        range.selectNodeContents(headline);
        range.collapse(false); // to end
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        firstFocus = false;
      }
    });
    headline.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') headline.blur();
    });
    // Paste as plain text only — keeps the layout intact if someone
    // pastes a screenshot or rich content from a doc.
    headline.addEventListener('paste', (e) => {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData('text/plain');
      document.execCommand('insertText', false, text);
    });
  }

  /* ============================================================
     4. WORK — image pool, desktop cycling grid, mobile slideshow
     -----------------------------------------------------------
     Single source of truth for the ~50 image pool. Replace the
     URLs below with paths into /assets/work/ when you have your
     real photos. For now we render Lorem Picsum placeholders in
     grayscale so the layout reads cohesively on the dark site.
     ============================================================ */
  const WORK_IMAGES = Array.from({ length: 50 }, (_, i) => {
    // Vary heights to give the masonry a natural rhythm.
    const heights = [600, 720, 800, 900, 1000, 720, 800];
    const h = heights[i % heights.length];
    return `https://picsum.photos/seed/dr-work-${i + 1}/720/${h}?grayscale`;
  });
  // Vary aspect ratios for the desktop grid cells (independent of image height
  // since object-fit: cover will crop). This gives the masonry visual variety.
  const CELL_RATIOS = [
    '4 / 5', '3 / 4', '1 / 1', '4 / 5', '3 / 4', '5 / 4',
    '4 / 5', '1 / 1', '3 / 4', '4 / 5', '5 / 7', '3 / 4',
    '4 / 5', '1 / 1', '3 / 4', '4 / 5'
  ];
  const VISIBLE_CELLS = 12;

  function shuffleIndices(n, exclude = new Set()) {
    const arr = [];
    for (let i = 0; i < n; i++) if (!exclude.has(i)) arr.push(i);
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function initWorkGrid() {
    const grid = document.getElementById('js-work-grid');
    if (!grid) return;

    // Pick the initial visible set + remember which images are "in pool".
    const visible = shuffleIndices(WORK_IMAGES.length).slice(0, VISIBLE_CELLS);
    const inPool  = new Set(visible);

    grid.innerHTML = '';
    visible.forEach((imgIdx, cellIdx) => {
      const cell = document.createElement('div');
      cell.className = 'work-cell';
      cell.style.setProperty('--ratio', CELL_RATIOS[cellIdx % CELL_RATIOS.length]);
      cell.dataset.imgIdx = String(imgIdx);

      const img = new Image();
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.src = WORK_IMAGES[imgIdx];
      cell.appendChild(img);

      grid.appendChild(cell);
    });

    // Cycle: every ~5s, swap one cell to a non-visible image.
    const FADE_MS = 550;
    const swapOne = () => {
      if (document.hidden) return;
      const cells = grid.querySelectorAll('.work-cell');
      if (!cells.length) return;
      const cell = cells[Math.floor(Math.random() * cells.length)];
      const oldIdx = parseInt(cell.dataset.imgIdx, 10);
      // Pick a new image not currently visible.
      const candidates = shuffleIndices(WORK_IMAGES.length, inPool);
      if (!candidates.length) return;
      const newIdx = candidates[0];
      inPool.delete(oldIdx);
      inPool.add(newIdx);

      // Preload, then swap.
      const next = new Image();
      next.onload = () => {
        cell.classList.add('is-fading');
        setTimeout(() => {
          const img = cell.querySelector('img');
          if (img) img.src = next.src;
          cell.dataset.imgIdx = String(newIdx);
          requestAnimationFrame(() => cell.classList.remove('is-fading'));
        }, FADE_MS);
      };
      next.onerror = () => {}; // skip silently
      next.src = WORK_IMAGES[newIdx];
    };
    setInterval(swapOne, 5000);
  }

  function initWorkSlides() {
    const root  = document.getElementById('js-work-slides');
    const stage = document.getElementById('js-slide-stage');
    const dots  = document.getElementById('js-slide-dots');
    if (!root || !stage || !dots) return;

    // Render two img elements that we cross-fade between.
    const a = new Image(); a.alt = ''; a.className = 'is-active';
    const b = new Image(); b.alt = '';
    a.loading = 'eager'; b.loading = 'eager';
    a.decoding = 'async'; b.decoding = 'async';
    stage.append(a, b);

    // Render dots.
    dots.innerHTML = '';
    WORK_IMAGES.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'dot';
      dot.setAttribute('role', 'tab');
      dot.setAttribute('aria-label', `Slide ${i + 1} of ${WORK_IMAGES.length}`);
      dot.addEventListener('click', () => goTo(i, true));
      dots.appendChild(dot);
    });

    let idx = 0;
    let front = a, back = b;

    function goTo(next, fromUser) {
      idx = ((next % WORK_IMAGES.length) + WORK_IMAGES.length) % WORK_IMAGES.length;
      back.onload = () => {
        front.classList.remove('is-active');
        back.classList.add('is-active');
        [front, back] = [back, front]; // swap roles
      };
      back.src = WORK_IMAGES[idx];
      Array.from(dots.children).forEach((d, i) => d.classList.toggle('is-active', i === idx));
      if (fromUser) restartTimer();
    }

    // Prime the first slide.
    a.src = WORK_IMAGES[0];
    Array.from(dots.children)[0].classList.add('is-active');

    let timer = 0;
    function restartTimer() {
      clearInterval(timer);
      timer = setInterval(() => {
        if (document.hidden) return;
        goTo(idx + 1, false);
      }, 4500);
    }
    restartTimer();
  }

  // Bootstrap based on viewport — keep both initialised so a resize works.
  // The CSS handles which one shows.
  initWorkGrid();
  initWorkSlides();

  /* ============================================================
     5. CONSOLE SIGNATURE
     ============================================================ */
  if (typeof console !== 'undefined' && console.log) {
    const css = 'font-family: serif; font-size: 14px; font-style: italic; color: #c8a978; padding: 4px 0';
    console.log('%cHello, curious one. — Drew', css);
  }
})();
