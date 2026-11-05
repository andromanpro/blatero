'use strict';
// Presentation only: no writes to cards, sources, session bindings or acceptance.
(() => {
  const root = document.documentElement;
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  const values = new Map();
  const entered = new Set();
  const seenElements = new WeakSet();
  const pending = new Set();
  const tweens = new Map();
  let pointerFrame = 0;
  let decorateFrame = 0;
  let previousScope = '';
  const views = {
    daily: ['00 / TODAY', 'С чего продолжим сегодня', 'Один фокус · решения · ближайший план · память'],
    board: ['01 / WORKFLOW', 'От замысла к результату', 'Перетаскивайте карточки между колонками'],
    planning: ['02 / TIMELINE', 'Время для важного', 'Встречи, работа и публикации в одном плане'],
    materials: ['03 / SOURCES', 'У каждой задачи есть основание', 'Встречи · договорённости · статьи'],
    list: ['04 / INDEX', 'Весь объём перед глазами', 'Статус, срок и следующий шаг'],
    knowledge: ['05 / KNOWLEDGE', 'Библиотека общего контекста', 'Документы · задачи · решения · история обсуждений'],
    recall: ['06 / RECALL', 'Вспомнить. Закрепить. Продолжить.', 'Сначала свой ответ, затем подсказка'],
    efficiency: ['07 / IMPACT', 'Результат и затраты', 'Приёмка и связанные сессии Neon Legion'],
    closed: ['08 / HISTORY', 'Можно вернуться к любой задаче', 'Причина закрытия · сохранённая история · ручное восстановление'],
  };
  const laneColors = ['#93a9bb', 'var(--cyan)', 'var(--warning)', '#c3a4ff', 'var(--accent)', '#72879a'];

  function enabled() { return root.dataset.motion !== 'off'; }
  document.addEventListener('workspace:motion', event => {
    if(event.detail.enabled)return;
    tweens.forEach((frame, element)=>{cancelAnimationFrame(frame);projectValue(element,element.dataset.total);});
    tweens.clear();
  });

  function clock() {
    const now = new Date();
    const time = document.querySelector('#workspaceClock');
    time.dateTime = now.toISOString();
    projectLabel(time,'{time} / МСК',()=>({time:now.toLocaleTimeString(window.BlateroI18n?.locale||'ru-RU',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'})}));
  }
  clock();
  setInterval(() => { if (!document.hidden) clock(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) clock(); });

  function countTo(element, target, key) {
    element.dataset.total = target;
    const from = values.get(key) ?? 0;
    values.set(key, target);
    if (!enabled() || from === target) return;
    const started = performance.now();
    function tick(now) {
      if (!element.isConnected) { tweens.delete(element); return; }
      const progress = Math.min(1, (now - started) / 650);
      projectValue(element,Math.round(from + (target - from) * (1 - (1 - progress) ** 3)));
      if (progress < 1) tweens.set(element, requestAnimationFrame(tick));
      else tweens.delete(element);
    }
    tweens.set(element, requestAnimationFrame(tick));
  }

  function updateChrome(tasks, currentView) {
    const project = document.querySelector('#projectFilter').value;
    const title = document.querySelector('#workspaceTitle');
    const name = state.projects.find(p => p.id === project)?.name;
    const special = {__unbound:'Разобрать привязку', __general:'Общие и личные вопросы'};
    if (name || special[project]) {
      if(name)projectValue(title,name);else projectLabel(title,special[project]);
      title.classList.add('project-selected');
    } else {
      title.innerHTML = `${projectText("Вся работа.")} <em>${projectText("В поле зрения.")}</em>`;
      title.classList.remove('project-selected');
    }
    const [code, caption, hint] = views[currentView] || views.board;
    projectValue(document.querySelector('#viewCode'),code);
    projectLabel(document.querySelector('#viewTitle'),caption);
    projectLabel(document.querySelector('#viewHint'),hint);
    const history = document.querySelector('.history-notice');
    history.hidden = !state.import_summary?.session_count;
    const count = state.import_summary?.session_count || 0;
    const general = new Set((state.triage || []).filter(t => t.kind === 'general').map(t => t.work_item_id));
    const unbound = state.tasks.filter(t => !t.project_id && !general.has(t.id)).length;
    projectLabel(document.querySelector('#historySummary'),()=>({source:"{p0} сессий в памяти{p1}",values:{p0:count.toLocaleString(window.BlateroI18n?.locale||'ru-RU'),p1:unbound ? ' · '+unbound+projectUi(" привязок нужно уточнить") : ''}}));
    const spectrum = document.querySelector('#workSpectrum');
    spectrum.replaceChildren(...Object.keys(labels).map((status, index) => {
      const segment = document.createElement('i');
      segment.style.flexGrow = tasks.filter(t => t.status === status).length;
      segment.style.setProperty('--lane', laneColors[index]);
      return segment;
    }));
    document.querySelectorAll('.overview-card').forEach((card, index) => {
      card.dataset.index = '0' + (index + 1);
      const strong = card.querySelector('strong');
      countTo(strong, Number(strong.textContent), index);
    });
    const scope = project + '/' + currentView;
    if (previousScope !== scope && enabled()) {
      const content = document.querySelector('#content');
      content.classList.remove('view-enter');
      void content.offsetWidth;
      content.classList.add('view-enter');
    }
    previousScope = scope;
  }
  document.addEventListener('projects:render', event => {
    requestAnimationFrame(() => updateChrome(event.detail.tasks, event.detail.view));
  });

  const observer = new IntersectionObserver(entries => {
    entries.forEach(({target, isIntersecting}) => {
      if (!isIntersecting) return;
      observer.unobserve(target); pending.delete(target);
      if (entered.has(target.dataset.drag)) return;
      entered.add(target.dataset.drag);
      if (enabled()) {
        target.style.setProperty('--enter-delay', Math.min(4, [...target.parentNode.querySelectorAll('.card')].indexOf(target)) * 45 + 'ms');
        target.classList.add('appear');
        target.addEventListener('animationend', () => target.classList.remove('appear'), {once:true});
      }
    });
  }, {threshold:0.03});
  function decorate() {
    decorateFrame = 0;
    pending.forEach(element => { if (!element.isConnected) { observer.unobserve(element); pending.delete(element); } });
    document.querySelectorAll('.card[data-drag]').forEach(card => {
      if (seenElements.has(card)) return;
      seenElements.add(card);
      observer.observe(card); pending.add(card);
    });
  }
  new MutationObserver(() => {
    if (!decorateFrame) decorateFrame = requestAnimationFrame(decorate);
  }).observe(document.querySelector('#content'), {childList:true});
  document.addEventListener('pointermove', event => {
    if (!enabled() || !finePointer.matches || pointerFrame) return;
    const card = event.target.closest('.card');
    if (!card) return;
    pointerFrame = requestAnimationFrame(() => {
      pointerFrame = 0;
      const rect = card.getBoundingClientRect();
      card.style.setProperty('--pointer-x', event.clientX - rect.left + 'px');
      card.style.setProperty('--pointer-y', event.clientY - rect.top + 'px');
    });
  }, {passive:true});
  decorate();
  if (state.tasks.length) updateChrome(filtered(), view);
})();
