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
    root.style.setProperty('--h1-weight', String(font.wght || 400));
    root.style.setProperty('--h1-scale',  String(font.scale || 1));
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
     A subtle tell that Drew is based in Denver. Tap toggles the
     time text out for the location label for ~3 seconds.
     ============================================================ */
  const clock     = document.getElementById('js-clock');
  const clockText = document.getElementById('js-clock-time');
  if (clock && clockText) {
    let locating = false;
    const formatTime = () => {
      const now = new Date();
      const time = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'America/Denver'
      });
      const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Denver',
        timeZoneName: 'short'
      }).formatToParts(now);
      const tz = (parts.find(p => p.type === 'timeZoneName') || {}).value || 'MT';
      return `${time} ${tz}`;
    };
    const paint = () => {
      clockText.textContent = locating
        ? (clock.dataset.loc || 'Denver, CO · 5,280 ft')
        : formatTime();
    };
    paint();
    setInterval(paint, 30 * 1000);

    let revealTimer = 0;
    clock.addEventListener('click', () => {
      locating = true;
      clock.classList.add('is-locating');
      paint();
      clearTimeout(revealTimer);
      revealTimer = setTimeout(() => {
        locating = false;
        clock.classList.remove('is-locating');
        paint();
      }, 3000);
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
     3a. LIVE PERFORMANCE STATS
     Reads the Performance API after the page has fully loaded and
     reports the real numbers — load time and resource count — back
     into the Colophon. Honest, no estimation.
     ============================================================ */
  const fmtMs = (ms) => ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
  const reportPerf = () => {
    const loadEl = document.getElementById('js-loadtime');
    const resEl  = document.getElementById('js-resources');
    try {
      const nav = performance.getEntriesByType('navigation')[0];
      if (loadEl && nav) {
        const dur = nav.loadEventEnd > 0 ? nav.loadEventEnd : nav.domContentLoadedEventEnd;
        loadEl.textContent = fmtMs(dur);
      }
      if (resEl) {
        const count = 1 /* the document itself */ +
                      performance.getEntriesByType('resource').length;
        resEl.textContent = String(count);
      }
    } catch (_) { /* Performance API not available — leave defaults */ }
  };
  if (document.readyState === 'complete') reportPerf();
  else window.addEventListener('load', () => setTimeout(reportPerf, 0));

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
     Pool of project covers pulled from Drew's Behance profile.
     Swap to local /assets/work/* paths once images are mirrored
     into the repo. object-fit: cover handles aspect cropping.
     ============================================================ */
  const WORK_IMAGES = [
    'https://mir-s3-cdn-cf.behance.net/projects/404/64ae8d110754963.Y3JvcCwyMTczLDE3MDAsMTkzLDA.png',  // Element
    'https://mir-s3-cdn-cf.behance.net/projects/404/37dab197905583.Y3JvcCwyMjc4LDE3ODIsNTMwLDM5.jpg',  // Increment Issue 13 — Frontend
    'https://mir-s3-cdn-cf.behance.net/projects/404/f1a7dd103213279.Y3JvcCwxMzgwLDEwODAsMjcwLDA.png',  // ōLiv
    'https://mir-s3-cdn-cf.behance.net/projects/404/8bf4d1103228781.Y3JvcCwxMzgwLDEwODAsMjcwLDA.jpg',  // Clyde
    'https://mir-s3-cdn-cf.behance.net/projects/404/572758103290303.Y3JvcCwxMzgwLDEwODAsMjcwLDA.jpg',  // Prost!Cards
    'https://mir-s3-cdn-cf.behance.net/projects/404/b36aee13619493.6172d816aed10.jpg',                  // TYPEFIGHT
    'https://mir-s3-cdn-cf.behance.net/projects/404/0c367119796977.Y3JvcCwxMzgwLDEwODAsMjcwLDA.png',  // Scooters Sandwich Shop
    'https://mir-s3-cdn-cf.behance.net/projects/404/684f27103167265.Y3JvcCwxMzgwLDEwODAsMjcwLDA.jpg',  // East Hampton Sandwich Co.
    'https://mir-s3-cdn-cf.behance.net/projects/404/f3085d48534019.Y3JvcCwxMzgwLDEwODAsMjcwLDA.jpg',  // trunkclub.com
    'https://mir-s3-cdn-cf.behance.net/projects/404/51a76e21733267.Y3JvcCw4NzksNjg4LDYwLDA.jpg',      // Missouri License Plate
    'https://mir-s3-cdn-cf.behance.net/projects/404/72bba813608983.5f5aeef869291.jpg'                   // MyBread
  ];
  const VISIBLE_CELLS = 8;
  // Each cell's aspect ratio is computed from the loaded image so
  // landscape work stays landscape and portrait stays portrait.
  const setCellRatio = (cell, img) => {
    if (!img.naturalWidth || !img.naturalHeight) return;
    cell.style.setProperty('--ratio', `${img.naturalWidth} / ${img.naturalHeight}`);
  };

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
    visible.forEach((imgIdx) => {
      const cell = document.createElement('div');
      cell.className = 'work-cell';
      cell.dataset.imgIdx = String(imgIdx);

      const img = new Image();
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.onload = () => setCellRatio(cell, img);
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

      // Preload, then swap. Cell aspect ratio is updated to match the
      // new image so landscapes don't get cropped into portraits.
      const next = new Image();
      next.onload = () => {
        cell.classList.add('is-fading');
        setTimeout(() => {
          const img = cell.querySelector('img');
          if (img) img.src = next.src;
          cell.dataset.imgIdx = String(newIdx);
          setCellRatio(cell, next);
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

    /* Touch + click navigation -----------------------------------
       - horizontal swipe ≥ 40px advances (left = next, right = prev)
       - a tap (or click on desktop) advances to the next slide */
    const SWIPE_THRESHOLD = 40;
    let startX = 0, startY = 0, startTime = 0, swiping = false;

    stage.addEventListener('touchstart', (e) => {
      const t = e.changedTouches[0];
      startX = t.clientX;
      startY = t.clientY;
      startTime = Date.now();
      swiping = true;
    }, { passive: true });

    stage.addEventListener('touchend', (e) => {
      if (!swiping) return;
      swiping = false;
      const t = e.changedTouches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      const dt = Date.now() - startTime;

      // If movement is mostly vertical, let the page scroll instead.
      if (Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 20) return;

      if (Math.abs(dx) >= SWIPE_THRESHOLD) {
        goTo(dx < 0 ? idx + 1 : idx - 1, true);
      } else if (Math.abs(dx) < 8 && dt < 400) {
        goTo(idx + 1, true);
      }
    }, { passive: true });

    // Desktop / non-touch click: also advance.
    stage.addEventListener('click', () => goTo(idx + 1, true));
    stage.style.cursor = 'pointer';
  }

  // Bootstrap based on viewport — keep both initialised so a resize works.
  // The CSS handles which one shows.
  initWorkGrid();
  initWorkSlides();

  /* ============================================================
     5. DITHERED PORTRAIT — ambient animation
     -----------------------------------------------------------
     Loads /assets/portrait.jpg, samples it into a low-res Bayer
     8x8 ordered-dither, and animates by slowly shifting the
     dither matrix offset + threshold. The canvas is small and
     scaled with image-rendering:pixelated for chunky grain.
     If the image is missing, paints a placeholder gradient.
     ============================================================ */
  (function initDitherPortrait() {
    const canvas = document.getElementById('js-portrait');
    if (!canvas) return;
    // Desktop gets ~10% more pixel density than mobile. Same image,
    // tighter dots; the chunky aesthetic is preserved.
    const isDesktop = window.matchMedia('(min-width: 760px)').matches;
    if (isDesktop) {
      canvas.width  = 132;   // 120 * 1.10
      canvas.height = 88;    //  80 * 1.10
    }
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const W = canvas.width;
    const H = canvas.height;

    // Bayer 8x8, scaled to 0..252 to match 0..255 grayscale comparison.
    const BAYER = [
       0, 32,  8, 40,  2, 34, 10, 42,
      48, 16, 56, 24, 50, 18, 58, 26,
      12, 44,  4, 36, 14, 46,  6, 38,
      60, 28, 52, 20, 62, 30, 54, 22,
       3, 35, 11, 43,  1, 33,  9, 41,
      51, 19, 59, 27, 49, 17, 57, 25,
      15, 47,  7, 39, 13, 45,  5, 37,
      63, 31, 55, 23, 61, 29, 53, 21
    ].map(v => v * 4);

    const DARK   = [12, 12, 13];
    const LIGHT  = [244, 241, 236];
    const ACCENT = [214, 255, 56];

    /* Doodle overlays — drawn in the accent color over the dither.
       Each function takes the canvas dimensions and returns a flat
       array of [x, y] pixel coordinates. Coordinates are relative to
       the photo so they shift slightly between desktop (132×88) and
       mobile (120×80) but stay aligned with the face. */
    const lineH = (y, x1, x2, dx) => {
      const out = [];
      for (let x = x1; x <= x2; x += (dx || 1)) out.push([x, y]);
      return out;
    };
    const dot = (x, y) => [[x, y]];
    const cross = (cx, cy, r) => {
      const out = [];
      for (let i = -r; i <= r; i++) {
        out.push([cx + i, cy + i]);
        out.push([cx + i, cy - i]);
        out.push([cx + i + 1, cy + i]); // +1 px thickness
        out.push([cx + i + 1, cy - i]);
      }
      return out;
    };
    const ring = (cx, cy, rx, ry) => {
      const out = [];
      const steps = 64;
      for (let s = 0; s < steps; s++) {
        const a = (s / steps) * Math.PI * 2;
        out.push([Math.round(cx + Math.cos(a) * rx), Math.round(cy + Math.sin(a) * ry)]);
      }
      return out;
    };

    // Face landmarks in normalized coords. The photo subject sits
    // upper-center; these are tuned by eye against the live render.
    const FACE = {
      headTop:  { x: 0.49, y: 0.11 },
      leftEye:  { x: 0.43, y: 0.40 },
      rightEye: { x: 0.55, y: 0.40 },
      nose:     { x: 0.49, y: 0.50 },
      mouth:    { x: 0.49, y: 0.62 }
    };
    const N = (n, max) => Math.round(n * max);

    const DOODLES = [
      null, // 0 — off (the photo as photographed)

      // 1 — Xs over the eyes
      function xEyes(W, H) {
        const lx = N(FACE.leftEye.x, W),  ly = N(FACE.leftEye.y, H);
        const rx = N(FACE.rightEye.x, W), ry = N(FACE.rightEye.y, H);
        const r = Math.max(2, Math.round(W * 0.025));
        return [...cross(lx, ly, r), ...cross(rx, ry, r)];
      },

      // 2 — Halo above the head
      function halo(W, H) {
        const cx = N(FACE.headTop.x, W);
        const cy = N(FACE.headTop.y - 0.06, H);
        return ring(cx, cy, Math.round(W * 0.13), Math.round(H * 0.04));
      },

      // 3 — Devil horns
      function horns(W, H) {
        const out = [];
        const baseY = N(FACE.headTop.y, H);
        const off = Math.round(W * 0.07);
        const cx = N(FACE.headTop.x, W);
        const horn = (hx) => {
          for (let i = 0; i < 5; i++) {
            const half = i;
            for (let j = -half; j <= half; j++) {
              if (i === 4 || j === -half || j === half) out.push([hx + j, baseY - i]);
            }
          }
        };
        horn(cx - off);
        horn(cx + off);
        return out;
      },

      // 4 — Sunglasses (two lens rectangles + bridge)
      function sunglasses(W, H) {
        const out = [];
        const ly = N(FACE.leftEye.y, H);
        const lx = N(FACE.leftEye.x, W);
        const rx = N(FACE.rightEye.x, W);
        const lensW = Math.max(3, Math.round(W * 0.045));
        const lensH = Math.max(2, Math.round(H * 0.05));
        const lens = (cx, cy) => {
          for (let i = -lensW; i <= lensW; i++) {
            for (let j = -lensH; j <= lensH; j++) {
              if (Math.abs(i) === lensW || Math.abs(j) === lensH) out.push([cx + i, cy + j]);
            }
          }
        };
        lens(lx, ly);
        lens(rx, ly);
        // bridge
        for (let x = lx + lensW + 1; x < rx - lensW; x++) out.push([x, ly]);
        return out;
      },

      // 5 — Smile arc over the mouth
      function smile(W, H) {
        const out = [];
        const cx = N(FACE.mouth.x, W);
        const cy = N(FACE.mouth.y, H);
        const rx = Math.round(W * 0.07);
        const ry = Math.round(H * 0.06);
        // bottom half of an ellipse
        for (let a = 0; a <= Math.PI; a += 0.08) {
          out.push([Math.round(cx - rx + (1 - Math.cos(a)) * rx), Math.round(cy + Math.sin(a) * ry)]);
        }
        return out;
      }
    ];

    // Index into DOODLES — 0 is the clean photo. Each click cycles.
    let doodle = 0;

    let gray = null;
    let raf = 0;
    let last = 0;
    const t0 = performance.now();
    let visible = true;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload  = () => { sample(); render(performance.now()); start(); };
    img.onerror = () => { fillPlaceholder(); render(performance.now()); start(); };
    img.src = canvas.dataset.src || 'assets/portrait.jpg';

    function sample() {
      const tmp = document.createElement('canvas');
      tmp.width = W; tmp.height = H;
      const tctx = tmp.getContext('2d');
      // Object-fit cover semantics
      const iar = img.naturalWidth / img.naturalHeight;
      const car = W / H;
      let sx, sy, sw, sh;
      if (iar > car) { sh = img.naturalHeight; sw = sh * car; sx = (img.naturalWidth - sw) / 2; sy = 0; }
      else           { sw = img.naturalWidth;  sh = sw / car; sx = 0; sy = (img.naturalHeight - sh) / 2; }
      tctx.drawImage(img, sx, sy, sw, sh, 0, 0, W, H);
      const src = tctx.getImageData(0, 0, W, H).data;
      gray = new Uint8Array(W * H);
      for (let i = 0; i < W * H; i++) {
        const r = src[i * 4], g = src[i * 4 + 1], b = src[i * 4 + 2];
        // Stretch contrast slightly so the dither pops against the dark bg.
        let v = 0.299 * r + 0.587 * g + 0.114 * b;
        v = (v - 128) * 1.18 + 128;
        gray[i] = Math.max(0, Math.min(255, v | 0));
      }
    }

    function fillPlaceholder() {
      // Soft radial vignette at portrait position so the layout reads even
      // before /assets/portrait.jpg is uploaded.
      gray = new Uint8Array(W * H);
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          const cx = (x - W * 0.5) / W;
          const cy = (y - H * 0.42) / H;
          const d = Math.sqrt(cx*cx + cy*cy);
          gray[y * W + x] = Math.max(0, Math.min(255, (220 - d * 280) | 0));
        }
      }
    }

    function render(now) {
      const t = reduce ? 0 : (now - t0) / 1000;
      const ox = (Math.sin(t * 0.25) * 6) | 0;
      const oy = (Math.cos(t * 0.18) * 6) | 0;
      const ts = Math.sin(t * 0.40) * 12;

      const out = ctx.createImageData(W, H);
      const data = out.data;
      for (let y = 0; y < H; y++) {
        const rowBase = ((y + oy) & 7) * 8;
        const yw = y * W;
        for (let x = 0; x < W; x++) {
          const idx = yw + x;
          const v = gray[idx] + ts;
          const m = BAYER[rowBase + ((x + ox) & 7)];
          const c = v > m ? LIGHT : DARK;
          const oi = idx * 4;
          data[oi]     = c[0];
          data[oi + 1] = c[1];
          data[oi + 2] = c[2];
          data[oi + 3] = 255;
        }
      }

      // Doodle overlay: paint accent pixels at face-relative coordinates
      // on top of the dither.
      const fn = DOODLES[doodle];
      if (fn) {
        const pts = fn(W, H);
        for (let p = 0; p < pts.length; p++) {
          const [x, y] = pts[p];
          if (x < 0 || x >= W || y < 0 || y >= H) continue;
          const oi = (y * W + x) * 4;
          data[oi]     = ACCENT[0];
          data[oi + 1] = ACCENT[1];
          data[oi + 2] = ACCENT[2];
          data[oi + 3] = 255;
        }
      }

      ctx.putImageData(out, 0, 0);
    }

    function loop(now) {
      // Cap to ~15 fps for an ambient feel and a kinder battery profile.
      if (now - last >= 65 && visible) { last = now; render(now); }
      if (!reduce && visible) raf = requestAnimationFrame(loop);
      else raf = 0;
    }
    function start() {
      if (raf) return;
      if (reduce) { render(performance.now()); return; }
      raf = requestAnimationFrame(loop);
    }
    function stop() {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    }

    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        for (const e of entries) {
          visible = e.isIntersecting;
          if (visible) start(); else stop();
        }
      });
      io.observe(canvas);
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop();
      else if (visible) start();
    });

    // Each click reveals the next doodle: X eyes → halo → horns →
    // sunglasses → smile → off → loop.
    canvas.addEventListener('click', () => {
      doodle = (doodle + 1) % DOODLES.length;
      if (gray) render(performance.now()); // immediate repaint
    });
  })();

  /* ============================================================
     6. CONSOLE SIGNATURE
     ============================================================ */
  if (typeof console !== 'undefined' && console.log) {
    const css = 'font-family: serif; font-size: 14px; font-style: italic; color: #d6ff38; padding: 4px 0';
    console.log('%cHello, curious one. — Drew', css);
  }
})();
