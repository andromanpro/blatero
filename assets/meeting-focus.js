'use strict';
// Meeting-only controls. Layout preferences never change capture or session data.
(() => {
  const byId = id => document.getElementById(id);
  const primary = document.querySelector('.header-primary');
  const toggle = document.createElement('button');
  toggle.id = 'minimalToggle'; toggle.type = 'button';
  meetingAttr(toggle,'title','Скрыть вспомогательные панели, оставить команды и подсказки');
  primary.append(toggle);
  function minimal(enabled) {
    document.body.classList.toggle('meeting-minimal', enabled);
    meetingLabel(toggle,enabled ? '↗ Обычный вид' : '↙ Только главное');
    toggle.setAttribute('aria-pressed', String(enabled));
    uiPreference('minimalMode', enabled ? '1' : '0');
  }
  toggle.onclick = () => minimal(!document.body.classList.contains('meeting-minimal'));
  minimal(uiPreference('minimalMode') === '1');

  const toolbar = document.createElement('div'); toolbar.className = 'hint-toolbar';
  toolbar.innerHTML = '<span class="hint-toolbar-label">Подсказки</span><div class="hint-size" role="group" aria-label="Размер текста подсказок"><button id="hintSmaller" type="button" aria-label="Уменьшить текст подсказок">A−</button><button id="hintSizeReset" type="button" title="Вернуть обычный размер">100%</button><button id="hintLarger" type="button" aria-label="Увеличить текст подсказок">A+</button></div><span id="aiActivity" role="status" aria-live="polite" aria-atomic="true">ИИ · ожидание запроса</span>';
  byId('hintzone').prepend(toolbar);
  window.BlateroMeetingI18n?.bindStatic(toolbar);
  const modelBadge = document.createElement('span'); modelBadge.id = 'aiModel';
  modelBadge.className = 'hint-model'; toolbar.insertBefore(modelBadge, byId('aiActivity'));
  let studioDetail=null;
  function showModel(info = currentInit?.llm_connection) {
    if(studioDetail?.meetingType==='тренировка'&&studioDetail.mode!=='personal'
        &&currentInit?.config?.scene_coach_route==='openrouter_flash'){
      meetingLabel(modelBadge,'Подсказки студии · DeepSeek V4 Flash · OpenRouter');
      meetingAttr(modelBadge,'title','Отдельный быстрый маршрут студии. Основная модель и голоса не меняются.');return;
    }
    if(info?.model_source==='cli_last_observed')meetingLabel(modelBadge,'Codex · авто · последняя: {model}',{model:info.model});
    else if(info?.model_source==='cli_auto')meetingLabel(modelBadge,'Codex · авто · модель уточняется');
    else modelBadge.textContent=info?.model_label || meetingUi('Модель ИИ · уточняется');
    meetingAttr(modelBadge,'title',info?.model_source === 'cli_last_observed'
      ? 'Codex выбирает модель автоматически. Показана модель из заголовка последнего запуска; усилие рассуждения low.'
      : 'Модель подсказок. Для Codex она подтверждается заголовком ответа CLI.');
  }
  showModel();
  window.addEventListener('blatero:training-state',event=>{studioDetail=event.detail;showModel();});
  let hintScale = 100;
  function font(value) {
    const parsed = Number(value);
    hintScale = Number.isFinite(parsed) ? Math.max(80, Math.min(180, parsed)) : 100;
    document.documentElement.style.setProperty('--hint-scale', hintScale / 100);
    byId('hintSizeReset').textContent = hintScale + '%';
    meetingAttr(byId('hintSizeReset'),'aria-label','Размер подсказок {count}%. Сбросить до 100%',{count:hintScale});
    byId('hintSmaller').disabled = hintScale <= 80;
    byId('hintLarger').disabled = hintScale >= 180;
    uiPreference('hintScale', String(hintScale));
  }
  font(uiPreference('hintScale') || 100);
  byId('hintSmaller').onclick = () => font(hintScale - 10);
  byId('hintLarger').onclick = () => font(hintScale + 10);
  byId('hintSizeReset').onclick = () => font(100);

  // Permanent settings homes preserve handlers without moving toolbar nodes.
  byId('contourSwitch').hidden = true;

  let activity = null, clock = null;
  function elapsedLabel(seconds) {
    const value = Math.max(0, Math.floor(seconds));
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
  }
  function drawActivity() {
    if (!activity) return;
    const elapsed = activity.elapsed + (activity.phase === 'running' ? (performance.now() - activity.received) / 1000 : 0);
    byId('aiElapsed').textContent = elapsedLabel(elapsed);
    if (activity.phase === 'running') {
      const connected = ws?.readyState === WebSocket.OPEN;
      meetingLabel(byId('aiActivity').querySelector('span'),connected ? 'Запрос принят · ИИ работает ' : 'Связь потеряна · запрос отправлен ');
    }
  }
  function showActivity(message) {
    if (message && message.session !== currentInit?.current_dir) return;
    if (message?.operation_status && message.operation_status.session_generation !== currentInit?.session_generation) return;
    if (message && message.phase !== 'running' && activity && message.request_id !== activity.request_id) return;
    clearInterval(clock); clock = null; activity = null;
    const element = byId('aiActivity'); element.classList.remove('working');
    if (!message) { meetingLabel(element,'ИИ · ожидание запроса');meetingAttr(element,'aria-label','ИИ · ожидание запроса'); return; }
    // The activity container now has children; do not let an old idle binding
    // replace them on a later language switch.
    window.BlateroMeetingI18n?.forget(element);
    const elapsed = Number(message.elapsed);
    activity = {...message, elapsed:Number.isFinite(elapsed) ? Math.max(0, elapsed) : 0, received:performance.now()};
    const running = message.phase === 'running';
    element.classList.toggle('working', running);
    element.replaceChildren();
    const label = document.createElement('span');
    const unknown = message.operation_status?.state === 'outcome_unknown';
    const labelSource = running ? 'Запрос принят · ИИ работает ' : unknown ? 'ИИ · результат запроса неизвестен после ' : message.phase === 'done' ? 'ИИ · готово за ' : message.phase === 'error' ? 'ИИ · ошибка через ' : 'ИИ · ожидание прервано после ';
    meetingLabel(label,labelSource);
    const timer = document.createElement('span'); timer.id = 'aiElapsed';
    // Seconds update visually, without announcing every tick to a screen reader.
    timer.setAttribute('aria-hidden', 'true'); element.append(label, timer);
    meetingAttr(element,'aria-label','{text} · {time}',()=>({text:meetingUi(labelSource),time:elapsedLabel(Number.isFinite(elapsed)?elapsed:0)}));
    drawActivity();
    if (running) clock = setInterval(drawActivity, 1000);
  }

  const dialog = document.createElement('dialog'); dialog.id = 'quickMeetingDialog';
  dialog.setAttribute('aria-labelledby', 'quickMeetingTitle');
  dialog.innerHTML = '<form id="quickMeetingForm"><div class="quick-meeting-heading"><h2 id="quickMeetingTitle">Новая встреча за один шаг</h2><button id="quickMeetingClose" type="button" aria-label="Закрыть">×</button></div><label>Тема встречи<input id="quickMeetingTopic" required maxlength="200" placeholder="Например: запуск печати этикеток"></label><label>Формат<select id="quickMeetingType"><option value="встреча">Рабочая встреча</option><option value="консалтинг">Консультация</option><option value="собеседование">Я провожу интервью</option></select></label><label>Что обсудить · необязательно<textarea id="quickMeetingBrief" maxlength="100000" rows="3"></textarea></label><label id="quickMeetingTaskRow" hidden><input type="checkbox" id="quickMeetingLink" checked> Связать встречу с выбранной задачей</label><p>Создаётся рабочая встреча. Запись и ИИ-подготовка не запускаются. Папку и материалы можно добавить позже.</p><p id="quickMeetingStatus" role="status"></p><div class="quick-meeting-actions"><button type="button" id="quickMeetingWizard">Подробный мастер</button><button type="button" id="quickMeetingRetryLink" hidden>Повторить только привязку</button><button class="primary" id="quickMeetingCreate" type="submit">Создать и открыть</button></div></form>';
  document.body.append(dialog);
  byId('quickMeetingTitle').textContent = wizardUi('Подготовить встречу');
  byId('quickMeetingTopic').closest('label').before(Object.assign(document.createElement('div'), {innerHTML:
    '<label>Проект · необязательно<select id="quickProject"><option value="">Без проекта — только тема</option></select></label><p class="privacy-note">Выберите проект: подтянем задачи доски, реестр из рабочей папки, материалы и прошлые договорённости. Без проекта доступен простой ввод темы.</p>'}));
  const projectFields = document.createElement('section'); projectFields.id = 'quickProjectFields'; projectFields.hidden = true;
  projectFields.innerHTML = `<div class="quick-time-grid"><label>Дата<input id="quickDate" type="date"></label><label>Время · по Москве<input id="quickTime" type="time"></label><label>Минут<input id="quickDuration" type="number" min="5" max="480" value="60"></label></div>
    <label>Найти задачу<input id="quickTaskSearch" type="search" placeholder="Номер или название"></label>
    <label><input id="quickTaskHistory" type="checkbox"> Показать историю и завершённые задачи</label>
    <div id="quickTaskList" class="quick-task-list" aria-label="Задачи проекта"></div>
    <button id="quickPrepare" type="button">Подтянуть контекст</button>
    <section id="quickPreview" aria-label="Найденный контекст" hidden></section>`;
  byId('quickMeetingBrief').closest('label').after(projectFields);
  const extras = document.createElement('details');
  extras.innerHTML = '<summary>Формат и дополнительная цель · необязательно</summary>';
  byId('quickMeetingType').closest('label').before(extras);
  extras.append(byId('quickMeetingType').closest('label'), byId('quickMeetingBrief').closest('label'));
  byId('quickTaskList').after(projectFields.querySelector('.quick-time-grid'));
  const intro = dialog.querySelector('#quickMeetingTaskRow + p');
  intro.textContent = wizardUi('Подготовка локальная: нет записи, вызова ИИ или приглашений во внешний календарь. Для встречи по проекту сначала проверьте найденные источники.');
  window.BlateroWizardI18n?.bindQuick(dialog);
  function localLabel(element,text,params={}) {
    if(window.BlateroWizardI18n)window.BlateroWizardI18n.label(element,text,params);
    else element.textContent=wizardUi(text,typeof params==='function'?params():params);
  }
  let projectTasks = [], selectedTasks = new Set(), prepared = null, optionsVersion = 0, createRequest = null;
  const projectSelect = byId('quickProject');
  function invalidate() {
    prepared = null; byId('quickPreview').hidden = true;
    if (!pending && !createdSession) byId('quickMeetingCreate').disabled = !!projectSelect.value;
  }
  function datesNow() {
    const pieces = new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date());
    const part = type => pieces.find(p => p.type === type)?.value;
    byId('quickDate').value = `${part('year')}-${part('month')}-${part('day')}`;
    byId('quickTime').value = `${part('hour')}:${part('minute')}`;
  }
  function drawTasks() {
    const query = byId('quickTaskSearch').value.trim().toLocaleLowerCase();
    const history = byId('quickTaskHistory').checked;
    const list = byId('quickTaskList'); list.replaceChildren();
    const shown = projectTasks.filter(t => (!query || (t.title + ' ' + t.goal).toLocaleLowerCase().includes(query)) &&
      (history || selectedTasks.has(t.id) || (t.origin !== 'history' && !['done','closed'].includes(t.status))));
    for (const task of shown) {
      const row = document.createElement('label'), checkbox = document.createElement('input'), text = document.createElement('span');
      checkbox.type = 'checkbox'; checkbox.value = task.id; checkbox.checked = selectedTasks.has(task.id);
      checkbox.disabled = task.status === 'closed';
      localLabel(text,'{title}{suffix}',()=>({title:task.title,suffix:task.status === 'closed' ? wizardUi(' · закрыта') : task.status === 'done' ? wizardUi(' · завершена') : ''}));
      checkbox.onchange = () => { if (checkbox.checked) selectedTasks.add(task.id); else selectedTasks.delete(task.id); invalidate(); notice('Выбрано задач: {count}. Подтяните контекст перед созданием.',{count:selectedTasks.size}); };
      row.append(checkbox, text); list.append(row);
    }
    if (!shown.length) { const empty=document.createElement('span');list.append(empty);localLabel(empty,'Подходящих задач нет. Измените поиск или включите историю. Создать задачу можно в разделе «Проекты».'); }
  }
  async function loadProjects() {
    const data = await projectRequest('quick-meeting/options');
    const previous = projectSelect.value; projectSelect.replaceChildren(new Option(wizardUi('Без проекта — только тема'), ''));
    localLabel(projectSelect.options[0],'Без проекта — только тема');
    for (const project of data.projects) projectSelect.add(new Option(project.name, project.id));
    projectSelect.value = previous;
  }
  async function chooseProject(ids = []) {
    const version = ++optionsVersion; invalidate(); selectedTasks = new Set(ids); projectTasks = [];
    projectFields.hidden = !projectSelect.value; byId('quickTaskList').replaceChildren();
    if (!projectSelect.value) { byId('quickMeetingCreate').disabled = false; return; }
    notice(wizardUi('Читаю задачи проекта…'));
    try {
      const data = await projectRequest('quick-meeting/options?project_id=' + encodeURIComponent(projectSelect.value));
      if (version !== optionsVersion || !dialog.open) return;
      projectTasks = data.tasks; drawTasks();
      if (!byId('quickMeetingTopic').value.trim()) byId('quickMeetingTopic').value = projectSelect.selectedOptions[0].textContent + ' — текущие задачи';
      notice(wizardUi('Выберите задачи, дату и время, затем нажмите «Подтянуть контекст».'));
    } catch(error) { if (version === optionsVersion) notice(error.message); }
  }
  projectSelect.onchange = () => { createRequest = null; chooseProject(); };
  byId('quickTaskSearch').oninput = drawTasks; byId('quickTaskHistory').onchange = drawTasks;
  for (const id of ['quickMeetingTopic','quickMeetingBrief','quickMeetingType','quickDate','quickTime','quickDuration']) byId(id).addEventListener('input', invalidate);
  function inputs() { return {project_id:projectSelect.value, task_ids:[...selectedTasks], name:byId('quickMeetingTopic').value.trim(), mtype:byId('quickMeetingType').value,
    date:byId('quickDate').value, time:byId('quickTime').value, duration:Number(byId('quickDuration').value), brief:byId('quickMeetingBrief').value.trim()}; }
  byId('quickPrepare').onclick = async () => {
    if (!selectedTasks.size) { notice(wizardUi('Выберите хотя бы одну задачу.')); return; }
    invalidate(); const version = ++optionsVersion; const payload = inputs();
    byId('quickPrepare').disabled = true; notice(wizardUi('Локально собираю источники. Исходные файлы не изменяются…'));
    try {
      const data = await projectRequest('quick-meeting/preview', payload);
      if (version !== optionsVersion || !dialog.open || JSON.stringify(inputs()) !== JSON.stringify(payload)) return;
      prepared = data; createRequest = null;
      const view = byId('quickPreview'); view.replaceChildren(); view.hidden = false;
      const summary = document.createElement('p');localLabel(summary,'Подготовлено: задач {tasks}, документов {files}, подтверждённых записей памяти {agreements}, прошлых отчётов {reports}. Папка: {path}',()=>({tasks:data.tasks.length,files:data.files.length,agreements:data.agreements.length,reports:data.reports.length,path:data.meta.workspace_path || wizardUi('не задана')}));view.append(summary);
      const files = document.createElement('div'); files.id = 'quickSourceList';
      for (const file of data.files) {
        const label = document.createElement('label'), box = document.createElement('input'), caption = document.createElement('span');
        box.type = 'checkbox'; box.value = file.path; box.checked = true;
        localLabel(caption,'{prefix}{path}{suffix}',()=>({prefix:file.registry ? wizardUi('Реестр · ') : '',path:file.path,suffix:file.truncated ? wizardUi(' · выдержка') : ''}));
        label.append(box, caption); files.append(label);
      }
      view.append(files);
      for (const agreement of data.agreements) { const row = document.createElement('p');localLabel(row,'Договорённость: {text}',{text:agreement.text});view.append(row); }
      for (const report of data.reports) { const row = document.createElement('p');localLabel(row,'Прошлый отчёт: {date} · {title}',{date:report.date,title:report.title});view.append(row); }
      for (const warning of data.warnings) { const row = document.createElement('p'); row.className = 'quick-warning'; row.textContent = warning; view.append(row); }
      byId('quickMeetingCreate').disabled = false; notice(wizardUi('Проверьте подборку. Снимите галочки с лишних или устаревших источников. Создание сохранит повестку, досье и встречу в локальном календаре.'));
      view.setAttribute('tabindex','-1'); view.scrollIntoView({block:'start'}); view.focus({preventScroll:true});
    } catch(error) { if (version === optionsVersion) notice(error.message); }
    finally { byId('quickPrepare').disabled = false; }
  };
  let taskContext = null, pending = null, createdSession = null;
  function notice(text,params={}) { localLabel(byId('quickMeetingStatus'),text,params); }
  function openQuick() {
    if (recLive) { alert(wizardUi('Сначала завершите текущую запись. Новая встреча не переключается во время REC.')); return; }
    if (!pending) { taskContext = null; createdSession = null; createRequest = null; prepared = null; selectedTasks.clear(); optionsVersion++; byId('quickMeetingForm').reset(); datesNow(); projectFields.hidden = true; byId('quickPreview').hidden = true; byId('quickMeetingLink').disabled = false; byId('quickMeetingCreate').disabled = false; byId('quickMeetingTaskRow').hidden = true; byId('quickMeetingRetryLink').hidden = true; notice(''); }
    dialog.showModal(); byId('quickMeetingTopic').focus();
    loadProjects().catch(error => notice(error.message));
  }
  const quickButton = document.createElement('button'); quickButton.type = 'button';
  quickButton.id = 'quickMeetingBtn'; quickButton.className='primary';quickButton.textContent = wizardUi('+ новая встреча'); quickButton.title = wizardUi('Создать по теме или перейти в подробный мастер');
  localLabel(quickButton,'+ новая встреча');quickButton.dataset.i18nTitle='quick.buttonHelp';
  byId('setupBtn').before(quickButton);
  byId('setupBtn').title = wizardUi('Пошаговый мастер с материалами и ИИ-подготовкой');
  byId('setupBtn').dataset.i18nTitle='quick.wizardHelp';
  quickButton.onclick = openQuick;
  byId('quickMeetingClose').onclick = () => dialog.close();
  byId('quickMeetingWizard').onclick = () => {
    const topic=byId('quickMeetingTopic').value, brief=byId('quickMeetingBrief').value;
    dialog.close(); quickButton.focus();openSetupWizard(byId('quickMeetingType').value);
    byId('setupName').value=topic; byId('setupBrief').value=brief;
  };
  async function projectRequest(path, body) {
    const response = await fetch('/api/projects/' + path, {method:body ? 'POST':'GET', headers:body ? {'Content-Type':'application/json'}:{}, body:body ? JSON.stringify(body):undefined});
    const data = await response.json(); if (!response.ok) throw Error(data.error || wizardUi('Не удалось связать встречу с задачей')); return data;
  }
  async function linkCreated() {
    if (createRequest) {
      try {
        const result = await projectRequest('quick-meeting/create', createRequest);
        if (result.warnings.length) { notice('Встреча сохранена. {message}',{message:result.warnings.join('; ')}); return; }
        dialog.close();
      } catch(error) { notice('Встреча сохранена, связь пока не восстановлена: {message}',{message:error.message}); }
      return;
    }
    if (!createdSession || !taskContext || !byId('quickMeetingLink').checked) { dialog.close(); return; }
    byId('quickMeetingRetryLink').hidden = true;
    try {
      const freshTask = await projectRequest('tasks/' + encodeURIComponent(taskContext.task.id));
      const snapshot = await projectRequest('meeting-sync', {session:createdSession});
      if (!snapshot.material?.available) throw Error(wizardUi('Встреча создана, но её источник пока недоступен'));
      await projectRequest('materials/link', {material_id:snapshot.material.id, snapshot_sha256:snapshot.material.snapshot_sha256, work_item_id:freshTask.task.id, revision:freshTask.task.revision});
      document.dispatchEvent(new CustomEvent('blatero:meeting', {detail:currentInit}));
      dialog.close();
    } catch (error) {
      notice('Встреча уже создана и открыта. Привязка не выполнена: {message}',{message:error.message});
      byId('quickMeetingRetryLink').hidden = false;
    }
  }
  byId('quickMeetingRetryLink').onclick = linkCreated;
  byId('quickMeetingForm').onsubmit = async event => {
    event.preventDefault();
    if (pending || createdSession) return;
    if (!byId('quickMeetingTopic').value.trim()) { notice('Укажите тему встречи.'); byId('quickMeetingTopic').focus(); return; }
    if (recLive) { notice('Запись идёт. Сначала завершите её.'); return; }
    if (!ws || ws.readyState !== WebSocket.OPEN) { notice('Нет подключения к серверу. Создание не отправлено.'); return; }
    if (projectSelect.value) {
      if (!prepared) { notice('Сначала нажмите «Подтянуть контекст».'); return; }
      createRequest ||= {request_id:prepared.request_id, files:[...byId('quickSourceList').querySelectorAll('input:checked')].map(el => el.value)};
      pending = {id:createRequest.request_id}; byId('quickMeetingCreate').disabled = true; notice('Сохраняю встречу, повестку и досье…');
      try {
        const result = await projectRequest('quick-meeting/create', createRequest);
        pending = null; createdSession = result.session;
        if (!recLive) send({type:'session', dir:result.session});
        if (result.warnings.length) { notice('Встреча создана. {message}',{message:result.warnings.join('; ')}); byId('quickMeetingRetryLink').hidden = false; }
        else { dialog.close(); document.dispatchEvent(new CustomEvent('blatero:meeting', {detail:currentInit})); }
      } catch(error) { pending = null; byId('quickMeetingCreate').disabled = false; notice('Создание не подтверждено: {message}. Повторное нажатие безопасно: используется тот же запрос. При изменении источников заново подтяните контекст.',{message:error.message}); }
      return;
    }
    pending = {id:crypto.randomUUID()}; byId('quickMeetingCreate').disabled = true;
    notice(wizardUi('Создаю локально…'));
    send({type:'new_meeting', request_id:pending.id, name:byId('quickMeetingTopic').value.trim(), mtype:byId('quickMeetingType').value, brief:byId('quickMeetingBrief').value.trim(), contour:'work', project_name:taskContext?.project?.name || '', initialize_workspace:false});
    pending.timer = setTimeout(() => {
      // Unknown outcome must not cause an automatic duplicate creation.
      notice(wizardUi('Ответ не получен. Проверьте список встреч перед повторным созданием; автоматического повтора нет.'));
      byId('quickMeetingCreate').disabled = false; pending = null;
    }, 15000);
  };
  const originalHandle = handle;
  handle = function(message) {
    originalHandle(message);
    if (message.type === 'init') showModel(message.llm_connection);
    if (message.type === 'ai_activity' && message.model_info) showModel(message.model_info);
    if (message.type === 'llm_connection_status') showModel(currentInit?.llm_connection);
    if (message.type === 'init') showActivity(message.ai_activity);
    if (message.type === 'ai_activity') showActivity(message);
    if (activity?.phase === 'running') byId('pulse').disabled = true;
    if (message.type === 'meeting_created' && message.request_id === pending?.id) {
      clearTimeout(pending.timer); pending = null; createdSession = message.session;
      byId('quickMeetingCreate').disabled = true; notice(wizardUi('Встреча создана.'));
      linkCreated();
    }
  };
  if (currentInit) showActivity(currentInit.ai_activity);
  const params = new URLSearchParams(location.search);
  if (params.has('quick_task')) {
    const id = params.get('quick_task');
    // Consume the action URL, so reloading never creates or opens another dialog.
    params.delete('quick_task'); history.replaceState({}, '', location.pathname + (params.size ? '?' + params : '') + location.hash);
    openQuick(); notice(wizardUi('Читаю задачу…')); byId('quickMeetingCreate').disabled = true;
    projectRequest('tasks/' + encodeURIComponent(id)).then(context => {
      taskContext = context; const task = context.task;
      byId('quickMeetingTopic').value = task.title;
      byId('quickMeetingBrief').value = [task.goal, task.next_step && 'Следующий шаг: ' + task.next_step].filter(Boolean).join('\n\n');
      byId('quickMeetingTaskRow').hidden = false;
      const retired = task.status === 'closed' || !!task.merged_into;
      byId('quickMeetingLink').checked = !retired;
      byId('quickMeetingLink').disabled = retired;
      byId('quickMeetingCreate').disabled = false;
      notice(retired ? wizardUi('Исходная карточка закрыта или объединена. Можно создать встречу по её теме, но связи и статус этой карточки меняться не будут.') : wizardUi('Тема и цель взяты из задачи. Можно изменить перед созданием.'));
    }).catch(error => { notice(error.message); byId('quickMeetingCreate').disabled = false; });
  }
})();
