/* drewroper.com — landing page interactions
   - Live clock in topbar
   - Footer year stamp
   - Mouse parallax for the z-space logo stage
   Keep it small, vanilla, and respectful of motion preferences. */

(() => {
  // -- Live clock ---------------------------------------------------------
  const clock = document.getElementById('js-clock');
  if (clock) {
    const tick = () => {
      const now = new Date();
      const time = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      });
      const tz = now
        .toLocaleTimeString('en-US', { timeZoneName: 'short' })
        .split(' ').pop();
      clock.textContent = `${time} ${tz}`;
    };
    tick();
    setInterval(tick, 30 * 1000);
  }

  // -- Year stamp ---------------------------------------------------------
  const year = document.getElementById('js-year');
  if (year) year.textContent = String(new Date().getFullYear());

  // -- Z-space mouse parallax --------------------------------------------
  const stage = document.getElementById('js-zstage');
  const camera = document.getElementById('js-zcamera');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine   = window.matchMedia('(pointer: fine)').matches;

  if (stage && camera && fine && !reduce) {
    let raf = 0;
    let tx = 0, ty = 0; // target
    let cx = 0, cy = 0; // current

    const onMove = (e) => {
      const rect = stage.getBoundingClientRect();
      tx = ((e.clientX - rect.left) / rect.width  - 0.5) * 2;
      ty = ((e.clientY - rect.top)  / rect.height - 0.5) * 2;
      if (!raf) raf = requestAnimationFrame(loop);
    };

    const onLeave = () => {
      tx = 0; ty = 0;
      if (!raf) raf = requestAnimationFrame(loop);
    };

    const loop = () => {
      cx += (tx - cx) * 0.08;
      cy += (ty - cy) * 0.08;

      stage.style.setProperty('--mx', cx.toFixed(3));
      stage.style.setProperty('--my', cy.toFixed(3));
      camera.style.transform =
        `rotateX(${6 - cy * 3}deg) rotateY(${cx * 4}deg)`;

      if (Math.abs(tx - cx) > 0.001 || Math.abs(ty - cy) > 0.001) {
        raf = requestAnimationFrame(loop);
      } else {
        raf = 0;
      }
    };

    stage.addEventListener('mousemove', onMove, { passive: true });
    stage.addEventListener('mouseleave', onLeave, { passive: true });
  }

  // -- Tiny console signature -- because microcopy --
  if (typeof console !== 'undefined' && console.log) {
    const css = [
      'font-family: serif',
      'font-size: 14px',
      'font-style: italic',
      'color: #c8a978',
      'padding: 4px 0'
    ].join(';');
    console.log('%cHello, curious one. — Drew', css);
  }
})();
