'use strict';
// A visual guide only. Never click the highlighted controls or use the API.
(() => {
  const byId = id => document.getElementById(id);
  const dialog = byId('meetingTour'), start = byId('helpTourStart');
  const i18n = window.BlateroI18n;
  if (!dialog || !start || !i18n) return;
  const {t} = i18n;
  i18n.register({
    tourNext: ['Далее', 'Next'], tourDone: ['Готово', 'Done'],
    tourProgress: ['Шаг {step} из {total}', 'Step {step} of {total}'],
    tourCompact: ['Эта кнопка скрыта в режиме «Только главное». После тура вернитесь к обычному виду.',
      'This control is hidden in Essentials only. Return to the normal view after the tour.'],
    tourReading: ['Открыты результаты встречи. Кнопки записи доступны на вкладке «Встреча», а проверка звука — при подготовке новой встречи.',
      'You are viewing meeting results. Find recording controls on the Meeting tab and audio checks when preparing a new meeting.'],
    tourReadingAudio: ['Для проверки одного микрофона выйдите из тура и откройте «Инструменты → Настройки → Звук и речь → Проверить микрофон». Новая встреча не нужна.',
      'To check just the microphone, exit the tour and open Tools → Settings → Audio and speech → Test microphone. No new meeting is needed.'],
    tourHidden: ['Кнопка сейчас скрыта. Ищите её на верхней панели встречи в обычном виде.',
      'This control is currently hidden. Look for it in the meeting toolbar in normal view.'],
    tourSettings: ['Настройки', 'Settings'],
    tourSettingsText: ['Откройте «Инструменты → Настройки», чтобы выбрать микрофон, звук встречи и подключение ИИ.',
      'Open Tools → Settings to choose the microphone, meeting audio and AI connection.'],
    tourMeeting: ['Новая встреча', 'New meeting'],
    tourMeetingText: ['Укажите тему или выберите проект и задачи. Подготовка встречи не запускает запись.',
      'Enter a topic or choose a project and tasks. Preparing a meeting does not start recording.'],
    tourCheck: ['Проверить всё', 'Check all'],
    tourCheckText: ['До встречи проверьте микрофон, звук собеседников, распознавание и ИИ.',
      'Before the meeting, check your microphone, meeting audio, speech recognition and AI.'],
    tourRecord: ['Запись и подсказки', 'Recording and hints'],
    tourRecordText: ['«Запись» запускает захват после подтверждения. «Подсказки» помогают по ходу разговора.',
      'Record starts capture after confirmation. Hints help you during the conversation.'],
    tourReport: ['Отчёт и результаты', 'Report and results'],
    tourReportText: ['После остановки проверьте выводы и сохраните отчёт. Готовые файлы ищите в «Результатах».',
      'After stopping, review the conclusions and save a report. Find the finished files under Results.'],
  });

  const steps = [
    ['tourSettings', ['.header-more > summary']],
    ['tourMeeting', ['#setupBtn']],
    ['tourCheck', ['#preflightQuick']],
    ['tourRecord', ['#recbtn', '#pulse']],
    ['tourReport', ['#report', '#outputTools > summary']],
  ];
  const title = byId('meetingTourTitle'), card = dialog.querySelector('.meeting-tour-card');
  const next = byId('meetingTourNext'), back = byId('meetingTourBack');
  const intro = byId('helpTourIntro'), busy = byId('helpTourBusy'), layoutNote = byId('meetingTourLayoutNote');
  const mask = byId('meetingTourMask'), rings = byId('meetingTourRings');
  const preference = 'blatero.meetingTourOffered.v1';
  let offered = false, index = 0, frame = 0, context = '';
  try { offered = localStorage.getItem(preference) === '1'; } catch {}

  function rememberOffer() {
    offered = true;
    try { localStorage.setItem(preference, '1'); } catch {}
  }

  const meetingKey = init => [init?.current_dir, init?.session_generation, init?.server_epoch].join('/');
  function syncEntry(recording) {
    start.disabled = recording;
    busy.hidden = !recording;
    if (recording) intro.hidden = true;
  }
  document.addEventListener('blatero:help-opened', event => {
    syncEntry(!!recLive);
    intro.hidden = !event.detail.automatic || offered || !!recLive;
    if (!intro.hidden) rememberOffer();
  });

  function highlight() {
    if (!dialog.open) return;
    const viewport = dialog.getBoundingClientRect();
    const {width, height} = viewport;
    const boxFor = selector => {
      const target = document.querySelector(selector);
      if (!target?.getClientRects().length || getComputedStyle(target).visibility !== 'visible') return null;
      const bounds = target.getBoundingClientRect();
      const x = Math.max(0, bounds.left - viewport.left - 3);
      const y = Math.max(0, bounds.top - viewport.top - 3);
      const right = Math.min(width, bounds.right - viewport.left + 3);
      const bottom = Math.min(height, bounds.bottom - viewport.top + 3);
      return right - x > 8 && bottom - y > 8 ? {x,y,right,bottom} : null;
    };
    const targets = steps[index][1].map(selector => boxFor(selector)
      || (selector === '#setupBtn' && boxFor('#meetingReadNew')) || null);
    const boxes = targets.filter(Boolean);
    const compact = !boxes.length && document.body.classList.contains('meeting-minimal');
    const reading = !boxes.length && document.body.matches('.meeting-reading, .meeting-post');
    const fallback = compact ? boxFor('#minimalToggle') : reading && boxFor(
      index === 2 ? '.header-more > summary' : index === 3 ? '#meetingViewTabs [data-meeting-view="live"]' : '#meetingReadNew');
    if (fallback) boxes.push(fallback);
    layoutNote.hidden = targets.every(Boolean);
    if (!layoutNote.hidden) layoutNote.textContent = t(compact ? 'tourCompact' : reading ? (index === 2 ? 'tourReadingAudio' : 'tourReading') : 'tourHidden');
    let path = `M0 0H${width}V${height}H0Z`;
    rings.replaceChildren(...boxes.map(({x,y,right,bottom}) => {
      path += ` M${x} ${y}H${right}V${bottom}H${x}Z`;
      const rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
      for (const [name,value] of Object.entries({x,y,width:right-x,height:bottom-y,rx:5}))
        rect.setAttribute(name,value);
      return rect;
    }));
    mask.setAttribute('d',path);
    const left = boxes.length ? Math.min(...boxes.map(b => b.x)) : width / 2 - card.offsetWidth / 2;
    const top = boxes.length ? Math.min(...boxes.map(b => b.y)) : 12;
    const bottom = boxes.length ? Math.max(...boxes.map(b => b.bottom)) : 0;
    const {offsetWidth:w,offsetHeight:h} = card;
    const y = bottom + h + 24 <= height ? bottom + 12
      : top - h - 12 >= 12 ? top - h - 12 : height - h - 12;
    dialog.style.setProperty('--tour-x', `${Math.max(12,Math.min(left,width-w-12))}px`);
    dialog.style.setProperty('--tour-y', `${Math.max(12,y)}px`);
  }

  function draw(focus = false) {
    if (!dialog.open) return;
    const [key] = steps[index];
    dialog.lang = i18n.language;
    title.textContent = t(key);
    byId('meetingTourText').textContent = t(key+'Text');
    byId('meetingTourProgress').textContent = t('tourProgress',{step:index+1,total:steps.length});
    next.textContent = t(index === steps.length - 1 ? 'tourDone' : 'tourNext');
    back.disabled = index === 0;
    highlight();
    if (focus) title.focus({preventScroll:true});
  }

  function refreshPosition() {
    if (!dialog.open || frame) return;
    frame = requestAnimationFrame(() => { frame = 0; highlight(); });
  }
  const sizing = new ResizeObserver(refreshPosition);
  const otherModal = () => document.querySelector('dialog[open]:not(#meetingTour), .overlay.show');
  const dialogs = new MutationObserver(() => { if (otherModal()) dismiss(false); });
  function dismiss(restore = true) {
    if (!dialog.open) return;
    sizing.disconnect();
    dialogs.disconnect();
    cancelAnimationFrame(frame);
    frame = 0;
    dialog.close();
    if (restore) {
      const target = ['#workspaceHelp','.header-more > summary','#minimalToggle'].map(
        selector => document.querySelector(selector)).find(node => node?.getClientRects().length);
      target?.focus({preventScroll:true});
    }
  }
  start.addEventListener('click', () => {
    if (recLive || dialog.open || document.querySelector('dialog[open], .overlay.show:not(#helpOverlay)')) return;
    context = meetingKey(currentInit);
    rememberOffer();
    intro.hidden = true;
    byId('helpOverlay').classList.remove('show');
    index = 0;
    dialog.showModal();
    draw(true);
    for (const node of [dialog, card, document.querySelector('.quickbar'), document.querySelector('.app-header')])
      if (node) sizing.observe(node);
    for (const node of document.querySelectorAll('dialog:not(#meetingTour), .overlay'))
      dialogs.observe(node, {attributes:true,attributeFilter:['class','open']});
  });
  byId('meetingTourExit').onclick = () => dismiss();
  next.onclick = () => { if (index + 1 === steps.length) dismiss(); else { index++; draw(true); } };
  back.onclick = () => { if (index) { index--; draw(true); } };
  dialog.addEventListener('cancel', event => { event.preventDefault(); dismiss(); });
  dialog.addEventListener('keydown', event => {
    event.stopPropagation();
    if (event.key !== 'Tab') return;
    const first = byId('meetingTourExit');
    if (!event.shiftKey && event.target === next) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && (event.target === first || event.target === title)) {
      event.preventDefault();
      next.focus();
    }
  });
  window.addEventListener('resize', refreshPosition);
  window.addEventListener('scroll', refreshPosition, {capture:true,passive:true});
  document.addEventListener('blatero:language', () => draw());
  document.addEventListener('blatero:meeting', event => {
    const recording = !!event.detail.rec_running;
    syncEntry(recording);
    if (recording || context !== meetingKey(event.detail)) dismiss(false);
  });
  window.addEventListener('blatero:training-levels', () => {
    syncEntry(!!recLive);
    if (recLive) dismiss(false);
  });
})();
