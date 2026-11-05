'use strict';
// One guide for the meeting console and the standalone project board.
(() => {
  const projectPage = location.pathname === '/projects';
  const routeNames = {meetings:'Провести встречу',projects:'Вести задачи',memory:'План и закрепление',apps:'Другие приложения',about:'О программе'};
  const i18n=window.BlateroI18n;
  const existing = document.getElementById('helpOverlay');
  let host = existing;
  if (!host) {
    host = document.createElement('dialog');
    host.id = 'workspaceGuideDialog';
    host.className = 'workspace-guide-dialog';
    host.setAttribute('aria-labelledby', 'workspaceGuideTitle');
    host.innerHTML = '<button class="guide-close" aria-label="Закрыть обучение">×</button><div class="help-shell"><small class="guide-kicker">РАБОЧЕЕ ПРОСТРАНСТВО</small><h2 id="workspaceGuideTitle">Как пользоваться Blatero</h2><p class="guide-intro">Выберите короткий маршрут. Задачи и знания доступны без записи встречи.</p></div>';
    document.body.append(host);
    host.querySelector('.guide-close').onclick = () => host.close();
  }
  const shell = host.querySelector('.help-shell');
  host.classList.add('workspace-guide');
  const tabs = document.createElement('div');
  tabs.className = 'guide-routes';
  tabs.setAttribute('role', 'tablist');
  tabs.setAttribute('aria-label', 'Маршруты обучения');
  const preference = shell.querySelector('.help-preference');
  if (preference) preference.after(tabs); else shell.append(tabs);
  const panels = {};
  for (const [key, label] of Object.entries(routeNames)) {
    const button = document.createElement('button');
    button.id = 'guide-tab-'+key; button.type='button'; button.textContent=label;
    button.dataset.guideRoute=key; button.setAttribute('role','tab');
    button.dataset.i18n=({meetings:'guideMeetings',projects:'guideProjects',memory:'guideMemory',apps:'otherApps',about:'guideAbout'})[key];
    button.setAttribute('aria-controls','guide-panel-'+key);
    tabs.append(button);
    const panel = document.createElement('section');
    panel.id='guide-panel-'+key; panel.className='guide-panel'; panel.setAttribute('role','tabpanel');
    panel.setAttribute('aria-labelledby',button.id); panel.tabIndex=0;
    panels[key]=panel; shell.append(panel);
  }
  panels.about.innerHTML='<h3>Blatero</h3><p class="guide-note"><span data-i18n="guideAuthor">Автор</span>: <strong>androman</strong></p><div class="guide-actions"><a href="https://androman.pro" target="_blank" rel="noopener noreferrer">androman.pro</a><a href="https://t.me/andromanpro1c" target="_blank" rel="noopener noreferrer">Telegram</a></div><p class="guide-note" data-i18n="guideCodeLicense">Код Blatero — MIT.</p>';
  if (existing) {
    shell.querySelectorAll(':scope > .help-steps, :scope > .help-start-note, :scope > .help-actions, :scope > .help-details').forEach(element => panels.meetings.append(element));
    const note = document.createElement('p'); note.className='guide-note';
    note.textContent='После проверки отчёта откройте «Задачи встречи»: выберите проект и создайте карточку или свяжите запись с существующей задачей.';
    panels.meetings.querySelector('.help-actions').before(note);
  } else {
    panels.meetings.innerHTML='<h3>Встреча: подготовить → проверить → записать → разобрать</h3><p>Выберите роль, цель и материалы. Проверьте микрофон и звук приложения встречи, затем начните запись. После разговора проверьте текст, говорящих и выводы перед созданием DOCX.</p><p class="guide-note">Открытие встречи и её подготовка не запускают запись. Облачные функции требуют разрешения в настройках приватности.</p><a class="guide-primary" href="/?panel=help">Открыть обучение встречам</a><p>В облегчённом отдельном сервере доступны только проекты. Для встреч запустите основную панель Blatero.</p>';
  }
  panels.projects.innerHTML=`<h3>От постановки к проверенному результату</h3>
    <div class="guide-grid">
      <article><b>01 / СУТЬ</b><h4>Назовите результат</h4><p>Выберите проект и создайте задачу. Запишите, что нужно получить, выбранный метод, почему он подходит и следующий шаг.</p></article>
      <article><b>02 / РАБОТА</b><h4>Поручите ведение агенту</h4><p>Агент связывает сессию с карточкой и обновляет решения. Хук фиксирует события сессии; содержательные выводы записывает сам агент.</p></article>
      <article><b>03 / ПРОВЕРКА</b><h4>Проверьте поставку</h4><p>Карточки можно перетаскивать или менять статус в списке. Завершение сессии не закрывает задачу: результат принимается отдельно.</p></article>
      <article><b>04 / ПАМЯТЬ</b><h4>Сохраните основание</h4><p>В карточке находятся знания, источники, проверки и история. Предложения агента подтверждаются отдельно; сведения из истории требуют сверки.</p></article>
    </div>
    <p class="guide-note">«Показать ещё» загружает до 40 карточек только в своей колонке. Предложение проекта по папке или названию встречи ещё не означает сохранённую связь.</p>
    <p class="guide-note">Неактуальную карточку можно закрыть с причиной. Во вкладке «Закрытые» сохранены история и материалы; карточку можно вручную вернуть во входящие или в работу. Закрытие не означает приёмку результата.</p>
    <p class="guide-note">Чтобы проект не занимал место в левой панели, нажмите «×» рядом с названием. Он попадёт в свёрнутую группу «Закрытые проекты», откуда его можно восстановить кнопкой «↶». Задачи проекта сохранят свои статусы.</p>
    <div class="guide-actions"><a class="guide-primary" data-guide-view="board" href="/projects">Открыть доску</a><a data-guide-view="list" href="/projects?view=list">Список задач</a><a data-guide-view="closed" href="/projects?view=closed">Закрытые задачи</a><a data-guide-view="knowledge" href="/projects?view=knowledge">Знания и решения</a>${existing?'<button type="button" id="guideMeetingTasks">Задачи текущей встречи</button>':''}</div>`;
  panels.memory.innerHTML=`<h3>Вернуться к задаче и продолжить с пониманием</h3>
    <p class="guide-note">Начните с «Сегодня»: выберите одну текущую задачу, ответьте на явные вопросы агента и посмотрите ближайшие семь дней. В карточке отметьте важное решение для закрепления — ежедневный экран предложит не больше двух тем. Метод и причина раскрываются после собственного пересказа.</p>
    <div class="guide-grid">
      <article><b>01 / ПЛАН</b><h4>Соберите неделю</h4><p>В общем плане видны встречи, сроки задач и даты статей. Начало и длительность задаются в карточке; пересечения отмечаются отдельно.</p></article>
      <article><b>02 / МАТЕРИАЛЫ</b><h4>Свяжите исходники</h4><p>Выберите встречу или статью Гранки и создайте карточку либо свяжите существующую. Обновление источника сохраняет ваши решения. Гранка читается в одну сторону.</p></article>
      <article><b>03 / ВСПОМНИТЬ</b><h4>Сначала своими словами</h4><p>Вспомните цель, метод и причину до открытия ответа. Затем сверьтесь и оцените себя: не вспомнил — завтра; частично — через 3 дня; помню — через 7 дней.</p></article>
      <article><b>04 / ЭФФЕКТИВНОСТЬ</b><h4>Смотрите на полноту</h4><p>Neon Legion показывает связанные сессии и оценку эквивалента API. Это не стоимость подписки и не измерение вашего рабочего времени.</p></article>
    </div>
    <p class="guide-note"><b>Библиотека</b> объединяет документы, досье задач, решения и обсуждения. Выберите проект, найдите фрагмент, откройте источник и его дату. «Предложение» требует подтверждения; «Нужна перепроверка» означает, что основание изменилось. Обновление работает отдельным фоновым процессом и приостанавливается во время записи встречи. <a data-guide-view="knowledge" href="/projects?view=knowledge">Открыть библиотеку ↗</a></p>
    <p class="guide-note">«Вспомнить» работает без микрофона и модели. Пересказ не сохраняется и не оценивается ИИ; напоминаний пока нет. Тренировка собеседования — отдельный режим с вопросами и оценкой ответа.</p>
    <div class="guide-actions"><a class="guide-primary" data-guide-view="daily" href="/projects?view=daily">Сегодня</a><a data-guide-view="planning" href="/projects?view=planning">Открыть план</a><a data-guide-view="materials" href="/projects?view=materials">Материалы</a><a class="guide-primary" data-guide-view="recall" href="/projects?view=recall">Попробовать вспомнить</a><a data-guide-view="efficiency" href="/projects?view=efficiency">Эффективность</a></div>`;
  shell.insertAdjacentHTML('beforeend','<p class="guide-version">Обучение актуализировано 12.10.2026 · Встречи, проекты, план и знания</p>');
  // Keep the original nodes: app.js binds action handlers before this guide loads.
  // Serializing/restoring innerHTML silently replaced the working buttons.
  const originalPanels=Object.fromEntries(['meetings','projects','memory'].map(key=>[key,[...panels[key].childNodes]]));
  const meetingActions=panels.meetings.querySelector('.help-actions');
  function translatedGuide() {
    if (!i18n) return;
    const t=i18n.t;
    Object.values(panels).forEach(panel=>{panel.lang=i18n.language;});
    panels.apps.innerHTML=`<h3>${t('appsTitle')}</h3><p class="guide-note">${t('appsNote')}</p><div class="guide-grid">
      <article><b>01 / NEON LEGION</b><h4>Neon Legion</h4><p>${t('neonAbout')}</p><a href="https://github.com/andromanpro/neon-legion" target="_blank" rel="noopener noreferrer">${t('learn')}</a></article>
      <article><b>02 / GRANKA</b><h4>Гранка / Granka</h4><p>${t('grankaAbout')}</p><a href="https://github.com/andromanpro/granka" target="_blank" rel="noopener noreferrer">${t('learn')}</a></article>
      <article><b>03 / MOTIVELIUM</b><h4>Мотивелиум / Motivelium</h4><p>${t('motiveliumAbout')}</p></article></div><p class="guide-note">${t('setup')}</p>`;
    if(i18n.language==='en') {
      panels.meetings.innerHTML=`<h3>${t('guideMeetTitle')}</h3><ol>${['guideMeet1','guideMeet2','guideMeet3','guideMeet4'].map(k=>`<li>${t(k)}</li>`).join('')}</ol>`;
      panels.projects.innerHTML=`<h3>${t('guideTasksTitle')}</h3><p>${t('guideTasksText')}</p><a href="/projects">${t('board')} ↗</a>`;
      panels.memory.innerHTML=`<h3>${t('guidePlanTitle')}</h3><p>${t('guidePlanText')}</p><a href="/projects?view=planning">${t('planning')} ↗</a>`;
      if(meetingActions)panels.meetings.append(meetingActions);
    } else for(const key of Object.keys(originalPanels))panels[key].replaceChildren(...originalPanels[key]);
    const title=shell.querySelector('#workspaceGuideTitle');if(title)title.dataset.i18n='guideTitle';
    const intro=shell.querySelector('.guide-intro');if(intro)intro.dataset.i18n='guideIntro';
    const kicker=shell.querySelector('.guide-kicker');if(kicker)kicker.dataset.i18n='guideKicker';
    i18n.apply(shell);
  }
  document.addEventListener('blatero:language',translatedGuide);
  translatedGuide();
  function select(route, focus=false) {
    if (!panels[route]) route=projectPage?'projects':'meetings';
    Object.entries(panels).forEach(([key,panel])=>{const active=key===route;panel.hidden=!active;const button=tabs.querySelector(`[data-guide-route="${key}"]`);button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;if(active&&focus)button.focus();});
  }
  tabs.addEventListener('click',event=>{const button=event.target.closest('[data-guide-route]');if(button)select(button.dataset.guideRoute);});
  tabs.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();const keys=Object.keys(panels);let index=keys.indexOf(event.target.dataset.guideRoute);
    index=event.key==='Home'?0:event.key==='End'?keys.length-1:(index+(event.key==='ArrowRight'?1:-1)+keys.length)%keys.length;
    select(keys[index],true);
  });
  host.addEventListener('click',event=>{if(event.target.closest('#guideMeetingTasks')){host.classList.remove('show');document.getElementById('meetingWorkButton')?.click();}});
  function updateLinks() {
    const project=document.getElementById('projectFilter')?.value;
    shell.querySelectorAll('[data-guide-view]').forEach(link=>{
      const search=new URLSearchParams();if(link.dataset.guideView!=='board')search.set('view',link.dataset.guideView);if(project)search.set('project',project);
      link.href='/projects'+(search.size?'?'+search:'');
    });
  }
  const entry=document.createElement('button');entry.type='button';entry.id='workspaceHelp';entry.textContent='Помощь';entry.dataset.i18n='help';entry.setAttribute('aria-label','Обучение работе с Blatero');
  document.querySelector('.space-actions')?.prepend(entry);
  entry.dataset.i18nAria='guideTitle';
  const close=host.querySelector('.guide-close');if(close)close.dataset.i18nAria='close';
  i18n?.apply();
  entry.onclick=()=>{updateLinks();if(existing){openHelp();}else{host.showModal();}};
  select(projectPage?'projects':'meetings');
  const params=new URLSearchParams(location.search);
  if(existing&&params.get('panel')==='help'){select(params.get('guide')||'meetings');openHelp();}
})();
