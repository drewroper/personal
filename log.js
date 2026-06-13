/* drewroper.com — life log renderer.

   Reads data/life-log.json (refreshed hourly by the
   .github/workflows/life-log.yml action) and renders an inline wall
   of CLI-style entries grouped by the year they happened in.

   Year pills are position: sticky so the year stays pinned to the
   top of the viewport while you scroll its entries. */

(() => {
  const MONTHS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];

  // Source → [tag, glyph]
  const SRC = {
    letterboxd: ['[lb]', '⌗'],
    discogs:    ['[dc]', '◉'],
  };

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

    const [tag, glyph] = SRC[e.source] || ['[?]', '·'];
    const tagEl = document.createElement('span'); tagEl.className = 'entry__tag';   tagEl.textContent = tag + ' ';
    const glEl  = document.createElement('span'); glEl.className  = 'entry__glyph'; glEl.textContent  = glyph + ' ';
    span.append(tagEl, glEl);

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
