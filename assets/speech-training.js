/* Speech practice: the shared REC owns capture; attempts and comparisons are immutable. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const host = el('speechTraining');
  // The preceding server version can remain open while an update is being applied.
  if (!host || !el('speechPractice')) return;
  // A running older server may still serve its pre-update HTML until restart.
  if(!el('speechCompareState')) {
    const saved=document.createElement('span');saved.id='speechCompareState';
    saved.setAttribute('role','status');saved.hidden=true;el('speechCompare').after(saved);
  }
  const fields = [['speechTopic','topic'],['speechAudience','audience'],['speechGoal','goal'],
    ['speechFocus','focus'],['speechSeconds','target_seconds'],['speechPreset','preset']];
  let data = {}, session = '', pendingStart = false, localBusy = false, lastError = '';
  let timer = null, audioEnd = null, lastPlan = '', historyKey = '', editing = false;
  let countdownAt = 0, busyType = '', busyAt = 0;
  let startToken = null, generation = null, serverEpoch = null, pendingText = null;
  const textKey = () => 'blatero.speechTextPending.' + session;
  function keepPendingText() {
    try {
      if (pendingText) sessionStorage.setItem(textKey(), JSON.stringify(pendingText));
      else sessionStorage.removeItem(textKey());
    } catch {}
  }
  function readPendingText() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(textKey()) || 'null');
      return saved?.exercise_id === data.plan?.exercise_id && typeof saved?.text === 'string'
        && typeof saved?.request_id === 'string' ? saved : null;
    } catch { return null; }
  }
  function acceptTextReceipt() {
    if (!pendingText || data.last?.id !== pendingText.request_id.replaceAll('-','')) return;
    if (el('speechText').value === pendingText.text) el('speechText').value = '';
    pendingText = null;
    keepPendingText();
  }
  const audio = el('speechAudio');
  const clock = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2,'0')}`;
  function command(type, extra = {}) {
    lastError = ''; localBusy = true; busyType = type; busyAt = Date.now();
    if (type === 'speech_start') stopAudio();
    if (!send({type, ...extra})) localBusy = false;
    render();
  }
  function stopAudio() { audio.pause(); audio.removeAttribute('src'); audio.hidden = true; audioEnd = null; }
  function playSegment(segment) {
    if (!segment?.audio_url) return;
    audio.hidden = false;
    const start = Math.max(0, Number(segment.start_ms || 0) / 1000);
    audioEnd = Number(segment.end_ms || 0) / 1000;
    audio.src = segment.audio_url;
    audio.onloadedmetadata = () => {
      audio.currentTime = Math.min(start, Number.isFinite(audio.duration) ? audio.duration : start);
      audio.play().catch(() => { studioLabel(el('speechStatus'),"Нажмите ▶ в проигрывателе."); });
    };
    audio.load();
  }
  audio.addEventListener('timeupdate', () => {
    if (audioEnd && audio.currentTime >= audioEnd) { audio.pause(); audioEnd = null; }
  });
  function beginCountdown() {
    pendingStart = false; countdownAt = Date.now() + 3000; lastError = ''; stopAudio();
  }
  function render() {
    const busy = localBusy || !!data.busy, active = data.status === 'active';
    const prepared = !!data.plan;
    const planKey = JSON.stringify(data.plan || {});
    if (data.plan && lastPlan !== planKey) {
      lastPlan = planKey; editing = false;
      for (const [field, key] of fields)
        el(field).value = data.plan[key] ?? '';
    }
    const dirty = prepared && fields.some(([id,key]) => String(el(id).value) !== String(data.plan[key] ?? ''));
    const last = data.last?.plan?.exercise_id === data.plan?.exercise_id ? data.last : null;
    const repeatReady = data.status === 'prepared' && !!data.repeat_from;
    const awaiting = pendingStart || !!countdownAt || (busy && busyType === 'speech_start');
    const locked = busy || active || awaiting;
    if (countdownAt && !recLive) { countdownAt = 0; startToken = null; lastError = studioUi("Запись остановлена. Нажмите «Записать попытку», когда будете готовы."); }
    if (countdownAt && Date.now() >= countdownAt) {
      countdownAt = 0; command('speech_start', {speech_rec_token:startToken}); startToken = null; return;
    }
    host.classList.toggle('speech-performing', active || awaiting);
    document.body.classList.toggle('speech-rec-live', active || awaiting || recLive);
    el('speechSetup').hidden = prepared && !editing;
    el('speechEdit').hidden = !prepared || active || awaiting;
    studioLabel(el('speechEdit'),()=>({source:"{value}",values:{value:editing ? studioUi("Скрыть параметры") : studioUi("Тема и параметры")}}));
    el('speechEdit').disabled = busy || recLive;
    el('speechPractice').hidden = !prepared || (data.status === 'saved' && !active && !awaiting);
    el('speechTextFallback').hidden = active || awaiting || (data.status === 'saved' && !editing);
    el('speechPrepare').disabled = locked || recLive;
    el('speechStart').hidden = active || awaiting;
    el('speechStart').disabled = locked || !prepared || dirty || (repeatReady && last?.source_kind === 'text');
    studioLabel(el('speechStart'),()=>({source:"{value}",values:{value:repeatReady ? studioUi("Записать повтор") : studioUi("Записать попытку")}}));
    el('speechFinish').hidden = !active;
    el('speechCancel').hidden = !active;
    el('speechFinish').disabled = busy || !active;
    el('speechCancel').disabled = busy || !active;
    el('speechCountdownCancel').hidden = !countdownAt;
    el('speechTextRun').disabled = locked || !prepared || recLive || dirty || (repeatReady && last?.source_kind === 'microphone');
    const connected = currentInit?.llm_connection;
    const aiReady = !!(currentInit?.config?.cloud_ack && connected?.configured);
    el('speechCoach').disabled = locked || recLive || !last || last.status === 'cancelled' || !aiReady || !!last.review?.created_at;
    studioLabel(el('speechCoach'),()=>({source:"{value}",values:{value:last?.review?.created_at ? studioUi("Разбор сохранён") : last?.previous ? studioUi("Разобрать эту попытку отдельно") : studioUi("Получить разбор")}}));
    el('speechCoach').classList.toggle('primary', !last?.previous);
    el('speechCompare').hidden = !last?.previous || !!last?.comparison;
    el('speechCompareState').hidden = !last?.comparison;
    studioLabel(el('speechCompareState'),"Сравнение сохранено");
    el('speechCompare').disabled = locked || recLive || !aiReady || !!last?.comparison;
    studioLabel(el('speechCompare'),()=>({source:"{value}",values:{value:last?.comparison ? studioUi("Сравнение сохранено") : studioUi("Сравнить по выбранной правке")}}));
    studioLabel(el('speechProvider'),()=>({source:"{value}",values:{value:studioUi("{p0} · в модель уходит текст, не аудио. ",{p0:connected?.label ? (window.BlateroSettingsI18n?.ui(connected.label) ?? connected.label) : studioUi("ИИ не подключён")}) +
      (aiReady ? studioUi("Запрос только по кнопке; API может быть платным.") : studioUi("Настройте подключение и разрешение облака в настройках."))}}));
    el('speechPlanFields').querySelectorAll('input,select').forEach(node => { node.disabled = locked || recLive; });
    const elapsed = active && data.active?.started_at
      ? Math.max(0, Math.floor((Date.now() - Date.parse(data.active.started_at)) / 1000)) : 0;
    const target = Number(data.plan?.target_seconds || 120);
    const remaining = countdownAt ? Math.max(1, Math.ceil((countdownAt - Date.now()) / 1000)) : 0;
    studioLabel(el('speechClock'),()=>({source:"{value}",values:{value:countdownAt ? String(remaining) : active ? clock(elapsed) : clock(target)}}));
    el('speechClock').classList.toggle('speech-overtime', active && elapsed > target);
    el('speechProgress').max = target; el('speechProgress').value = active ? Math.min(target,elapsed) : 0;
    studioLabel(el('speechCue'),()=>({source:"{value}",values:{value:countdownAt ? studioUi("Приготовьтесь…") : active ? (recLive ? studioUi("Говорите") : studioUi("Запись остановлена — сохраните попытку"))
      : repeatReady && last?.source_kind === 'text' ? studioUi("Текстовый повтор: откройте поле ниже")
      : awaiting ? studioUi("Готовим запись…") : repeatReady ? studioUi("Повтор: та же тема, одна правка") : studioUi("Попробуйте объяснить без готового текста")}}));
    studioLabel(el('speechCurrentFocus'),()=>({source:"{value}",values:{value:data.plan?.focus ? studioUi("Задача: {p0}",{p0:data.plan.focus}) : studioUi("{p0} — ориентир, не ограничение. Запись завершаете вы.",{p0:clock(target)})}}));
    studioLabel(el('speechStatus'),()=>({source:"{value}",values:{value:lastError || (busy ? (busyType === 'speech_compare' ? studioUi("Сравниваю две попытки…") : busyType === 'speech_coach' ? studioUi("Разбираю содержание…") : busyType === 'speech_finish' ? studioUi("Завершаю запись и сохраняю последние слова…") : studioUi("Готовлю упражнение…"))
      : countdownAt ? studioUi("После отсчёта появится «Говорите».") : pendingStart ? studioUi("Подтвердите начало записи в открывшемся окне.")
      : active ? studioUi("Запись идёт. Когда закончите мысль, нажмите «Завершить и сохранить».")
      : dirty ? studioUi("Параметры изменились — подготовьте упражнение заново.")
      : last?.status === 'cancelled' ? studioUi("Попытка отменена. Исходная запись сохранена; подготовьте упражнение заново.")
      : last?.comparison?.created_at ? studioUi("Сравнение готово. Прослушайте фрагменты или выберите следующую правку.")
      : last?.review?.created_at ? studioUi("Разбор готов. Выберите одну правку и подготовьте повтор.")
      : data.status === 'saved' ? studioUi("Попытка сохранена. Получите разбор или выберите правку для повтора.")
      : prepared ? studioUi("Нажмите кнопку записи, когда будете готовы. Затем начнётся отсчёт.") : studioUi("Укажите проект и подготовьте упражнение. Микрофон пока выключен."))}}));
    el('speechStatus').style.color = lastError ? 'var(--red)' : '';
    studioLabel(el('speechOutline'),()=>({source:"{value}",values:{value:data.plan ? data.plan.outline.join(' → ') : ''}}));
    el('speechBusy').hidden = !busy;
    studioLabel(el('speechBusyText'),()=>({source:"{value}",values:{value:`${busyType === 'speech_compare' ? studioUi("Сравнение") : busyType === 'speech_coach' ? studioUi("Разбор") : studioUi("Обработка")} · ${clock(Math.max(0, Math.floor((Date.now() - busyAt) / 1000)))}. ${busyType === 'speech_finish' ? studioUi("Ждём последние слова распознавания.") : studioUi("Результат появится здесь.")}`}}));
    for (let i = 1; i <= 4; i++) {
      const step = repeatReady ? 3 : last?.comparison ? 4 : last?.previous ? 3 : last ? 2 : 1;
      el(`speechStep${i}`).classList.toggle('active', step === i);
      if (step === i) el(`speechStep${i}`).setAttribute('aria-current','step');
      else el(`speechStep${i}`).removeAttribute('aria-current');
    }
    if ((active || awaiting || busy) && !timer) timer = setInterval(render, 250);
    if (!(active || awaiting || busy) && timer) { clearInterval(timer); timer = null; }
    // Keep playback and edited fields intact during timer ticks.
    const resultKey = `${last?.id || ''}:${last?.review?.created_at || ''}:${last?.comparison?.created_at || ''}`;
    el('speechResult').hidden = !last || active || awaiting || repeatReady;
    if (el('speechResult').dataset.key !== resultKey) {
      el('speechResult').dataset.key = resultKey;
      stopAudio();
      renderResult(last);
    }
    el('speechRepeat').disabled = locked || recLive || !last || last.status === 'cancelled' || !el('speechRepeatFocus').value.trim();
    el('speechRepeatFocus').disabled = locked || recLive;
    host.querySelectorAll('.speech-note button,.speech-segment button,.speech-comparison button').forEach(button => { button.disabled = locked || recLive; });
    const nextHistory = JSON.stringify([data.history, last?.id]);
    if (historyKey !== nextHistory) { historyKey = nextHistory; renderHistory(last); }
    el('speechHistoryList').querySelectorAll('button').forEach(button => { button.disabled = locked || recLive || button.dataset.id === last?.id; });
    studioLabel(el('speechTitle'),()=>({source:"{value}",values:{value:data.plan?.preset === 'intro' ? studioUi("Представиться") : data.plan?.preset === 'answer' ? studioUi("Ответить на возражение") : target === 120 ? studioUi("Объяснить проект за две минуты") : studioUi("Объяснить проект")}}));
    studioLabel(el('speechLead'),()=>({source:"{value}",values:{value:prepared ? `${data.plan.topic} · ${data.plan.audience}` : studioUi("Кому он нужен, как работает на примере и что делать дальше.")}}));
    document.body.classList.toggle('speech-result', trainingView === 'speech' && !!last && !active && !awaiting);
  }
  function renderHistory(last) {
    el('speechHistoryList').replaceChildren();
    for (const row of data.history || []) {
      const box = document.createElement('div'); box.className = 'speech-history-row';
      const text = document.createElement('span');
      studioLabel(text,()=>({source:"{value}",values:{value:studioUi("{p0} · {p1} · {p2} · {p3} слов{p4}",{p0:new Date(row.created_at).toLocaleString(window.BlateroI18n?.locale || 'ru-RU'),p1:row.plan?.topic || '',p2:row.source_kind === 'text' ? studioUi("текст") : studioUi("микрофон"),p3:row.metrics?.words || 0,p4:row.status === 'cancelled' ? studioUi(" · отменена") : ''})}}));
      const button = document.createElement('button'); studioLabel(button,()=>({source:"{value}",values:{value:row.id === last?.id ? studioUi("Открыта") : studioUi("Открыть")}}));
      button.dataset.id = row.id;
      button.onclick = () => command('speech_select', {attempt_id:row.id});
      box.append(text,button); el('speechHistoryList').append(box);
    }
  }
  function citationBox(label, item, attempt) {
    const box = document.createElement('article'); box.className = 'speech-note';
    const heading = document.createElement('strong'); studioLabel(heading,label);
    const quote = document.createElement('blockquote'); studioValue(quote,item.quote);
    box.append(heading);
    if (item.text) { const p = document.createElement('p'); studioValue(p,item.text); box.append(p); }
    box.append(quote);
    if (item.why) { const p = document.createElement('p'); studioValue(p,item.why); box.append(p); }
    if (item.suggestion) { const p = document.createElement('p'); studioLabel(p,()=>({source:"{value}",values:{value:studioUi("Попробовать: {p0}",{p0:item.suggestion})}})); box.append(p); }
    const segment = attempt.segments.find(s => s.event_id === item.event_id);
    if (segment?.audio_url) { const b = document.createElement('button'); studioLabel(b,"Послушать фрагмент"); b.onclick = () => playSegment(segment); box.append(b); }
    return box;
  }
  function renderResult(last) {
    el('speechSegments').replaceChildren(); el('speechReview').replaceChildren(); el('speechComparison').replaceChildren();
    if (!last) return;
    studioLabel(el('speechResultTitle'),()=>({source:"{value}",values:{value:last.comparison ? studioUi("Что изменилось в повторе") : last.previous ? studioUi("Повтор сохранён") : last.status === 'cancelled' ? studioUi("Попытка отменена") : studioUi("Попытка сохранена")}}));
    el('speechRepeatFocus').value = last.comparison?.next_focus || last.review?.next_focus || last.plan.focus || 'Привести конкретный пример';
    const metrics = last.metrics;
    studioLabel(el('speechMetrics'),()=>({source:"{value}",values:{value:(last.status === 'cancelled' ? studioUi("Попытка отменена · ") : '') + studioUi("{p0} слов · ",{p0:metrics.words}) + (metrics.duration_sec == null
      ? studioUi("надёжной длительности речи нет") : studioUi("{p0} с между началом и концом распознанной речи · примерно {p1} слов/мин",{p0:metrics.duration_sec,p1:metrics.words_per_minute})) +
      studioUi(" · слов и оборотов для прослушивания: {p0}",{p0:metrics.candidate_count})}}));
    studioLabel(el('speechLimits'),()=>({source:"{value}",values:{value:metrics.note + (last.source_kind === 'microphone'
      ? studioUi(" Полнота записи и распознавания автоматически не подтверждена; аудиозапись доступна у фрагментов.")
      : studioUi(" Это текстовая попытка: звучание и длительность не оценивались."))}}));
    if (last.review?.takeaway) el('speechReview').append(citationBox(studioUi("Что понял слушатель"), last.review.takeaway, last));
    const extra = document.createElement('details');
    const summary = document.createElement('summary'); studioLabel(summary,"Остальные наблюдения"); extra.append(summary);
    for (const [group,label] of [['strengths',studioUi("Что получилось")],['improvements',studioUi("Что поправить")]]) {
      for (const [index,item] of (last.review?.[group] || []).entries()) {
        (index === 0 ? el('speechReview') : extra).append(citationBox(label,item,last));
      }
    }
    if (extra.children.length > 1) el('speechReview').append(extra);
    for (const [key,label] of [['next_focus',studioUi("Одна задача для повтора")],['listener_question',studioUi("Возможный вопрос слушателя")]]) {
      if (last.review?.[key]) { const p = document.createElement('p'),heading=document.createElement('span');studioLabel(heading,label);p.append(heading,document.createTextNode(': '+last.review[key]));el('speechReview').append(p); }
    }
    const c = last.comparison;
    if (c && last.previous) {
      const heading = document.createElement('h3'); studioLabel(heading,()=>({source:"{value}",values:{value:{improved:studioUi("Правка сработала"), partial:studioUi("Есть продвижение"), not_yet:studioUi("Правка пока не видна"), unclear:studioUi("Изменение не удалось проверить")}[c.status]}}));
      const p = document.createElement('p'); studioLabel(p,()=>({source:"{value}",values:{value:studioUi("Проверяли: {p0}. {p1}",{p0:c.focus,p1:c.summary})}}));
      const pair = document.createElement('div'); pair.className = 'speech-comparison-pair';
      pair.append(citationBox(studioUi("Первая попытка"), {quote:c.before_quote,event_id:c.before_event_id}, last.previous), citationBox(studioUi("Повтор"), {quote:c.after_quote,event_id:c.after_event_id}, last));
      const why = document.createElement('p'); studioValue(why,c.why);
      const limit = document.createElement('p'); limit.className = 'privacy-note'; studioLabel(limit,"Сравнение по распознанному тексту, не оценка голоса или уверенности. Обе записи сохранены.");
      el('speechComparison').append(heading,p,pair,why,limit);
    } else if (last.comparison_error || last.previous) {
      studioLabel(el('speechComparison'),()=>({source:"{value}",values:{value:last.comparison_error || studioUi("Предыдущая попытка сохранена. Сравните, удалось ли: {p0}.",{p0:last.plan.focus})}}));
    }
    for (const segment of last.segments) {
      const box = document.createElement('article'); box.className = 'speech-segment';
      const p = document.createElement('p');
      const terms = (metrics.candidates || []).filter(item => item.event_id === segment.event_id).map(item => item.quote);
      const pattern = terms.length ? new RegExp('(' + [...new Set(terms)].map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi') : null;
      for (const [index,part] of (pattern ? segment.text.split(pattern) : [segment.text]).entries()) {
        if (pattern && index % 2) { const mark = document.createElement('mark'); studioValue(mark,part); p.append(mark); }
        else p.append(document.createTextNode(part));
      }
      box.append(p);
      if (segment.audio_url) {
        const button = document.createElement('button');
        studioLabel(button,()=>({source:"{value}",values:{value:studioUi("Послушать · {p0} с",{p0:Math.floor(Number(segment.start_ms || 0) / 1000)})}}));
        button.onclick = () => playSegment(segment); box.append(button);
      }
      el('speechSegments').append(box);
    }
  }
  el('speechPrepare').onclick = () => command('speech_prepare', {
    preset:el('speechPreset').value, topic:el('speechTopic').value,
    audience:el('speechAudience').value, goal:el('speechGoal').value,
    focus:el('speechFocus').value, target_seconds:el('speechSeconds').value,
  });
  el('speechPreset').onchange = () => { el('speechSeconds').value = {intro:60, project:120, answer:90}[el('speechPreset').value]; render(); };
  el('speechEdit').onclick = () => { editing = !editing; render(); if (editing) el('speechTopic').focus(); };
  el('speechStart').onclick = () => {
    startToken = null;
    if (recLive) beginCountdown();
    else { pendingStart = true; startToken = crypto.randomUUID().replaceAll('-',''); openStartOverlay('тренировка',null,startToken); }
    render();
  };
  el('speechCountdownCancel').onclick = () => {
    countdownAt = 0; pendingStart = false;
    if (startToken) send({type:'rec',action:'stop',speech_rec_token:startToken});
    startToken = null;
    lastError = studioUi("Старт отменён. Готовую попытку это не меняет."); render();
  };
  el('speechFinish').onclick = () => command('speech_finish', {attempt_id:data.active?.id});
  el('speechCancel').onclick = () => command('speech_cancel', {attempt_id:data.active?.id});
  el('speechTextRun').onclick = () => {
    const text = el('speechText').value, exercise_id = data.plan?.exercise_id;
    if (!pendingText || pendingText.text !== text || pendingText.exercise_id !== exercise_id)
      pendingText = {text, exercise_id, request_id:crypto.randomUUID()};
    keepPendingText();
    command('speech_text', pendingText);
  };
  el('speechCoach').onclick = () => { if (data.last) command('speech_coach', {attempt_id:data.last.id}); };
  el('speechCompare').onclick = () => { if (data.last?.previous) command('speech_compare', {before_id:data.last.previous.id,attempt_id:data.last.id}); };
  el('speechRepeat').onclick = () => {
    const focus = el('speechRepeatFocus').value.trim();
    command('speech_repeat', {focus});
  };
  el('speechPlanFields').addEventListener('input', render);
  el('speechRepeatFocus').addEventListener('input', render);
  for (const id of ['startCancel','startClose']) el(id).addEventListener('click', () => { pendingStart = false; startToken = null; render(); });
  function acceptMessage(message) {
    queueMicrotask(() => {
      if (message.type === 'init') {
        if (session !== message.current_dir || generation !== message.session_generation || serverEpoch !== message.server_epoch) {
          startToken = null; pendingText = null;
          pendingStart = false; countdownAt = 0; lastError = ''; lastPlan = ''; historyKey = ''; editing = false; stopAudio();
          el('speechText').value = '';
          el('speechTopic').value = ''; el('speechAudience').value = 'Коллега, который впервые слышит о проекте';
          el('speechGoal').value = 'Понять назначение проекта, увидеть пример и следующий шаг';
          el('speechFocus').value = ''; el('speechPreset').value = 'project'; el('speechSeconds').value = '120';
        }
        session = message.current_dir; generation = message.session_generation; serverEpoch = message.server_epoch;
        data = message.speech_training || {}; localBusy = false;
        if (!pendingText && (pendingText = readPendingText())) el('speechText').value ||= pendingText.text;
        acceptTextReceipt();
      } else if (message.type === 'speech_training' && message.session === session) {
        if (message.busy && !localBusy) busyAt = Date.now();
        data = message; localBusy = !!message.busy;
        if (message.error) lastError = message.error;
        acceptTextReceipt();
      } else if (message.type === 'status' && localBusy && !message.busy) {
        localBusy = false; lastError = message.text || '';
      } else if (message.type === 'status' && pendingStart && !message.busy && !recLive
          && /^(запись:|ошибка запроса:)/.test(message.text || '')) {
        pendingStart = false; startToken = null; lastError = message.text;
      }
      if (pendingStart && recLive && trainingView === 'speech' && !data.active) {
        beginCountdown();
      }
      render();
    });
  }
  window.addEventListener('blatero:brand-message', event => acceptMessage(event.detail));
  window.addEventListener('blatero:connection', () => { pendingStart = false; countdownAt = 0; startToken = null; localBusy = false; render(); });
  window.BlateroSpeechTraining = {active:() => data.status === 'active'};
  // A fast WebSocket can deliver init before this deferred script has loaded.
  if (currentInit) acceptMessage({...currentInit, type:'init'});
})();
