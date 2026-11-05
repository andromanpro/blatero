'use strict';
// Shared visual projection only: no recording, provider calls or microphone access.
(() => {
  const marks = new Set();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let session = '', request = '', phase = '', voice = 0, lastLevel = 0;
  let expiry = null, readyTimer = null, ready = false, serial = 0, source = null;
  const now = () => performance.now();
  const level = value => typeof value === 'number' && Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
  const state = () => phase === 'running' ? 'thinking' : ready ? 'ready' : voice > 0 ? 'listening' : 'idle';
  function draw() {
    const current = state();
    const motion = document.documentElement.dataset.motion !== 'off' && !reduced.matches && !document.hidden;
    for (const mark of marks) {
      mark.dataset.brandState = current;
      mark.dataset.brandMotion = motion ? 'on' : 'off';
      mark.style.setProperty('--brand-voice', String(voice));
      mark.style.setProperty('--brand-x', String(1 + .12 * voice));
      mark.style.setProperty('--brand-y', String(1 - .10 * voice));
      mark.style.setProperty('--brand-skew', `${-4 * voice}deg`);
      mark.style.setProperty('--brand-wave', String(.9 + .18 * voice));
      mark.title = {idle:'Blatero',listening:'Blatero — поступает звук',thinking:'Blatero — готовит подсказку',ready:'Blatero — подсказка готова'}[current];
    }
  }
  function silence() {clearTimeout(expiry); expiry = null; voice = 0; draw();}
  function reset() {
    clearTimeout(readyTimer); readyTimer = null; ready = false;
    request = ''; phase = ''; silence();
  }
  function activity(message, initial = false) {
    if (!session || message?.session !== session || !message.request_id) return;
    if (message.phase === 'running') {
      clearTimeout(readyTimer); ready = false;
      request = message.request_id; phase = 'running'; draw();
    } else if (!initial && request === message.request_id && phase === 'running') {
      phase = message.phase; ready = phase === 'done';
      if (ready) readyTimer = setTimeout(() => {
        ready = false; if (now() - lastLevel > 1500) voice = 0; draw();
      }, 900);
      draw();
    }
  }
  function message(message) {
    if (!message || typeof message !== 'object') return;
    if (message.type === 'init') {
      reset(); session = String(message.current_dir || '');
      // Reconnecting to an active job resumes it; historical completion is not a new event.
      if (message.ai_activity?.phase === 'running') activity(message.ai_activity, true);
    } else if (message.type === 'ai_activity') activity(message);
    else if (message.type === 'levels') {
      if (!session || (message.session && message.session !== session)) return;
      if (!message.live || message.rec === false || message.healthy === false || message.error) {silence(); return;}
      const peak = Math.max(level(message.me), level(message.guest));
      voice = peak < .045 ? 0 : Math.sqrt((peak - .045) / .955);
      lastLevel = now(); clearTimeout(expiry);
      expiry = setTimeout(silence, 1500); draw();
    }
  }
  async function mount(mark) {
    marks.add(mark); draw();
    try {
      source ??= fetch('/assets/blatero-mark.svg').then(response => {
        if (!response.ok) throw Error('Brand asset unavailable');
        return response.text();
      }).catch(error => {source = null; throw error;});
      const text = await source;
      const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
      if (svg.localName !== 'svg') throw Error('Invalid brand asset');
      const prefix = `blatero-e-${++serial}-`;
      const ids = new Map([...svg.querySelectorAll('[id]')].map(node => [node.id, prefix + node.id]));
      for (const node of [svg, ...svg.querySelectorAll('*')]) {
        for (const attr of [...node.attributes]) {
          if (attr.name === 'id') node.id = ids.get(attr.value);
          else for (const [id, unique] of ids) {
            if (attr.value === '#' + id) node.setAttribute(attr.name, '#' + unique);
            if (attr.value === `url(#${id})`) node.setAttribute(attr.name, `url(#${unique})`);
          }
        }
      }
      svg.setAttribute('aria-hidden', 'true'); svg.setAttribute('focusable', 'false');
      mark.replaceChildren(document.importNode(svg, true)); draw();
    } catch { /* The static image and wordmark remain usable if inline loading fails. */ }
  }
  window.BlateroBrand = Object.freeze({mount, message});
  window.addEventListener('blatero:brand-message', event => message(event.detail));
  window.addEventListener('blatero:connection', event => {if (!event.detail?.connected) {reset(); session = '';}});
  document.addEventListener('workspace:motion', draw);
  document.addEventListener('visibilitychange', () => {if (document.hidden || now() - lastLevel > 1500) silence(); else draw();});
  reduced.addEventListener('change', draw);
})();
