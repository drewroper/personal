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
  const fmtMs = (ms) => `${Math.round(ms)} ms`;
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

  /* Claude Code spinner — same pulsing-star cycle the CLI shows
     while it's thinking. Loops the symbol next to "Claude Code" in
     the colophon so the mark feels alive. */
  (function spinnerClaudeMark() {
    const el = document.getElementById('js-claude-spinner');
    if (!el) return;
    const FRAMES = ['·', '✢', '✳', '∗', '✻', '✽'];
    let i = 0;
    setInterval(() => {
      i = (i + 1) % FRAMES.length;
      el.textContent = FRAMES[i];
    }, 260);
  })();

  /* Time-on-page ticker — increments every second from page load. */
  (function reportTimeHere() {
    const el = document.getElementById('js-timeonpage');
    if (!el) return;
    const startedAt = Date.now();
    const fmt = (s) => {
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      return h > 0
        ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
        : `${m}:${String(sec).padStart(2, '0')}`;
    };
    const tick = () => {
      el.textContent = fmt(Math.floor((Date.now() - startedAt) / 1000));
    };
    tick();
    setInterval(tick, 1000);
  })();

  /* Visit count — fetched from GoatCounter's public counter endpoint
     and rendered into the colophon. Requires "Allow public access to
     the counter" turned on in the GoatCounter site settings. */
  (function reportVisits() {
    const el = document.getElementById('js-visits');
    if (!el) return;
    fetch('https://drewroper.goatcounter.com/counter/TOTAL.json', { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((data) => {
        const n = parseInt(data.count, 10);
        if (Number.isFinite(n)) el.textContent = n.toLocaleString();
      })
      .catch(() => { /* leave the em-dash placeholder */ });
  })();

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
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/470a2519895231.5f5bdbaf65706.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/1888c216106531.5f983e6d0ca14.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/d2b14b16106531.5f5a81e2c56a6.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/153c9216106531.5f5a81e2c109c.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/b16be216106531.5f5a8bd3bf8d4.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/04f61516106531.5f5a81e2c2501.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_still/14f6b313608983.5f5abddb46075.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_still/6ec3a513608983.5f5abddb46621.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/f8364c103167265.5f472cee7f8ed.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/fc436a103167265.5f46ef490430b.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/43fce8103167265.5f4728f8b4f0d.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/23ddbd19796977.562e06cadfd98.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_632_webp/3f122019796977.562e06ca31a91.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/8cb90213619493.57c6cc31171ac.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_632_webp/673f5713619493.56279c8756603.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_632_webp/d7008f13619493.56279c13ad7bf.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_632_webp/b3883713619493.562996d7e6aaf.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_632_webp/2f3c8113619493.56279e5966f2b.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd/abb75797905583.5ecff5126eb5f.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd/a75b6197905583.5ecff5126db73.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/a03eb597905583.5ecff51321485.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/b832be97905583.5ecff5131c628.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/700547110754963.5ff52a2a6d595.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/ffd76b110754963.5ff52a2a6c313.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/67cc4d110754963.5ff52a2a6df83.jpg',
    'https://mir-cdn.behance.net/v1/rendition/project_modules/hd_webp/46773513618371.5f475a9f3efc7.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/2914af13618371.5f475a9f3df17.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/df0e1513618371.5f475a9f3e881.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/e5ba4713619279.5f4765af9f939.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_1200/db22e814062025.5627c9a4da41a.jpg',
    'https://mir-s3-cdn-cf.behance.net/project_modules/max_1200/2e8e4014062025.5627c99416861.jpg',
    'https://cdn.dribbble.com/users/58866/screenshots/1029223/attachments/124052/derby-party_800.jpg',
    'https://cdn.dribbble.com/userupload/22194261/file/original-99773e67f3c0640908be411ac25b9b8d.jpg?resize=752x564&vertical=center',
    'https://cdn.dribbble.com/userupload/21894247/file/original-c69072010c75071b7cd7e0e2afdff921.jpg?resize=800x600&vertical=center',
    'https://cdn.dribbble.com/userupload/41708673/file/original-1f5bcabbf930f9e34fa0c6ababfc72db.jpg?resize=800x600&vertical=center',
    'assets/12.jpg',
    'assets/15.jpg',
    'assets/1strokers.png',
    'assets/35d79c13772667.56278079f07be.png',
    'assets/46684c23795559.56328eed3145f.jpg',
    'assets/4854d216106531.562a57a9848db.jpg',
    'assets/4c9f6c13608983.5c54c6944cbe1.jpg',
    'assets/53c96313889503.56279ee3c5b68.png',
    'assets/6.jpg',
    'assets/68210e13889503.56279eca5a64c.jpg',
    'assets/6fccbc23795559.56328f3c0004e.jpg',
    'assets/7.jpg',
    'assets/753e0223795559.56328f3bd86f3.jpg',
    'assets/8.jpg',
    'assets/9.jpg',
    'assets/Artboard.png',
    'assets/DrewRoper_FreshHeir.jpeg',
    'assets/DrewRoper_LocalNatives.jpeg',
    'assets/Fence-MockUp-Tempe.jpg',
    'assets/Flatirons%20poster.png',
    'assets/Gemini_Generated_Image_7nc3tm7nc3tm7nc3.png',
    'assets/Gemini_Generated_Image_argc5xargc5xargc.png',
    'assets/Gemini_Generated_Image_dctoq8dctoq8dcto.png',
    'assets/HACK_People.png',
    'assets/HACK_bbb-CloseUp.png',
    'assets/HW_Award_Individual01.png',
    'assets/Hat-Boulder.jpg',
    'assets/Screen%20Shot%202015-07-30%20at%204.05.58%20PM.png',
    'assets/Screen%20Shot%202015-07-30%20at%204.59.59%20PM.png',
    'assets/Screen%20Shot%202015-07-30%20at%205.00.28%20PM.png',
    'assets/a4f35013608983.5c54c6944dafb.jpg',
    'assets/ads.png',
    'assets/b22b2214002221.5627bb6e294f1.png',
    'assets/b68adc13772667.56277f16a2084.png',
    'assets/cc31ee13772667.56277e8618184.png',
    'assets/email.png',
    'assets/grace-weber.jpeg',
    'assets/icons.png',
    'assets/scooters2.png'
  ];
  // URLs whose source assets are transparent / need a white plate
  // behind them so they don't lose their edges on the dark page.
  const WHITE_BG_URLS = new Set([
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/153c9216106531.5f5a81e2c109c.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/hd_webp/04f61516106531.5f5a81e2c2501.png',
    'https://mir-s3-cdn-cf.behance.net/project_modules/1400_opt_1/d2b14b16106531.5f5a81e2c56a6.png'
  ]);
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

    const applyWhiteBg = (cell, url) => {
      cell.classList.toggle('work-cell--white', WHITE_BG_URLS.has(url));
    };

    // Shuffle every image into a single random order and render the
    // whole pool. loading="lazy" defers each fetch until the cell
    // approaches the viewport, so scrolling effectively streams the
    // grid in. Each cell takes its image's natural aspect-ratio once
    // the load lands, which animates the fallback 4/5 into shape.
    const order = shuffleIndices(WORK_IMAGES.length);

    grid.innerHTML = '';
    order.forEach((imgIdx) => {
      const url = WORK_IMAGES[imgIdx];
      const cell = document.createElement('div');
      cell.className = 'work-cell';
      applyWhiteBg(cell, url);

      const img = new Image();
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.className = 'work-cell__layer';
      img.onload = () => {
        setCellRatio(cell, img);
        // requestAnimationFrame so the ratio change is flushed before
        // the fade-in starts; otherwise the image flashes at 4/5.
        requestAnimationFrame(() => img.classList.add('is-active'));
      };
      img.src = url;

      cell.appendChild(img);
      grid.appendChild(cell);
    });
  }

  /* Mobile: render every image as a card in a native horizontal
     scroll-snap row. The next card peeks at the right edge so the
     swipe gesture telegraphs itself; no auto-advance, no reshape,
     so the footer never jumps. */
  function initWorkSlides() {
    const root = document.getElementById('js-work-slides');
    if (!root) return;

    const order = shuffleIndices(WORK_IMAGES.length);
    root.innerHTML = '';

    order.forEach((imgIdx) => {
      const url  = WORK_IMAGES[imgIdx];
      const card = document.createElement('div');
      card.className = 'work-slides__card';
      if (WHITE_BG_URLS.has(url)) card.classList.add('work-slides__card--white');

      const img = new Image();
      img.alt = '';
      img.loading  = 'lazy';
      img.decoding = 'async';
      img.className = 'work-slides__img';
      img.onload = () => requestAnimationFrame(() => img.classList.add('is-loaded'));
      img.src = url;

      card.appendChild(img);
      root.appendChild(card);
    });
  }

  // Bootstrap based on viewport — keep both initialised so a resize works.
  // The CSS handles which one shows.
  initWorkGrid();
  initWorkSlides();

  /* Clients chyron — rAF-driven so touch can drag it. Auto-advance
     waits until the section enters the viewport (Anthropic-first
     guarantee), pauses on hover/focus, and yields to touch drags. */
  (function initClientsMarquee() {
    const section = document.querySelector('.clients');
    const marquee = document.querySelector('.clients__marquee');
    const track   = document.querySelector('.clients__track');
    if (!section || !marquee || !track) return;

    const PX_PER_S = 35;
    const reduced  = matchMedia('(prefers-reduced-motion: reduce)').matches;

    let x = 0, halfW = 0;
    let inView = false, dragging = false, hovered = false;
    let dragStartX = 0, dragStartTrackX = 0;
    let lastT = 0, touchDist = 0;

    const measure = () => { halfW = track.scrollWidth / 2; };
    const apply   = () => { track.style.transform = `translateX(${x}px)`; };
    const wrap    = () => {
      if (!halfW) measure();
      if (!halfW) return;
      while (x <= -halfW) x += halfW;
      while (x > 0)       x -= halfW;
    };

    function tick(t) {
      requestAnimationFrame(tick);
      if (!lastT) { lastT = t; return; }
      const dt = (t - lastT) / 1000;
      lastT = t;
      if (!inView || dragging || hovered || reduced) return;
      x -= PX_PER_S * dt;
      wrap();
      apply();
    }

    if (!('IntersectionObserver' in window)) {
      inView = true;
    } else {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) { inView = true; io.disconnect(); }
        });
      }, { threshold: 0.15 });
      io.observe(section);
    }

    marquee.addEventListener('mouseenter', () => { hovered = true; });
    marquee.addEventListener('mouseleave', () => { hovered = false; });
    marquee.addEventListener('focusin',    () => { hovered = true; });
    marquee.addEventListener('focusout',   () => { hovered = false; });

    // A real click on a pill (i.e. the user committed to a link, not a
    // swipe) releases the hover lock so the chyron keeps moving.
    marquee.addEventListener('click', (e) => {
      if (e.defaultPrevented) return; // swallowed by a drag
      if (e.target.closest('.clients__pill')) hovered = false;
    });

    marquee.addEventListener('touchstart', (e) => {
      if (e.touches.length !== 1) return;
      measure();
      dragging = true;
      dragStartX = e.touches[0].clientX;
      dragStartTrackX = x;
      touchDist = 0;
    }, { passive: true });

    marquee.addEventListener('touchmove', (e) => {
      if (!dragging || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - dragStartX;
      touchDist = Math.abs(dx);
      x = dragStartTrackX + dx;
      wrap();
      apply();
    }, { passive: true });

    marquee.addEventListener('touchend', () => {
      dragging = false;
      // If the finger actually moved, swallow the synthesized click
      // so a swipe doesn't accidentally launch a pill's link.
      if (touchDist > 8) {
        const swallow = (ev) => { ev.preventDefault(); ev.stopPropagation(); };
        marquee.addEventListener('click', swallow, { capture: true, once: true });
      }
    });

    window.addEventListener('resize', measure);
    setTimeout(measure, 250);
    requestAnimationFrame(tick);
  })();

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
    // Desktop gets a denser dither than mobile. Mobile stays at 120×80
    // (set on the canvas element); desktop bumps up to 144×96 — same
    // 3:2 aspect, +20% per axis (~44% more pixels). Tighter grain on
    // a bigger screen; chunky aesthetic preserved.
    const isDesktop = window.matchMedia('(min-width: 760px)').matches;
    if (isDesktop) {
      canvas.width  = 144;
      canvas.height = 96;
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
        // 3-pixel-thick X, symmetric around the center column (no right-skew).
        for (let t = -1; t <= 1; t++) {
          out.push([cx + i + t, cy + i]);
          out.push([cx + i + t, cy - i]);
        }
      }
      return out;
    };
    const ring = (cx, cy, rx, ry, thickness = 1) => {
      const out = [];
      const steps = 96;
      for (let t = 0; t < thickness; t++) {
        for (let s = 0; s < steps; s++) {
          const a = (s / steps) * Math.PI * 2;
          out.push([
            Math.round(cx + Math.cos(a) * (rx + t)),
            Math.round(cy + Math.sin(a) * (ry + t))
          ]);
        }
      }
      return out;
    };

    // Hand-drawn ring — same as ring() but with deterministic noise on
    // the radius so the line wobbles slightly, like a sketch.
    const handRing = (cx, cy, rx, ry, thickness = 1) => {
      const out = [];
      const steps = 128;
      for (let t = 0; t < thickness; t++) {
        for (let s = 0; s < steps; s++) {
          const a = (s / steps) * Math.PI * 2;
          // Two layered sines give an organic wobble that doesn't repeat
          const wobble = Math.sin(a * 5 + 0.7) * 0.9
                       + Math.sin(a * 11 + 1.4) * 0.5;
          out.push([
            Math.round(cx + Math.cos(a) * (rx + t + wobble)),
            Math.round(cy + Math.sin(a) * (ry + t + wobble))
          ]);
        }
      }
      return out;
    };

    // Thick diagonal line from (x1,y1) to (x2,y2). Stamps a small cross
    // at every step so the line reads as 3 pixels wide.
    const thickLine = (x1, y1, x2, y2) => {
      const out = [];
      const steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        const x = Math.round(x1 + (x2 - x1) * t);
        const y = Math.round(y1 + (y2 - y1) * t);
        out.push([x, y], [x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
      }
      return out;
    };

    // Face landmarks in normalized coords. The photo subject sits
    // upper-center, biased a touch right of frame center.
    const FACE = {
      headTop:  { x: 0.52, y: 0.11 },
      leftEye:  { x: 0.46, y: 0.22 },
      rightEye: { x: 0.58, y: 0.22 },
      nose:     { x: 0.52, y: 0.30 },
      mouth:    { x: 0.52, y: 0.37 }
    };
    const N = (n, max) => Math.round(n * max);

    const filledCircle = (cx, cy, r) => {
      const out = [];
      const r2 = r * r;
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          if (dx * dx + dy * dy <= r2) out.push([cx + dx, cy + dy]);
        }
      }
      return out;
    };

    // Smile arc: bottom half of an ellipse centered at (cx, cy).
    const smileArc = (cx, cy, rx, ry, thickness = 2) => {
      const out = [];
      for (let a = 0; a <= Math.PI; a += 0.04) {
        const x = Math.round(cx - rx + (1 - Math.cos(a)) * rx);
        const y = Math.round(cy + Math.sin(a) * ry);
        for (let t = 0; t < thickness; t++) out.push([x, y + t]);
      }
      return out;
    };

    // Pixel heart, 13 wide × 10 tall, centered horizontally at col 6,
    // top of bitmap at -5 from center. Big-big.
    const HEART = (() => {
      const rows = [
        '.####...####.',  // -5 (two top lobes)
        '#############',  // -4
        '#############',  // -3
        '#############',  // -2
        '.###########.',  // -1
        '..#########..',  //  0
        '...#######...',  //  1
        '....#####....',  //  2
        '.....###.....',  //  3
        '......#......',  //  4
      ];
      const halfW = 6;
      const dyStart = -5;
      const out = [];
      for (let r = 0; r < rows.length; r++) {
        for (let c = 0; c < rows[r].length; c++) {
          if (rows[r][c] === '#') out.push([c - halfW, dyStart + r]);
        }
      }
      return out;
    })();
    const heart = (cx, cy) => HEART.map(([dx, dy]) => [cx + dx, cy + dy]);

    const DOODLES = [
      null, // 0 — off (the photo as photographed)

      // 1 — Xs over the eyes (shifted slightly left for alignment)
      function xEyes(W, H) {
        const lx = N(FACE.leftEye.x, W)  - 2, ly = N(FACE.leftEye.y, H);
        const rx = N(FACE.rightEye.x, W) - 2, ry = N(FACE.rightEye.y, H) + 2;
        const r = Math.max(4, Math.round(W * 0.056));
        return [...cross(lx, ly, r), ...cross(rx, ry, r)];
      },

      // 2 — Heart eyes (sit a few pixels lower than the eye landmarks
      // and a touch left so they land on the actual irises)
      function heartEyes(W, H) {
        const dx = -1, dy = 3;
        const lx = N(FACE.leftEye.x, W)  + dx, ly = N(FACE.leftEye.y, H)  + dy;
        const rx = N(FACE.rightEye.x, W) + dx, ry = N(FACE.rightEye.y, H) + dy;
        return [...heart(lx, ly), ...heart(rx, ry)];
      },

      // 3 — Halo above the head
      function halo(W, H) {
        const cx = N(FACE.headTop.x, W) - 2;
        const cy = N(FACE.headTop.y - 0.06, H);
        return ring(cx, cy, Math.round(W * 0.13), Math.round(H * 0.04), 2);
      },

      // 3 — Devil horns — wide base on the head, tapering to a curling tip
      function horns(W, H) {
        const out = [];
        const baseY = N(FACE.headTop.y, H);
        const cx = N(FACE.headTop.x, W);
        const off = Math.round(W * 0.06);
        // Each entry: row offset (dy) + array of dx offsets for that row.
        // dx >= 0 = outward (away from head center). 5-wide base tapering
        // to a 2-pixel tip that curls back inward.
        const shape = [
          { dy:  1, dxs: [-1, 0, 1, 2, 3] },     // base bottom, on head
          { dy:  0, dxs: [-1, 0, 1, 2, 3] },     // 5-wide base
          { dy: -1, dxs: [-1, 0, 1, 2, 3, 4] },  // 6-wide, leaning out
          { dy: -2, dxs: [ 0, 1, 2, 3, 4] },     // 5-wide
          { dy: -3, dxs: [ 1, 2, 3, 4, 5] },     // 5-wide, more outward
          { dy: -4, dxs: [ 2, 3, 4, 5] },        // 4-wide
          { dy: -5, dxs: [ 3, 4, 5] },           // 3-wide
          { dy: -6, dxs: [ 3, 4] },              // 2-wide peak
          { dy: -7, dxs: [ 2, 3] },              // 2-wide, curling back
          { dy: -8, dxs: [ 1, 2] }               // 2-wide tip pointing inward
        ];
        const horn = (baseX, dir) => {
          for (const r of shape) {
            for (const dx of r.dxs) {
              out.push([baseX + dir * dx, baseY + r.dy]);
            }
          }
        };
        horn(cx - off - 2, -1);
        horn(cx + off,      1);
        return out;
      },

      // 5 — Mustache traced as a single continuous line: horizontal "M"
      // shape — curl at each end, swoop up to a peak, dip to a valley
      // in the middle. Line is thinner at the tips and the middle
      // point, thicker through the swoops.
      function mustache(W, H) {
        const out = [];
        // Anchor a couple pixels left of the FACE.nose center so the
        // mustache lands over Drew's actual upper lip.
        const cx = N(FACE.nose.x, W) - 2;
        const cy = N(FACE.mouth.y, H) - 2;

        // Path: [dx, centerline_dy, thickness]. Tips rise into a curl
        // before the line drops to the swoop, peaks at -3 above anchor.
        const path = [
          [-19, -2, 1],  // far-left tip (curling up)
          [-18, -3, 1],  // top of curl
          [-17, -2, 2],
          [-16, -1, 2],
          [-15,  0, 2],
          [-14,  0, 2],
          [-13, -1, 3],
          [-12, -1, 3],
          [-11, -2, 3],
          [-10, -2, 4],
          [ -9, -3, 4],
          [ -8, -3, 4],
          [ -7, -3, 3],   // left peak (thinner)
          [ -6, -3, 3],
          [ -5, -3, 4],
          [ -4, -2, 4],
          [ -3, -2, 4],
          [ -2, -1, 3],
          [ -1, -1, 2],
          [  0,  0, 1],   // valley (thin)
          [  1, -1, 2],
          [  2, -1, 3],
          [  3, -2, 4],
          [  4, -2, 4],
          [  5, -3, 4],
          [  6, -3, 3],   // right peak
          [  7, -3, 3],
          [  8, -3, 4],
          [  9, -3, 4],
          [ 10, -2, 4],
          [ 11, -2, 3],
          [ 12, -1, 3],
          [ 13, -1, 3],
          [ 14,  0, 2],
          [ 15,  0, 2],
          [ 16, -1, 2],
          [ 17, -2, 2],
          [ 18, -3, 1],   // top of right curl
          [ 19, -2, 1]    // far-right tip
        ];
        for (const [dx, yc, thick] of path) {
          for (let t = 0; t < thick; t++) {
            out.push([cx + dx, cy + yc + t]);
          }
        }
        return out;
      },

      // 6 — Smiley face: tall pill eyes + a wide thick smile.
      // Eyes drop a few rows below the FACE landmark and pull closer
      // together; mouth comes up. Whole face shifts a touch left.
      function smiley(W, H) {
        const out = [];
        const xShift = -2;     // nudge whole face left
        const yShift = -1;     // nudge whole face up
        const eyeYOff = 4;     // down
        const eyeXSqueeze = 2; // each eye toward center
        const mouthYOff = -4;  // mouth up

        const lx = N(FACE.leftEye.x, W)  + eyeXSqueeze + xShift, ly = N(FACE.leftEye.y, H)  + eyeYOff + yShift;
        const rx = N(FACE.rightEye.x, W) - eyeXSqueeze + xShift, ry = N(FACE.rightEye.y, H) + eyeYOff + yShift;

        // 5-wide × 9-tall vertical pill — reads as a happy almond eye.
        const eyeRows = [
          '.###.',
          '#####',
          '#####',
          '#####',
          '#####',
          '#####',
          '#####',
          '#####',
          '.###.'
        ];
        const halfEyeW = 2;
        const halfEyeH = 4;
        const drawEye = (cx, cy) => {
          for (let r = 0; r < eyeRows.length; r++) {
            for (let c = 0; c < eyeRows[r].length; c++) {
              if (eyeRows[r][c] === '#') {
                out.push([cx + c - halfEyeW, cy + r - halfEyeH]);
              }
            }
          }
        };
        drawEye(lx, ly);
        drawEye(rx, ry);

        // Smile: wide arc, 3-pixel thick.
        const mx = N(FACE.mouth.x, W) + xShift;
        const my = N(FACE.mouth.y, H) + mouthYOff + yShift;
        out.push(...smileArc(mx, my, Math.round(W * 0.10), Math.round(H * 0.07), 3));

        // Head outline — a hand-drawn 2-pixel ring around the eyes
        // and mouth. Closer to circular than oval. Sits low enough
        // that the smiley reads as a face floating over Drew's head.
        const headCx = N(FACE.nose.x, W) - 1;
        const headCy = Math.round((N(FACE.leftEye.y, H) + N(FACE.mouth.y, H)) / 2 + 2) + yShift;
        out.push(...handRing(headCx, headCy, Math.round(W * 0.16), Math.round(H * 0.23), 2));
        return out;
      },

      // 7 — Necklace with a more obnoxious dollar pendant
      function chain(W, H) {
        const out = [];
        const chainCenterY = N(0.56, H);
        const chainCenterX = N(0.49, W);
        const halfSpan = Math.round(W * 0.10);
        // Chain hangs in a deep parabolic dip and is 3 rows thick so
        // it has weight; the deepest point reaches the top of the
        // pendant below.
        for (let dx = -halfSpan; dx <= halfSpan; dx++) {
          const t = dx / halfSpan;
          const dy = Math.round((1 - t * t) * 9);
          const x = chainCenterX + dx;
          const y = chainCenterY + dy;
          if (((dx + halfSpan) % 3) === 2) continue; // chain-link gaps
          out.push([x, y], [x, y + 1], [x, y + 2]);
        }

        // 17×21 big-big dollar sign. 3-col vertical bar runs all the
        // way through (top, S-curves, bottom) so it reads as a proper
        // dollar sign — not just a bar at the ends. Side curves are
        // also 3 cols thick for that heavy-metal weight.
        const dollarRows = [
          '.......###.......',  // -10
          '.......###.......',  //  -9
          '.......###.......',  //  -8
          '.###############.',  //  -7
          '.###############.',  //  -6
          '.###############.',  //  -5
          '###....###.......',  //  -4
          '###....###.......',  //  -3
          '###....###.......',  //  -2
          '.###############.',  //  -1
          '.###############.',  //   0
          '.###############.',  //   1
          '.......###....###',  //   2
          '.......###....###',  //   3
          '.......###....###',  //   4
          '.###############.',  //   5
          '.###############.',  //   6
          '.###############.',  //   7
          '.......###.......',  //   8
          '.......###.......',  //   9
          '.......###.......'   //  10
        ];
        const halfDX = 8;   // (17-1)/2
        const halfDY = 10;  // (21-1)/2
        const cx = chainCenterX;
        const cy = chainCenterY + 21; // pendant hangs lower, touching the chain dip
        for (let r = 0; r < dollarRows.length; r++) {
          const row = dollarRows[r];
          for (let c = 0; c < row.length; c++) {
            if (row[c] === '#') out.push([cx + (c - halfDX), cy + (r - halfDY)]);
          }
        }
        return out;
      },

      // 8 — Big lime X across the face
      function bigX(W, H) {
        const cx = N(FACE.nose.x, W);
        const cy = N(FACE.nose.y, H);
        const hw = Math.round(W * 0.22);
        const hh = Math.round(H * 0.22);
        return [
          ...thickLine(cx - hw, cy - hh, cx + hw, cy + hh),
          ...thickLine(cx + hw, cy - hh, cx - hw, cy + hh)
        ];
      }
    ];

    // Index into DOODLES — 0 is the clean photo. Each click cycles.
    let doodle = 0;

    // Pixels painted by the visitor in Draw mode (set of "x,y").
    const userPixels = new Set();

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

      // User-drawn pixels (Draw mode) — same lime accent.
      if (userPixels.size) {
        for (const key of userPixels) {
          const ci = key.indexOf(',');
          const x = +key.slice(0, ci), y = +key.slice(ci + 1);
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

    // Each click reveals the next doodle. Draw mode disables this so
    // clicks paint instead. Once the visitor has wrapped past every
    // preset, expose the Draw pill on mobile too.
    canvas.addEventListener('click', () => {
      if (drawMode) return;
      doodle = (doodle + 1) % DOODLES.length;
      if (doodle === 0) {
        const btn = document.getElementById('js-portrait-draw');
        if (btn) btn.classList.add('portrait__draw--unlocked');
      }
      if (gray) render(performance.now());
    });

    /* ----------------------------------------------------------
       Draw mode. Pill ships visible on desktop and unlocks on mobile
       once the visitor has cycled through every preset doodle.
       Click "Draw" → enter draw mode, doodle resets to clean photo,
       button becomes "Clear", crosshair cursor, pointer (mouse or
       finger) paints lime pixels (Bresenham line for smooth strokes).
       Click "Clear" → wipe user pixels and exit draw mode.
       ---------------------------------------------------------- */
    const drawBtn = document.getElementById('js-portrait-draw');
    let drawMode = false;
    let isDrawing = false;
    let lastPx = -1, lastPy = -1;

    const evToPixel = (e) => {
      const rect = canvas.getBoundingClientRect();
      const px = Math.round((e.clientX - rect.left) * canvas.width  / rect.width);
      const py = Math.round((e.clientY - rect.top)  * canvas.height / rect.height);
      return [px, py];
    };
    const stamp = (px, py) => {
      // 1-pixel cross brush
      const offsets = [[0,0],[1,0],[-1,0],[0,1],[0,-1]];
      for (const [dx, dy] of offsets) userPixels.add(`${px+dx},${py+dy}`);
    };
    const lineStamp = (x0, y0, x1, y1) => {
      const dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
      const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
      let err = dx - dy, x = x0, y = y0;
      while (true) {
        stamp(x, y);
        if (x === x1 && y === y1) break;
        const e2 = err * 2;
        if (e2 > -dy) { err -= dy; x += sx; }
        if (e2 <  dx) { err += dx; y += sy; }
      }
    };

    if (drawBtn) {
      drawBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (drawMode) {
          // Clear + exit
          userPixels.clear();
          drawMode = false;
          drawBtn.textContent = 'Doodle';
          drawBtn.classList.remove('is-active');
          canvas.classList.remove('is-drawing');
        } else {
          // Enter draw mode on a clean photo
          drawMode = true;
          doodle = 0;
          drawBtn.textContent = 'Clear';
          drawBtn.classList.add('is-active');
          canvas.classList.add('is-drawing');
        }
        if (gray) render(performance.now());
      });
    }

    canvas.addEventListener('pointerdown', (e) => {
      if (!drawMode) return;
      e.preventDefault();
      isDrawing = true;
      const [x, y] = evToPixel(e);
      lastPx = x; lastPy = y;
      stamp(x, y);
      if (gray) render(performance.now());
    });
    canvas.addEventListener('pointermove', (e) => {
      if (!drawMode || !isDrawing) return;
      const [x, y] = evToPixel(e);
      lineStamp(lastPx, lastPy, x, y);
      lastPx = x; lastPy = y;
      if (gray) render(performance.now());
    });
    const stopDraw = () => { isDrawing = false; };
    canvas.addEventListener('pointerup', stopDraw);
    canvas.addEventListener('pointerleave', stopDraw);
    canvas.addEventListener('pointercancel', stopDraw);
  })();

  /* ============================================================
     6. CONSOLE SIGNATURE
     ============================================================ */
  if (typeof console !== 'undefined' && console.log) {
    const css = 'font-family: serif; font-size: 14px; font-style: italic; color: #d6ff38; padding: 4px 0';
    console.log('%cHello, curious one. — Drew', css);
  }
})();
