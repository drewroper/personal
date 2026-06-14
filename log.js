/* drewroper.com — life log renderer.

   Reads data/life-log.json (refreshed hourly by the
   .github/workflows/life-log.yml action) and renders an inline wall
   of CLI-style entries grouped by the year they happened in.

   Year pills are position: sticky so the year stays pinned to the
   top of the viewport while you scroll its entries. */

(() => {
  const MONTHS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];

  /* Phosphor icon set (light weight, 256-viewBox). Inlined SVG path
     data — no external requests, scales as text, inherits currentColor
     via stroke=none/fill=currentColor on Phosphor's default rendering
     (these are solid-look outline glyphs; CSS handles colour). */
  const ICONS = {
    'film-reel':         'M232,218H176a102,102,0,1,0-48,12H232a6,6,0,0,0,0-12ZM38,128a90,90,0,1,1,90,90A90.1,90.1,0,0,1,38,128Zm90-26a22,22,0,1,0-22-22A22,22,0,0,0,128,102Zm0-32a10,10,0,1,1-10,10A10,10,0,0,1,128,70Zm22,106a22,22,0,1,0-22,22A22,22,0,0,0,150,176Zm-32,0a10,10,0,1,1,10,10A10,10,0,0,1,118,176Zm58-26a22,22,0,1,0-22-22A22,22,0,0,0,176,150Zm0-32a10,10,0,1,1-10,10A10,10,0,0,1,176,118ZM80,106a22,22,0,1,0,22,22A22,22,0,0,0,80,106Zm0,32a10,10,0,1,1,10-10A10,10,0,0,1,80,138Z',
    'vinyl-record':      'M128,26A102,102,0,1,0,230,128,102.12,102.12,0,0,0,128,26Zm0,192a90,90,0,1,1,90-90A90.1,90.1,0,0,1,128,218Zm0-148a58.07,58.07,0,0,0-58,58,6,6,0,0,1-12,0,70.08,70.08,0,0,1,70-70,6,6,0,0,1,0,12Zm70,58a70.08,70.08,0,0,1-70,70,6,6,0,0,1,0-12,58.07,58.07,0,0,0,58-58,6,6,0,0,1,12,0Zm-40,0a30,30,0,1,0-30,30A30,30,0,0,0,158,128Zm-48,0a18,18,0,1,1,18,18A18,18,0,0,1,110,128Z',
    'microphone-stage':  'M168,18A69.94,69.94,0,0,0,98.74,98l-70,95.46a13.92,13.92,0,0,0,1.39,18.17l14.3,14.3a13.93,13.93,0,0,0,18.17,1.39l95.46-70A70,70,0,1,0,168,18Zm58,70a57.65,57.65,0,0,1-13,36.52L131.49,43A57.95,57.95,0,0,1,226,88ZM55.5,217.59a2,2,0,0,1-2.6-.2L38.61,203.1a2,2,0,0,1-.2-2.6l64.22-87.56a70.32,70.32,0,0,0,40.44,40.43ZM110,88a57.73,57.73,0,0,1,13-36.52L204.53,133A58,58,0,0,1,110,88Zm-1.75,59.75a6,6,0,0,1,0,8.49l-8,8a6,6,0,1,1-8.49-8.49l8-8A6,6,0,0,1,108.26,147.74Z',
    'beer-stein':        'M216,90H198V72a38,38,0,0,0-38-38H148.07C136.47,23.8,120.56,18,104,18,69.81,18,42,42.22,42,72V208a14,14,0,0,0,14,14H184a14,14,0,0,0,14-14V198h18a22,22,0,0,0,22-22V112A22,22,0,0,0,216,90ZM104,30c14.38,0,28.08,5.22,37.59,14.33A6,6,0,0,0,145.74,46H160a26,26,0,0,1,25.29,20H54.52C58,45.67,78.86,30,104,30Zm82,178a2,2,0,0,1-2,2H56a2,2,0,0,1-2-2V78H186Zm40-32a10,10,0,0,1-10,10H198V102h18a10,10,0,0,1,10,10ZM102,104v80a6,6,0,0,1-12,0V104a6,6,0,0,1,12,0Zm48,0v80a6,6,0,0,1-12,0V104a6,6,0,0,1,12,0Z',
    'music-notes':       'M211.69,19.27a6,6,0,0,0-5.15-1.09l-128,32A6,6,0,0,0,74,56V170.11A34,34,0,1,0,86,196V108.68l116-29v58.43A34,34,0,1,0,214,164V24A6,6,0,0,0,211.69,19.27ZM52,218a22,22,0,1,1,22-22A22,22,0,0,1,52,218ZM86,96.32V60.68l116-29V67.32ZM180,186a22,22,0,1,1,22-22A22,22,0,0,1,180,186Z',
    'book-bookmark':     'M208,26H72A30,30,0,0,0,42,56V224a6,6,0,0,0,6,6H192a6,6,0,0,0,0-12H54v-2a18,18,0,0,1,18-18H208a6,6,0,0,0,6-6V32A6,6,0,0,0,208,26ZM118,38h52v78L147.59,99.2a6,6,0,0,0-7.2,0L118,116Zm84,148H72a29.87,29.87,0,0,0-18,6V56A18,18,0,0,1,72,38h34v90a6,6,0,0,0,9.6,4.8L144,111.5l28.41,21.3A6,6,0,0,0,182,128V38h20Z',
    'git-branch':        'M230,64a30,30,0,1,0-36,29.4V112a10,10,0,0,1-10,10H96a21.84,21.84,0,0,0-10,2.42v-31a30,30,0,1,0-12,0v69.2a30,30,0,1,0,12,0V144a10,10,0,0,1,10-10h88a22,22,0,0,0,22-22V93.4A30.05,30.05,0,0,0,230,64ZM62,64A18,18,0,1,1,80,82,18,18,0,0,1,62,64ZM98,192a18,18,0,1,1-18-18A18,18,0,0,1,98,192ZM200,82a18,18,0,1,1,18-18A18,18,0,0,1,200,82Z',
    'git-pull-request':  'M102,64A30,30,0,1,0,66,93.4v69.2a30,30,0,1,0,12,0V93.4A30.05,30.05,0,0,0,102,64ZM54,64A18,18,0,1,1,72,82,18,18,0,0,1,54,64ZM90,192a18,18,0,1,1-18-18A18,18,0,0,1,90,192Zm116-29.4v-52a21.88,21.88,0,0,0-6.44-15.56L158.48,54H192a6,6,0,0,0,0-12H144a6,6,0,0,0-6,6V96a6,6,0,0,0,12,0V62.48l41.07,41.08a9.91,9.91,0,0,1,2.93,7.07v52a30,30,0,1,0,12,0ZM200,210a18,18,0,1,1,18-18A18,18,0,0,1,200,210Z',
    'git-merge':         'M208,114a30,30,0,0,0-29.21,23.19l-44-6.28a10,10,0,0,1-6.18-3.39L91.18,83.83A30,30,0,1,0,74,85.4v85.2a30,30,0,1,0,12,0V96.22l33.52,39.11a22,22,0,0,0,13.6,7.46l45.35,6.48A30,30,0,1,0,208,114ZM62,56A18,18,0,1,1,80,74,18,18,0,0,1,62,56ZM98,200a18,18,0,1,1-18-18A18,18,0,0,1,98,200Zm110-38a18,18,0,1,1,18-18A18,18,0,0,1,208,162Z',
    'tag':               'M241.91,137.42,142.59,38.1a13.94,13.94,0,0,0-9.9-4.1H40a6,6,0,0,0-6,6v92.69a13.94,13.94,0,0,0,4.1,9.9l99.32,99.32a14,14,0,0,0,19.8,0l84.69-84.69A14,14,0,0,0,241.91,137.42Zm-8.49,11.31-84.69,84.69a2,2,0,0,1-2.83,0L46.59,134.1a2,2,0,0,1-.59-1.41V46h86.69a2,2,0,0,1,1.41.59l99.32,99.31A2,2,0,0,1,233.42,148.73ZM94,84A10,10,0,1,1,84,74,10,10,0,0,1,94,84Z',
    'git-fork':          'M222,64a30,30,0,1,0-36,29.4V112a10,10,0,0,1-10,10H80a10,10,0,0,1-10-10V93.4a30,30,0,1,0-12,0V112a22,22,0,0,0,22,22h42v28.6a30,30,0,1,0,12,0V134h42a22,22,0,0,0,22-22V93.4A30.05,30.05,0,0,0,222,64ZM46,64A18,18,0,1,1,64,82,18,18,0,0,1,46,64ZM146,192a18,18,0,1,1-18-18A18,18,0,0,1,146,192ZM192,82a18,18,0,1,1,18-18A18,18,0,0,1,192,82Z',
  };

  // Source → [tag, phosphor-icon-name]
  const SRC = {
    letterboxd: ['[lb]', 'film-reel'],
    discogs:    ['[dc]', 'vinyl-record'],
    songkick:   ['[sk]', 'microphone-stage'],
    untappd:    ['[ut]', 'beer-stein'],
    aoty:       ['[ao]', 'music-notes'],
    books:      ['[bk]', 'book-bookmark'],
  };

  /* Build an inline SVG element for a Phosphor icon. The svg inherits
     currentColor via fill, so colour is controlled by the surrounding
     class's `color` property. */
  function iconEl(name) {
    const path = ICONS[name];
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'entry__icon');
    svg.setAttribute('viewBox', '0 0 256 256');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    if (path) {
      const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', path);
      p.setAttribute('fill', 'currentColor');
      svg.appendChild(p);
    }
    return svg;
  }

  function fmtDate(iso) {
    // "2026-06-12" → "12 jun"
    if (!iso || iso.length < 10) return '';
    const m = MONTHS[parseInt(iso.slice(5, 7), 10) - 1] || '';
    const d = String(parseInt(iso.slice(8, 10), 10) || '').padStart(2, '0');
    return `${d} ${m}`;
  }

  function yearOf(iso) { return (iso || '').slice(0, 4); }

  // Build one entry as a DOM fragment.
  function entryEl(e) {
    const span = document.createElement('span');
    span.className = 'entry';

    const [tag, iconName] = SRC[e.source] || ['[?]', null];
    const tagEl = document.createElement('span');
    tagEl.className   = 'entry__tag';
    tagEl.textContent = tag + ' ';
    span.appendChild(tagEl);
    if (iconName && ICONS[iconName]) {
      span.appendChild(iconEl(iconName));
      span.appendChild(document.createTextNode(' '));
    }

    // Title (linked).
    const a = document.createElement('a');
    a.href = e.url || '#';
    a.target = '_blank';
    a.rel = 'noopener';

    if (e.source === 'discogs') {
      // "Artist — Title"
      const parts = [e.artist, e.title].filter(Boolean).join(' — ');
      a.textContent = parts;
    } else {
      a.textContent = e.title || '';
    }
    span.appendChild(a);

    // Year of the work, e.g. " (2023)"
    if (e.year) {
      const y = document.createElement('span');
      y.className = 'entry__year';
      y.textContent = ` (${e.year})`;
      span.appendChild(y);
    }

    // Rating (letterboxd) — preceded by middle dot.
    if (e.rating) {
      const sep = document.createElement('span');
      sep.className = 'sep'; sep.textContent = ' · ';
      const r = document.createElement('span');
      r.className = 'entry__rating'; r.textContent = e.rating;
      span.append(sep, r);
    }

    // Rewatch indicator.
    if (e.source === 'letterboxd' && e.rewatch) {
      const sep = document.createElement('span');
      sep.className = 'sep'; sep.textContent = ' · ';
      const r = document.createElement('span');
      r.className = 'entry__date'; r.textContent = 'rewatch';
      span.append(sep, r);
    }

    // Date — for discogs prefix with "added", for letterboxd just the date.
    const sep = document.createElement('span');
    sep.className = 'sep'; sep.textContent = ' · ';
    const d = document.createElement('span');
    d.className = 'entry__date';
    d.textContent = (e.source === 'discogs' ? 'added ' : '') + fmtDate(e.date);
    span.append(sep, d);

    return span;
  }

  function render(entries) {
    const root = document.getElementById('js-feed');
    const count = document.getElementById('js-count');
    if (!root) return;

    if (!entries.length) {
      root.className = 'empty';
      root.textContent = 'No entries yet.';
      if (count) count.textContent = '0';
      return;
    }

    root.className = ''; // drop .empty
    root.innerHTML = '';
    if (count) count.textContent = String(entries.length);

    // One unbroken stream — year pills are inserted inline at the
    // moment each year changes. The feed reads as a single flowing
    // chain of events; the pills act as ordering markers, not
    // section dividers. The pill is bound to the next entry via a
    // non-breaking space so the album/film always sits right next
    // to the year, never wrapping to a new line on its own.
    let lastYear = null;
    entries.forEach((e, i) => {
      const y = yearOf(e.date);
      const yearChanged = y !== lastYear;

      // Separator between entries: " / " before each entry except the
      // very first. When the year just changed, the separator goes
      // BEFORE the pill, and there's no separator between pill+entry —
      // just a non-breaking space.
      if (i > 0) {
        const s = document.createElement('span');
        s.className = 'sep';
        s.textContent = '  /  ';
        root.appendChild(s);
      }
      if (yearChanged) {
        const pill = document.createElement('span');
        pill.className = 'year__pill';
        pill.textContent = y;
        root.appendChild(pill);
        //   = non-breaking space, keeps pill + next entry on the
        // same line as one wrap unit.
        root.appendChild(document.createTextNode(' '));
        lastYear = y;
      }
      root.appendChild(entryEl(e));
    });
  }

  // Hydrate any [data-icon] holders in the static HTML (e.g. the
  // legend in the meta row) with their Phosphor SVG.
  document.querySelectorAll('[data-icon]').forEach((el) => {
    const name = el.getAttribute('data-icon');
    if (ICONS[name]) el.appendChild(iconEl(name));
  });

  fetch('data/life-log.json', { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error('fetch failed'))))
    .then((data) => render(Array.isArray(data) ? data : []))
    .catch(() => {
      const root = document.getElementById('js-feed');
      if (root) {
        root.className = 'empty';
        root.textContent = 'Log unavailable — the feed will refresh on the next deploy.';
      }
    });
})();
