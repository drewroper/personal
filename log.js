/* drewroper.com — life log renderer.

   Reads data/life-log.json (refreshed hourly by the
   .github/workflows/life-log.yml action) and renders an inline wall
   of CLI-style entries grouped by the year they happened in.

   Year pills are position: sticky so the year stays pinned to the
   top of the viewport while you scroll its entries. */

(() => {
  const MONTHS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];

  /* Phosphor icon set (regular weight, 256-viewBox). Inlined SVG path
     data — no external requests, scales with surrounding text, takes
     colour from currentColor via the path's fill attribute. */
  const ICONS = {
    'film-reel':         'M232,216H183.36A103.95,103.95,0,1,0,128,232H232a8,8,0,0,0,0-16ZM40,128a88,88,0,1,1,88,88A88.1,88.1,0,0,1,40,128Zm88-24a24,24,0,1,0-24-24A24,24,0,0,0,128,104Zm0-32a8,8,0,1,1-8,8A8,8,0,0,1,128,72Zm24,104a24,24,0,1,0-24,24A24,24,0,0,0,152,176Zm-32,0a8,8,0,1,1,8,8A8,8,0,0,1,120,176Zm56-24a24,24,0,1,0-24-24A24,24,0,0,0,176,152Zm0-32a8,8,0,1,1-8,8A8,8,0,0,1,176,120ZM80,104a24,24,0,1,0,24,24A24,24,0,0,0,80,104Zm0,32a8,8,0,1,1,8-8A8,8,0,0,1,80,136Z',
    'vinyl-record':      'M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm0,192a88,88,0,1,1,88-88A88.1,88.1,0,0,1,128,216Zm0-144a56.06,56.06,0,0,0-56,56,8,8,0,0,1-16,0,72.08,72.08,0,0,1,72-72,8,8,0,0,1,0,16Zm72,56a72.08,72.08,0,0,1-72,72,8,8,0,0,1,0-16,56.06,56.06,0,0,0,56-56,8,8,0,0,1,16,0Zm-40,0a32,32,0,1,0-32,32A32,32,0,0,0,160,128Zm-48,0a16,16,0,1,1,16,16A16,16,0,0,1,112,128Z',
    'microphone-stage':  'M168,16A72.07,72.07,0,0,0,96,88a73.29,73.29,0,0,0,.63,9.42L27.12,192.22A15.93,15.93,0,0,0,28.71,213L43,227.29a15.93,15.93,0,0,0,20.78,1.59l94.81-69.53A73.29,73.29,0,0,0,168,160a72,72,0,1,0,0-144Zm56,72a55.72,55.72,0,0,1-11.16,33.52L134.49,43.16A56,56,0,0,1,224,88ZM54.32,216,40,201.68,102.14,117A72.37,72.37,0,0,0,139,153.86ZM112,88a55.67,55.67,0,0,1,11.16-33.51l78.34,78.34A56,56,0,0,1,112,88Zm-2.35,58.34a8,8,0,0,1,0,11.31l-8,8a8,8,0,1,1-11.31-11.31l8-8A8,8,0,0,1,109.67,146.33Z',
    'beer-stein':        'M104,104v80a8,8,0,0,1-16,0V104a8,8,0,0,1,16,0Zm40-8a8,8,0,0,0-8,8v80a8,8,0,0,0,16,0V104A8,8,0,0,0,144,96Zm96,16v64a24,24,0,0,1-24,24H200v8a16,16,0,0,1-16,16H56a16,16,0,0,1-16-16V72c0-30.88,28.71-56,64-56,16.77,0,32.91,5.8,44.82,16H160a40,40,0,0,1,40,40V88h16A24,24,0,0,1,240,112ZM57,64H182.62A24,24,0,0,0,160,48H145.74a8,8,0,0,1-5.53-2.22C131.06,37,117.87,32,104,32,80.82,32,61.43,45.76,57,64ZM184,208V80H56V208H184Zm40-96a8,8,0,0,0-8-8H200v80h16a8,8,0,0,0,8-8Z',
    'music-notes':       'M212.92,17.69a8,8,0,0,0-6.86-1.45l-128,32A8,8,0,0,0,72,56V166.08A36,36,0,1,0,88,196V110.25l112-28v51.83A36,36,0,1,0,216,164V24A8,8,0,0,0,212.92,17.69ZM52,216a20,20,0,1,1,20-20A20,20,0,0,1,52,216ZM88,93.75V62.25l112-28v31.5ZM180,184a20,20,0,1,1,20-20A20,20,0,0,1,180,184Z',
    'book-bookmark':     'M208,24H72A32,32,0,0,0,40,56V224a8,8,0,0,0,8,8H192a8,8,0,0,0,0-16H56a16,16,0,0,1,16-16H208a8,8,0,0,0,8-8V32A8,8,0,0,0,208,24ZM120,40h48v72L148.79,97.6a8,8,0,0,0-9.6,0L120,112Zm80,144H72a31.82,31.82,0,0,0-16,4.29V56A16,16,0,0,1,72,40h32v88a8,8,0,0,0,12.8,6.4L144,114l27.21,20.4A8,8,0,0,0,176,136a8,8,0,0,0,8-8V40h16Z',
    'git-branch':        'M232,64a32,32,0,1,0-40,31v17a8,8,0,0,1-8,8H96a23.84,23.84,0,0,0-8,1.38V95a32,32,0,1,0-16,0v66a32,32,0,1,0,16,0V144a8,8,0,0,1,8-8h88a24,24,0,0,0,24-24V95A32.06,32.06,0,0,0,232,64ZM64,64A16,16,0,1,1,80,80,16,16,0,0,1,64,64ZM96,192a16,16,0,1,1-16-16A16,16,0,0,1,96,192ZM200,80a16,16,0,1,1,16-16A16,16,0,0,1,200,80Z',
    'git-pull-request':  'M104,64A32,32,0,1,0,64,95v66a32,32,0,1,0,16,0V95A32.06,32.06,0,0,0,104,64ZM56,64A16,16,0,1,1,72,80,16,16,0,0,1,56,64ZM88,192a16,16,0,1,1-16-16A16,16,0,0,1,88,192Zm120-31V110.63a23.85,23.85,0,0,0-7-17L163.31,56H192a8,8,0,0,0,0-16H144a8,8,0,0,0-8,8V96a8,8,0,0,0,16,0V67.31L189.66,105a8,8,0,0,1,2.34,5.66V161a32,32,0,1,0,16,0Zm-8,47a16,16,0,1,1,16-16A16,16,0,0,1,200,208Z',
    'git-merge':         'M208,112a32.05,32.05,0,0,0-30.69,23l-42.21-6a8,8,0,0,1-4.95-2.71L94.43,84.55A32,32,0,1,0,72,87v82a32,32,0,1,0,16,0V101.63l30,35a24,24,0,0,0,14.83,8.14l44,6.28A32,32,0,1,0,208,112ZM64,56A16,16,0,1,1,80,72,16,16,0,0,1,64,56ZM96,200a16,16,0,1,1-16-16A16,16,0,0,1,96,200Zm112-40a16,16,0,1,1,16-16A16,16,0,0,1,208,160Z',
    'tag':               'M243.31,136,144,36.69A15.86,15.86,0,0,0,132.69,32H40a8,8,0,0,0-8,8v92.69A15.86,15.86,0,0,0,36.69,144L136,243.31a16,16,0,0,0,22.63,0l84.68-84.68a16,16,0,0,0,0-22.63Zm-96,96L48,132.69V48h84.69L232,147.31ZM96,84A12,12,0,1,1,84,72,12,12,0,0,1,96,84Z',
    'git-fork':          'M224,64a32,32,0,1,0-40,31v17a8,8,0,0,1-8,8H80a8,8,0,0,1-8-8V95a32,32,0,1,0-16,0v17a24,24,0,0,0,24,24h40v25a32,32,0,1,0,16,0V136h40a24,24,0,0,0,24-24V95A32.06,32.06,0,0,0,224,64ZM48,64A16,16,0,1,1,64,80,16,16,0,0,1,48,64Zm96,128a16,16,0,1,1-16-16A16,16,0,0,1,144,192ZM192,80a16,16,0,1,1,16-16A16,16,0,0,1,192,80Z',
    'heartbeat':         'M72,144H32a8,8,0,0,1,0-16H67.72l13.62-20.44a8,8,0,0,1,13.32,0l25.34,38,9.34-14A8,8,0,0,1,136,128h24a8,8,0,0,1,0,16H140.28l-13.62,20.44a8,8,0,0,1-13.32,0L88,126.42l-9.34,14A8,8,0,0,1,72,144ZM178,40c-20.65,0-38.73,8.88-50,23.89C116.73,48.88,98.65,40,78,40a62.07,62.07,0,0,0-62,62c0,.75,0,1.5,0,2.25a8,8,0,1,0,16-.5c0-.58,0-1.17,0-1.75A46.06,46.06,0,0,1,78,56c19.45,0,35.78,10.36,42.6,27a8,8,0,0,0,14.8,0c6.82-16.67,23.15-27,42.6-27a46.06,46.06,0,0,1,46,46c0,53.61-77.76,102.15-96,112.8-10.83-6.31-42.63-26-66.68-52.21a8,8,0,1,0-11.8,10.82c31.17,34,72.93,56.68,74.69,57.63a8,8,0,0,0,7.58,0C136.21,228.66,240,172,240,102A62.07,62.07,0,0,0,178,40Z',
  };

  // Source → [tag, phosphor-icon-name]. Tag is no longer rendered
  // (the icon carries the identity) but kept for any future logging
  // or accessibility hooks.
  const SRC = {
    letterboxd: ['[lb]', 'film-reel'],
    discogs:    ['[dc]', 'vinyl-record'],
    songkick:   ['[sk]', 'microphone-stage'],
    untappd:    ['[ut]', 'beer-stein'],
    strava:     ['[st]', 'heartbeat'],
    aoty:       ['[ao]', 'music-notes'],
    books:      ['[bk]', 'book-bookmark'],
    github:     ['[gh]', 'git-branch'],
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
    span.dataset.source = e.source || '';

    // No text tag — the icon itself carries the source identity (the
    // legend in the meta row up top maps icons → sources).
    const [, iconName] = SRC[e.source] || [, null];
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
      a.textContent = [e.artist, e.title].filter(Boolean).join(' — ');
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

    // Venue + city (songkick).
    if (e.source === 'songkick' && (e.venue || e.city)) {
      const parts = [e.venue, e.city].filter(Boolean).join(' · ');
      const sep = document.createElement('span');
      sep.className = 'sep'; sep.textContent = ' · ';
      const v = document.createElement('span');
      v.className = 'entry__venue';
      v.textContent = parts;
      span.append(sep, v);
    }

    // Brewery (untappd).
    if (e.source === 'untappd' && e.brewery) {
      const sep = document.createElement('span');
      sep.className = 'sep'; sep.textContent = ' · ';
      const v = document.createElement('span');
      v.className = 'entry__venue';
      v.textContent = e.brewery;
      span.append(sep, v);
    }

    // Repo description (github) / activity stats (strava).
    if ((e.source === 'github' || e.source === 'strava') && e.description) {
      const sep = document.createElement('span');
      sep.className = 'sep'; sep.textContent = ' · ';
      const v = document.createElement('span');
      v.className = 'entry__venue';
      v.textContent = e.description;
      span.append(sep, v);
    }

    // Author (books).
    if (e.source === 'books' && e.author) {
      const sep = document.createElement('span');
      sep.className = 'sep'; sep.textContent = ' · ';
      const v = document.createElement('span');
      v.className = 'entry__venue';
      v.textContent = e.author;
      span.append(sep, v);
    }

    // (Letterboxd star rating intentionally not rendered — the date
    // alone tells the story; ratings stay in the JSON in case we
    // want them back.)

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

    // Mark legend buttons whose source has zero entries — they
    // render dimmer + show as "(soon)" on hover so visitors know
    // the source is planned but not live yet.
    const sourceCounts = entries.reduce((m, e) => {
      m[e.source] = (m[e.source] || 0) + 1;
      return m;
    }, {});
    document.querySelectorAll('.meta__filter').forEach((b) => {
      const src = b.dataset.source;
      b.classList.toggle('meta__filter--empty', !sourceCounts[src]);
    });

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

  // Legend filter — click a source in the meta row to highlight just
  // that source's entries. Click the same one again to clear.
  (function initFilter() {
    const log = document.getElementById('js-log');
    if (!log) return;
    const buttons = document.querySelectorAll('.meta__filter');
    function apply(activeSource) {
      log.classList.toggle('is-filtered', !!activeSource);
      buttons.forEach((b) => {
        b.classList.toggle('is-active', b.dataset.source === activeSource);
      });
      document.querySelectorAll('.entry').forEach((entry) => {
        entry.classList.toggle('is-match', activeSource && entry.dataset.source === activeSource);
      });
    }
    buttons.forEach((b) => {
      b.addEventListener('click', () => {
        const src = b.dataset.source;
        const already = b.classList.contains('is-active');
        apply(already ? null : src);
      });
    });
  })();

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
