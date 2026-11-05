'use strict';
// This catalog routes real controls. Values remain in the original server stores;
// drafts live only in memory and cannot be mistaken for acknowledged settings.
(() => {
  const byId = id => document.getElementById(id), overlay = byId('settingsOverlay');
  if (!overlay) return;
  const ui = (text,params={}) => window.BlateroSettingsI18n?.ui(text,params) ??
    String(text).replace(/\{([a-zA-Z_]\w*)\}/g,(match,name)=>Object.hasOwn(params,name)?String(params[name]):match);
  const sections = [
    ['overview','Обзор','M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z'],
    ['sound','Звук и речь','M9 4v8a3 3 0 0 0 6 0V4a3 3 0 0 0-6 0 M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3'],
    ['ai','ИИ и подсказки','m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z'],
    ['reports','Отчёты','M5 2h10l4 4v16H5z M9 10h6 M9 14h6'],
    ['privacy','Данные и приватность','M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6z M8 12l3 3 5-6'],
    ['appearance','Внешний вид','M3 4h18v14H3z M8 22h8 M12 18v4'],
    ['connections','Интеграции','M8 12h8 M9 5H6a7 7 0 0 0 0 14h3 M15 5h3a7 7 0 0 1 0 14h-3'],
    ['practice','Практика','m2 8 10-5 10 5-10 5z M6 10v6c4 3 8 3 12 0v-6'],
    ['service','Обслуживание','M14 3a6 6 0 0 0-7 7L2 16l6 6 6-6a6 6 0 0 0 7-7l-5 3-4-4z']
  ];
  const config = {
    selMic:'mic_device',selOutput:'output_device',selSpeech:'speech_provider',
    selWhisper:'whisper_model',selAecBackend:'pre_stt_echo_backend',
    acousticEchoSuppression:'pre_stt_echo_suppression',echoSuppression:'cross_channel_echo_suppression',
    selQuestionVoice:'question_voice_provider',selVoice:'voice',selProvider:'llm_provider',
    selAuto:'auto_pulse',selSceneCoach:'scene_coach_route',inpPulseModel:'pulse_model',inpReportModel:'report_model',
    selStyle:'question_style',reportReviewBeforeFinalize:'report_review_before_finalize',
    reportTimestamps:'report_include_timestamps',selPrivacy:'text_privacy_mode',
    cloudAck:'cloud_processing_acknowledged',selFont:'font_scale'
  };
  const meta = {
    selMType:'type',selDur:'duration',inpName:'name',inpClient:'client_name',
    inpProject:'project_name',inpWorkspace:'workspace_path',inpSpeakerMe:'speaker_me',
    inpSpeakerGuest:'speaker_guest',inpEmulationRole:'emulation_role',selContour:'contour'
  };
  const fields = {...config,...meta}, drafts = new Map(), baselines = new Map();
  const aliases = {settingsAudio:'sound',settingsAi:'ai',settingsReports:'reports',
    settingsPrivacy:'privacy',settingsInterface:'appearance',settingsPractice:'practice',
    settingsService:'service',settingsConnections:'connections',settingsMeeting:'meeting',settingsWorkspace:'meeting'};
  const synonyms = {
    selProvider:'ключ токен api codex chatgpt openrouter подключить',
    inpLlmApiKey:'ключ секрет пароль токен api',inpLlmBaseUrl:'адрес сервер endpoint ollama',
    selSpeech:'stt speechkit whisper распознавание',selFont:'шрифт масштаб',
    trainingBtn:'тренировка сценка симуляция рекрутер кандидат',selPrivacy:'персональные данные обезличивание',
    speakerBankBtn:'имена говорящие голоса дикторы',reportTimestamps:'таймкоды ссылки',
    modelManagerSettings:'установка модели whisper chatterbox aec',themeToggle:'светлая темная тема',
    motionToggle:'движение анимация',cloudAck:'согласие облако разрешение'
  };
  let active = 'overview', session = '', revisions = {}, pending = null, lastMessage = '';
  let secret = '', endpoint = '', endpointDirty = false, connectionPending = null, closeAfterSave = false, trainingRequest = null, rebase = null;
  const scopeOf = id => id in meta ? 'meta' : 'config';
  const keyOf = id => scopeOf(id) === 'meta' ? session + ':' + id : id;
  const read = el => el?.type === 'checkbox' ? el.checked : el?.value;
  const same = (a,b) => String(a ?? '') === String(b ?? '');
  function put(el,value) {
    if (!el) return;
    if (el.type === 'checkbox') { el.checked = !!value; return; }
    if (el.tagName === 'SELECT' && value && ![...el.options].some(x => x.value === String(value))) {
      el.add(new Option(String(value) + (el.id === 'selDur' ? '' : ui(' (недоступно)')), String(value)));
    }
    el.value = value ?? '';
  }
  const currentDrafts = () => [...drafts.values()].filter(d => d.scope === 'config' || d.session === session);
  const sectionOf = el => el.closest('[data-settings-page]')?.dataset.settingsPage;
  const visibleDrafts = () => currentDrafts().filter(d => sectionOf(byId(d.id)) === active);
  byId('settingsNav').innerHTML = sections.map(([id,label,path]) =>
    '<button type="button" data-settings-target="' + id + '"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="' + path + '"/></svg><span data-settings-nav-label>' + ui(label) + '</span></button>').join('');
  byId('settingsSectionSelect').innerHTML = [...sections,['meeting','Параметры встречи']].map(([id,label]) =>
    '<option value="' + id + '">' + ui(label) + '</option>').join('');
  function showState(text,params={}) { lastMessage = {text,params}; footer(); }
  const jumpChanges = document.createElement('button');
  jumpChanges.type = 'button'; jumpChanges.id = 'settingsJumpChanges'; jumpChanges.hidden = true;
  byId('settingsSaveState').after(jumpChanges);
  jumpChanges.onclick = () => { const first = visibleDrafts()[0] || currentDrafts()[0]; if(first) reveal(first.id); };
  function footer() {
    const list = visibleDrafts(), total = currentDrafts().length;
    byId('settingsSaveState').textContent = pending ? ui('Сохраняю…') : lastMessage ? ui(lastMessage.text,lastMessage.params) :
      (list.length ? ui('Несохранённых изменений: {count}',{count:list.length}) :
        total ? ui('В других разделах есть изменения: {count}',{count:total}) : ui('Изменений нет'));
    byId('settingsApply').hidden = byId('settingsDiscard').hidden = !list.length;
    byId('settingsApply').disabled = !!pending;
    byId('settingsDiscard').disabled = !!pending;
    overlay.querySelector('.settings-footer').dataset.dirty = String(!!total);
    jumpChanges.hidden = !total;
    jumpChanges.textContent = ui('Перейти к изменениям');
    overlay.querySelectorAll('.settings-dirty').forEach(row => row.classList.remove('settings-dirty'));
    overlay.querySelectorAll('[data-settings-dirty]').forEach(field => field.removeAttribute('data-settings-dirty'));
    for(const draft of currentDrafts()) {
      const field = byId(draft.id); field.dataset.settingsDirty = 'true';
      field.closest('.setting-row, .consent-check, label')?.classList.add('settings-dirty');
    }
    const speech = currentDrafts().find(d => d.id === 'selSpeech') ||
      currentDrafts().find(d => d.id === 'selWhisper');
    byId('settingsApplySpeech').hidden = !recLive || !speech;
    byId('settingsApplySpeech').disabled = !!pending;
    byId('settingsApplySpeech').textContent = ui(speech?.id === 'selSpeech' ? 'Переключить движок' : 'Применить модель');
    byId('settingsNav').querySelectorAll('[data-settings-target]').forEach(button => {
      const n = currentDrafts().filter(d => sectionOf(byId(d.id)) === button.dataset.settingsTarget).length;
      let badge = button.querySelector('.settings-change-count');
      if(!badge) { badge=document.createElement('span');badge.className='settings-change-count';badge.setAttribute('aria-hidden','true');button.append(badge); }
      badge.hidden = !n; badge.textContent = String(n);
      button.setAttribute('aria-label', button.querySelector('[data-settings-nav-label]').textContent.trim() + (n ? ui(', изменений: {count}',{count:n}) : ''));
    });
    for(const option of byId('settingsSectionSelect').options) {
      const count=currentDrafts().filter(d=>sectionOf(byId(d.id))===option.value).length;
      option.textContent=ui(sections.find(row=>row[0]===option.value)?.[1] || 'Параметры встречи')+(count?' · '+count:'');
    }
    window.BlateroSettingsI18n?.applyOwned();
  }
  function select(id, focus = false) {
    id = aliases[id] || id;
    const page = overlay.querySelector('[data-settings-page="' + id + '"]');
    if (!page) return;
    active = id; lastMessage = ''; byId('settingsSearch').value = '';
    byId('settingsSearchResults').hidden = true;
    overlay.querySelectorAll('[data-settings-page]').forEach(el => { el.hidden = el !== page; });
    byId('settingsNav').querySelectorAll('button').forEach(button => {
      if (button.dataset.settingsTarget === id) button.setAttribute('aria-current','page');
      else button.removeAttribute('aria-current');
    });
    byId('settingsSectionSelect').value = id;
    byId('settingsTitle').textContent = ui(id === 'meeting' ? 'Параметры встречи' : 'Настройки программы');
    byId('settingsModeNote').textContent = id === 'meeting' ? (currentInit?.session || session) : ui('Подключения, звук и оформление.');
    overlay.scrollTop = 0;
    if (focus) { page.querySelector('h4').tabIndex = -1; page.querySelector('h4').focus(); }
    footer();
  }
  function reveal(id) {
    const el = byId(id);
    if (!el || !overlay.contains(el)) return;
    if ((id === 'inpLlmApiKey' && byId('selProvider').value === 'codex') ||
        (id === 'inpLlmBaseUrl' && byId('selProvider').value !== 'compatible')) {
      select('ai'); byId('selProvider').focus();
      showState(id === 'inpLlmApiKey' ? 'Для Codex API-токен не нужен. Для API выберите провайдера.' :
        'Адрес сервера задаётся для подключения «Совместимый API».');
      return;
    }
    select(sectionOf(el) || aliases[id] || 'overview');
    for (let parent = el.parentElement; parent && parent !== overlay; parent = parent.parentElement)
      if (parent.tagName === 'DETAILS') parent.open = true;
    el.scrollIntoView({block:'center'});
    el.focus({preventScroll:true});
    el.closest('.setting-row, .consent-check')?.classList.add('settings-highlight');
  }
  overlay.addEventListener('click', event => {
    const target = event.target.closest('[data-settings-target],[data-settings-field]');
    if (target?.dataset.settingsTarget) select(target.dataset.settingsTarget, true);
    if (target?.dataset.settingsField) reveal(target.dataset.settingsField);
  });
  byId('settingsSectionSelect').onchange = e => select(e.target.value);
  function preview(id) {
    if (id === 'selProvider') {
      const provider = byId(id).value, key = byId('inpLlmApiKey').value, url = byId('inpLlmBaseUrl').value;
      updateProviderControls(provider, provider === currentInit?.config?.llm_provider ? currentInit.llm_connection : null);
      byId('inpLlmApiKey').value = key; byId('inpLlmBaseUrl').value = url;
      byId('settingsConnectionHelp').textContent = provider === 'codex'
        ? '' : ui('Успешная проверка сохраняет подключение.');
      byId('settingsConnectionHelp').hidden = provider === 'codex';
      const credentialNote = byId('settingsCredentialNote') || byId('llmConnectionStatus')?.nextElementSibling;
      if (credentialNote) credentialNote.textContent = ui(provider === 'codex'
        ? 'Проверка не отправляет материалы встречи.'
        : 'Токен хранится в Windows Credential Manager. Проверка не отправляет материалы встречи.');
      byId('providerHint').hidden = provider !== 'codex';
    }
    if (id === 'selSpeech') updateSpeechControls(byId(id).value);
    if (id === 'selFont') applyFontScale(byId(id).value);
    byId('settingsSpeechRoute').textContent = ui(byId('selSpeech').value === 'yandex'
      ? 'Аудио отправляется в Яндекс SpeechKit. Смена движка не прерывает запись.'
      : 'Аудио распознаётся на этом компьютере. Смена движка не прерывает запись.');
  }
  function stage(event) {
    const el = event.target;
    if (!(el.id in fields)) return;
    event.stopImmediatePropagation();
    const value = read(el), key = keyOf(el.id);
    if (same(value,baselines.get(key))) drafts.delete(key);
    else drafts.set(key,{id:el.id,key:fields[el.id],scope:scopeOf(el.id),session,value,
      revision:drafts.get(key)?.revision || revisions[scopeOf(el.id)]});
    lastMessage = ''; preview(el.id); footer();
  }
  overlay.addEventListener('input', stage, true);
  overlay.addEventListener('change', stage, true);
  function discard(list = visibleDrafts()) {
    for (const item of list) { drafts.delete(keyOf(item.id)); put(byId(item.id),baselines.get(keyOf(item.id))); }
    preview('selProvider'); preview('selSpeech'); preview('selFont');
    showState('Изменения отменены');
  }
  byId('settingsDiscard').onclick = () => discard();
  function apply(list = visibleDrafts()) {
    if (pending || !list.length) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) { showState('Нет соединения с сервером. Черновик сохранён в этой вкладке.'); return; }
    const scope = list[0].scope, batch = list.filter(d => d.scope === scope);
    const updates = Object.fromEntries(batch.map(d => [d.key, d.key === 'duration' ? (d.value ? Number(d.value) : '') : d.value]));
    if (updates.text_privacy_mode === 'raw' && !confirm(ui('Передавать исходные имена, контакты и другие данные без обезличивания?'))) return;
    if (updates.contour && updates.contour !== currentContour &&
      !confirm(ui('Переместить встречу в {environment} контур?',{environment:ui(updates.contour === 'test' ? 'тестовый' : 'рабочий')}))) return;
    const requestId = crypto.randomUUID();
    pending = {requestId,batch,scope,timer:setTimeout(() => {
      pending = null; closeAfterSave = false;
      showState('Сервер не подтвердил сохранение. Черновик оставлен; проверьте соединение и повторите.');
    },90000)};
    send({type:'settings_apply',scope,request_id:requestId,session,generation:currentInit.session_generation,
      revision:batch[0].revision,updates,raw_acknowledged:updates.text_privacy_mode === 'raw'});
    footer();
  }
  byId('settingsApply').onclick = () => apply();
  byId('settingsApplySpeech').onclick = () => {
    const item = currentDrafts().find(d => d.id === 'selSpeech') ||
      currentDrafts().find(d => d.id === 'selWhisper');
    if (item) apply([item]);
  };
  const closeChoice = document.createElement('div'); closeChoice.hidden = true;
  closeChoice.className = 'settings-close-choice';
  closeChoice.innerHTML = '<p data-i18n="settings.dynamic.22">В настройках есть несохранённые изменения.</p><div class="setting-actions"><button type="button" data-choice="save" class="primary" data-i18n="settings.dynamic.23">Сохранить и закрыть</button><button type="button" data-choice="discard" data-i18n="settings.dynamic.24">Не сохранять</button><button type="button" data-choice="return" data-i18n="settings.dynamic.25">Продолжить настройку</button></div>';
  overlay.querySelector('.settings-footer').after(closeChoice);
  window.BlateroI18n?.apply(closeChoice);
  closeChoice.onclick = event => {
    const choice = event.target.closest('[data-choice]')?.dataset.choice;
    if (!choice) return;
    closeChoice.hidden = true;
    if (choice === 'return') { byId('settingsSearch').focus(); return; }
    if (choice === 'discard') {
      discard(currentDrafts()); byId('inpLlmApiKey').value = ''; secret = ''; endpointDirty = false;
      closeSettingsOverlay(); return;
    }
    closeAfterSave = true;
    if (byId('inpLlmApiKey').value || endpointDirty) {
      select('ai'); showState('Сохраните подключение отдельной кнопкой, затем закройте настройки.'); closeAfterSave = false; return;
    }
    apply(currentDrafts());
  };
  function canClose() {
    if (pending) { showState('Дождитесь подтверждения сохранения.'); return false; }
    if (currentDrafts().length || byId('inpLlmApiKey').value || endpointDirty) {
      closeChoice.hidden = false; closeChoice.scrollIntoView({block:'end'});
      closeChoice.querySelector('[data-choice=return]').focus(); return false;
    }
    closeChoice.hidden = true; return true;
  }
  window.addEventListener('beforeunload', event => {
    if (currentDrafts().length || byId('inpLlmApiKey').value || endpointDirty || pending) { event.preventDefault(); event.returnValue = ''; }
  });
  window.addEventListener('blatero:connection',event => {
    if (event.detail.connected || !pending) return;
    clearTimeout(pending.timer); pending = null; closeAfterSave = false;
    showState('Соединение потеряно до подтверждения. Черновик оставлен; после подключения проверьте настройки.');
  });
  // Prevent init/status refreshes from erasing an unsubmitted credential.
  byId('inpLlmApiKey').addEventListener('input', () => { secret = byId('inpLlmApiKey').value; });
  byId('inpLlmBaseUrl').addEventListener('input', () => { endpoint = byId('inpLlmBaseUrl').value; endpointDirty = true; });
  ['llmSave','llmTest'].forEach(id => byId(id).addEventListener('click', () => {
    connectionPending = {provider:byId('selProvider').value,secret:byId('inpLlmApiKey').value};
  },true));
  function beforeMessage(m) {
    if (m.type === 'workspace_probe' && m.target === 'settings' &&
        (m.session !== session || m.generation !== currentInit?.session_generation)) return false;
    if (m.type === 'init') secret = byId('inpLlmApiKey').value;
    if (m.type === 'llm_connection_status' && connectionPending &&
        m.provider === connectionPending.provider && m.state !== 'scanning') {
      if (m.state === 'ready' || /Настройки сохранены/.test(m.message || '')) {
        drafts.delete('selProvider'); secret = ''; byId('inpLlmApiKey').value = '';
        endpointDirty = false; endpoint = byId('inpLlmBaseUrl').value; footer();
      }
      connectionPending = null;
    }
    if (m.type === 'settings_result' && pending && m.request_id === pending.requestId) {
      const submitted = pending; clearTimeout(pending.timer); pending = null;
      if (m.ok) {
        for (const d of submitted.batch) {
          const key = d.scope === 'meta' ? d.session + ':' + d.id : d.id;
          if (same(drafts.get(key)?.value,d.value)) drafts.delete(key);
        }
        revisions[m.scope] = m.revision;
        for (const d of currentDrafts()) if (d.scope === m.scope) d.revision = m.revision;
        showState('Сохранено сервером');
        if (closeAfterSave) {
          if (currentDrafts().length) apply(currentDrafts());
          else { closeAfterSave = false; closeSettingsOverlay(); }
        }
      } else { closeAfterSave = false; rebase = m.scope; showState('Не сохранено: {message}',{message:m.message}); }
    }
    if (m.type === 'meeting_created' && m.request_id === trainingRequest) {
      trainingRequest = null; overlay.classList.remove('show');
      byId('trainingPanel').scrollIntoView({block:'start'});
    }
  }
  function afterInit(m) {
    session = m.current_dir; revisions = m.settings_revisions || {};
    put(byId('selDur'),m.meta?.duration ? String(m.meta.duration) : '');
    put(byId('selMic'),m.mic_current || 'auto');
    put(byId('selOutput'),m.output_current || 'auto');
    if (rebase) {
      for (const d of currentDrafts()) if (d.scope === rebase) d.revision = revisions[rebase];
      rebase = null;
    }
    for (const id of Object.keys(fields)) baselines.set(keyOf(id),read(byId(id)));
    for (const d of currentDrafts()) put(byId(d.id),d.value);
    byId('inpLlmApiKey').value = secret;
    if (endpointDirty) byId('inpLlmBaseUrl').value = endpoint;
    else endpoint = byId('inpLlmBaseUrl').value;
    preview('selProvider'); preview('selSpeech');
    for (const option of byId('selSpeech').options)
      option.textContent = ui(option.value === 'yandex' ? 'SpeechKit · Яндекс' : 'Whisper · локально');
    for (const id of ['selAuto','selFont','selStyle'])
      for (const option of byId(id).options) option.textContent = option.textContent.replace(/^(авто|шрифт|вопросы):\s*/i,'');
    if (drafts.has('selFont')) preview('selFont');
    renderSummary(m);
    footer();
  }
  function renderSummary(m) {
    renderProviderContractStatus(m.provider_contracts || {});
    byId('settingsMeetingLabel').textContent = m.session;
    byId('trainingBtn').textContent = ui(m.meta?.type === 'тренировка' ? 'Продолжить тренировку' : 'Подробная настройка тренировки');
    const nameLabel = ui(['собеседование','кандидат'].includes(byId('selMType').value) ? 'Имя участника' : 'Тема встречи');
    byId('settingsNameLabel').textContent = nameLabel; byId('inpName').setAttribute('aria-label',nameLabel);
    byId('settingsSoundState').textContent = (m.mic_current || ui('Автовыбор')) + ' · ' +
      ui(m.preflight?.state === 'ready' ? 'Проверка пройдена' : 'Проверьте устройства перед встречей');
    byId('settingsAiState').textContent = ui(m.llm_connection?.label || m.config.llm_provider) + ' · ' +
      ui(m.llm_connection?.source || 'Доступ не настроен');
    byId('settingsDataState').textContent = ui(m.config.cloud_ack
      ? (m.config.text_privacy_mode === 'redact' ? 'Облако разрешено · обезличивание включено' : 'Облако разрешено · исходный текст')
      : 'Облачные функции выключены');
  }
  const searchable = () => [...new Set([...Object.keys(fields),...Object.keys(synonyms),'settingsRecovery','settingsData','settingsShutdown','settingsAnalysis'])].map(id => {
    const el = byId(id), label = overlay.querySelector('label[for="' + id + '"]')?.textContent ||
      el?.closest('label')?.querySelector('strong')?.textContent || el?.textContent || el?.getAttribute('aria-label') || id;
    return {id,label:label.trim(),section:sectionOf(el),words:((window.BlateroSettingsI18n?.searchTerms(label.trim()) || label) + ' ' + (synonyms[id] || '')).toLocaleLowerCase()};
  });
  byId('settingsSearch').oninput = event => {
    const query = event.target.value.trim().toLocaleLowerCase(), results = byId('settingsSearchResults');
    if (!query) { select(active); byId('settingsSearch').focus(); return; }
    overlay.querySelectorAll('[data-settings-page]').forEach(el => { el.hidden = true; });
    results.replaceChildren(); results.hidden = false;
    const matches = searchable().filter(row => query.split(/\s+/).every(term => row.words.includes(term)));
    if (!matches.length) { results.textContent = ui('Настройка не найдена. Попробуйте «микрофон», «токен» или «тренировка».'); return; }
    for (const row of matches) {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = row.label;
      const note = document.createElement('small'); note.textContent = ui(sections.find(x => x[0] === row.section)?.[1] || 'Параметры встречи');
      button.append(note); button.onclick = () => reveal(row.id); results.append(button);
    }
  };
  function routeHash() {
    let target;
    try { target = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (!target.startsWith('settings')) return;
    openSettingsOverlay(); select(aliases[target] || 'overview');
    if (target === 'settingsWorkspace') queueMicrotask(() => reveal('inpWorkspace'));
  }
  window.addEventListener('hashchange',routeHash);
  byId('settingsPreflight').onclick = () => { if (closeSettingsOverlay()) byId('preflightQuick').click(); };
  byId('settingsAnalysis').onclick = () => openAnalysisHub();
  byId('settingsRecovery').onclick = () => byId('recoveryBtn').click();
  byId('settingsData').onclick = () => openSessionLifecycle(currentInit.current_dir);
  byId('settingsShutdown').onclick = () => shutdownApplication();
  overlay.addEventListener('click', event => {
    const button = event.target.closest('[data-practice]');
    if (!button || !currentInit) return;
    if (recLive) { showState('Сначала остановите текущую запись.'); return; }
    if (!canClose()) return;
    selectTrainingMode(button.dataset.practice);
    trainingRequest = crypto.randomUUID();
    send({type:'new_meeting',name:'Тренировка разговора',mtype:'тренировка',contour:'test',
      request_id:trainingRequest,initialize_workspace:false});
    showState('Создаю тренировку…');
  });
  overlay.addEventListener('click',event => {
    const id = event.target.closest('button')?.id;
    const needsSound = ['audioBtn','settingsMicTest','aecTestStart','voiceTestBtn'].includes(id);
    const needsMeeting = id === 'workspaceInit';
    if (visibleDrafts().length && (needsSound || needsMeeting)) {
      event.stopImmediatePropagation();
      showState('Сначала сохраните или отмените изменения этого раздела.');
    }
  },true);
  const workspaceProbe = () => stage({target:byId('inpWorkspace'),stopImmediatePropagation(){}});
  window.BlateroSettings = {select,reveal,canClose,beforeMessage,afterInit,workspaceProbe};
  document.addEventListener('blatero:language',()=>{
    for(const [id,label] of sections) {
      const button=byId('settingsNav').querySelector('[data-settings-target="'+id+'"]');
      button.querySelector('[data-settings-nav-label]').textContent=ui(label);
    }
    for(const option of byId('settingsSectionSelect').options)
      option.textContent=ui(sections.find(row=>row[0]===option.value)?.[1] || 'Параметры встречи');
    byId('settingsTitle').textContent=ui(active==='meeting'?'Параметры встречи':'Настройки программы');
    byId('settingsModeNote').textContent=active==='meeting'?(currentInit?.session || session):ui('Подключения, звук и оформление.');
    preview('selProvider');preview('selSpeech');
    if(currentInit)renderSummary(currentInit);
    window.BlateroI18n.apply(closeChoice);footer();
  });
  select('overview');
  if (currentInit) afterInit(currentInit);
  routeHash();
})();
