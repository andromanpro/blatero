'use strict';
let openReportMemoryReview;
// Report completion is not project-memory confirmation. Make that next step explicit.
(() => {
  const el = id => document.getElementById(id);
  const banner = document.createElement('section'); banner.id = 'reportMemoryNext'; banner.hidden = true;
  banner.innerHTML = '<div><b id="reportMemoryTitle"></b><p id="reportMemoryText"></p></div><button id="reportMemoryOpen" class="primary" type="button">Проверить договорённости</button>';
  el('meetingReadBody').before(banner);
  const dialog = document.createElement('dialog'); dialog.id = 'reportMemoryDialog';
  dialog.setAttribute('aria-labelledby','reportMemoryDialogTitle');
  dialog.innerHTML = '<div class="report-memory-heading"><div><h2 id="reportMemoryDialogTitle">Что запомнить к следующей встрече</h2><p id="reportMemorySession"></p></div><button type="button" id="reportMemoryClose" aria-label="Закрыть проверку договорённостей">×</button></div><p>Проверьте формулировки, ответственных и сроки. В память попадут только отмеченные пункты после нажатия «Подтвердить и сохранить». Неотмеченные останутся на потом. Статусы задач не меняются.</p><p id="reportMemoryWarning" class="reading-warning" hidden></p><p id="reportMemoryStatus" role="status" aria-live="polite"></p><div id="reportMemoryRows"></div><div class="report-memory-footer"><button id="reportMemoryLater" type="button">Позже</button><button id="reportMemoryManual" type="button">Добавить вручную</button><button id="reportMemoryRebuild" type="button" hidden>Новый черновик из отчёта</button><button id="reportMemoryReject" type="button">Отклонить оставшееся</button><button id="reportMemorySave" type="button" class="primary">Подтвердить и сохранить</button></div>';
  document.body.append(dialog);
  window.BlateroMeetingI18n?.bindStatic(banner);window.BlateroMeetingI18n?.bindStatic(dialog);
  let data = null, session = '', generation = null, requestVersion = 0, saving = false, pendingCommand = null;
  let bannerKey = '', displayedReport = null;
  const notice = (text,params={}) => meetingLabel(el('reportMemoryStatus'),text,params);
  const points = count => `${count} ${meetingUi({one:'пункт',few:'пункта',many:'пунктов',other:'пункта'}[new Intl.PluralRules(window.BlateroI18n?.language||'ru').select(count)])}`;
  function updateBanner() {
    const state = memoryState?.review || currentInit?.memory?.review || {};
    const key = JSON.stringify([currentInit?.current_dir, state, document.body.dataset.meetingView, currentMeetingResult.has_final, currentMeetingResult.kind, displayedReport]);
    if (key === bannerKey) return; bannerKey = key;
    banner.hidden = document.body.dataset.meetingView !== 'report' || !currentMeetingResult.has_final || currentMeetingResult.kind === 'draft' || state.status === 'test';
    if (banner.hidden) return;
    const saved = Number(state.saved_count) || 0, count = Number(state.pending_count) || 0;
    meetingLabel(el('reportMemoryTitle'),state.status==='reviewed'?'Договорённости проверены':'Следующий шаг — память проекта');
    if(state.status==='reviewed')meetingLabel(el('reportMemoryText'),'Добавлено в память: {count}. Подтверждённые пункты подтянутся при подготовке следующей встречи этого проекта.',{count:saved});
    else if(state.status==='pending')meetingLabel(el('reportMemoryText'),'В черновике {points}. Они ещё не в памяти: проверьте их и сохраните выбранные.',()=>({points:points(count)}));
    else meetingLabel(el('reportMemoryText'),state.status==='stale'?'После подготовки пунктов изменился отчёт или проект. Обновите черновик перед сохранением.':state.status==='needs_scope'?'Укажите проект или рабочую папку встречи: без этого договорённости не с чем связать.':'Отчёт сам по себе не пополняет память. Подготовьте предложения, проверьте их и сохраните нужные для следующей встречи.');
    if(count&&!['needs_scope','reviewed'].includes(state.status))meetingLabel(el('reportMemoryOpen'),'Проверить {points}',()=>({points:points(count)}));
    else meetingLabel(el('reportMemoryOpen'),state.status==='needs_scope'?'Указать проект':state.status==='reviewed'?'Посмотреть память':'Проверить договорённости');
  }
  async function api(action, body) {
    const response = await fetch('/api/sessions/' + encodeURIComponent(session) + '/memory-review' + (action ? '/' + action : ''), {
      method:action ? 'POST' : 'GET', headers:action ? {'Content-Type':'application/json'} : {}, body:action ? JSON.stringify(body || {}) : undefined,
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || meetingUi('Не удалось обновить память'));
    return result;
  }
  function remember(value) {
    data = value;
    if (currentInit?.current_dir === session && currentInit?.session_generation === generation) {
      renderMemory(value); if (currentInit) currentInit.memory = value; updateBanner(); renderWorkflowNext();
    }
  }
  function renderRows(preserve=false) {
    const rows = el('reportMemoryRows'), drafts = new Map();
    if (preserve) for (const card of rows.querySelectorAll('[data-proposal]')) {
      drafts.set(card.dataset.proposal,{baseline:card.dataset.baseline,checked:card.querySelector('[data-pick]').checked,
        fields:Object.fromEntries([...card.querySelectorAll('[data-field]')].map(field=>[field.dataset.field,field.value]))});
    }
    rows.replaceChildren();
    const state = data.review;
    el('reportMemoryWarning').hidden = !state.legacy_draft && state.status !== 'stale';
    meetingLabel(el('reportMemoryWarning'),state.status === 'stale'
      ? 'Отчёт или проект изменились. Старые пункты сохранены, но подтверждение заблокировано. Создайте новый черновик по текущему отчёту; предыдущий останется в резервной копии.'
      : 'Это ранее созданный черновик без контрольной суммы отчёта. Пункты не пересоздавались. Сверьте основания перед подтверждением.');
    for (const item of data.draft.entries || []) {
      const card = document.createElement('article'); card.className = 'report-memory-card'; card.dataset.proposal = item.id;
      card.dataset.baseline=JSON.stringify(item);
      const label = document.createElement('label'), box = document.createElement('input'), heading = document.createElement('b');
      box.type = 'checkbox'; box.checked = true; box.dataset.pick = item.id;
      meetingLabel(heading,({decision:'Решение',commitment:'Действие / обещание',open_question:'Открытый вопрос',fact:'Подтверждённый факт'})[item.kind]||item.kind_label||item.kind);label.append(box, heading); card.append(label);
      const field = (labelText, name, value, multiline=false) => {
        const wrapper=document.createElement('label'),caption=document.createElement('span');meetingLabel(caption,labelText);wrapper.append(caption);
        const input=document.createElement(multiline ? 'textarea':'input'); input.dataset.field=name; input.value=value||'';
        input.maxLength = multiline ? 1200:160; if(multiline)input.rows=3; wrapper.append(input); card.append(wrapper); return input;
      };
      field('Формулировка','text',item.text,true);
      const scopes = document.createElement('select'); scopes.dataset.field='scope';meetingAttr(scopes,'aria-label','Куда сохранить');
      for(const scope of data.scopes){const option=new Option('',scope.scope);meetingLabel(option,'{scope}: {label}',()=>({scope:meetingUi(scope.scope==='project'?'Проект':'Клиент'),label:scope.label}));scopes.add(option);}
      scopes.value=item.scope; card.append(scopes);
      const kinds = document.createElement('select'); kinds.dataset.field='kind';meetingAttr(kinds,'aria-label','Тип записи');
      for(const [kind,name] of [['decision','Решение'],['commitment','Действие / обещание'],['open_question','Открытый вопрос'],['fact','Подтверждённый факт']]){const option=new Option('',kind);meetingLabel(option,name);kinds.add(option);}
      kinds.value=item.kind; card.append(kinds);
      field('Ответственный · если известен','owner',item.owner);field('Срок или условие · если названы','due',item.due);
      const draft=drafts.get(item.id);
      if(draft?.baseline===card.dataset.baseline){box.checked=draft.checked;for(const node of card.querySelectorAll('[data-field]'))node.value=draft.fields[node.dataset.field];}
      if(item.evidence){const evidence=document.createElement('details'), summary=document.createElement('summary'), text=document.createElement('p');meetingLabel(summary,'Основание в отчёте');text.textContent=item.evidence;evidence.append(summary,text);card.append(evidence);}
      rows.append(card);
    }
    if (!data.draft.entries?.length) {
      const message = document.createElement('p');
      if(state.status==='reviewed')meetingLabel(message,'Проверка завершена. Добавлено в память: {count}. Для следующей встречи будут использоваться подтверждённые записи.',{count:state.saved_count});
      else meetingLabel(message,'В явных разделах отчёта не найдены пункты для переноса. Можно добавить договорённость вручную; программа ничего не додумывала.');rows.append(message);
    }
    el('reportMemoryRebuild').hidden=state.status!=='stale';
    el('reportMemoryReject').hidden=!data.draft.entries?.length && state.status!=='empty';
    meetingLabel(el('reportMemoryReject'),state.status==='empty'?'Подтвердить: сохранять нечего':'Отклонить оставшееся');
    updateSelection();
  }
  function updateSelection() {
    const count = el('reportMemoryRows').querySelectorAll('[data-pick]:checked').length;
    el('reportMemorySave').disabled=saving || !data?.review?.can_confirm || !count;
    if(count)meetingLabel(el('reportMemorySave'),'Подтвердить и сохранить ({count})',{count});else meetingLabel(el('reportMemorySave'),'Подтвердить и сохранить');
  }
  el('reportMemoryRows').addEventListener('change',updateSelection);
  function lockRows(ids=null) {
    const controls=[];
    for (const row of el('reportMemoryRows').querySelectorAll('[data-proposal]')) {
      if (ids && !ids.has(row.dataset.proposal)) continue;
      for (const node of row.querySelectorAll('[data-pick],[data-field]')) {
        if (!node.disabled) { node.disabled=true; controls.push(node); }
      }
    }
    return () => { for (const node of controls) node.disabled=false; };
  }
  function stamp(){return {draft_revision:data.review.draft_revision,report_sha256:data.review.report_sha256,scope_stamp:data.review.scope_stamp};}
  async function openReview() {
    if(recLive){alert(meetingUi('Сначала завершите запись.'));return;}
    session=currentInit?.current_dir;generation=currentInit?.session_generation;
    const version=++requestVersion;data=null;pendingCommand=null;saving=false;
    el('reportMemoryRows').replaceChildren();el('reportMemoryWarning').hidden=true;el('reportMemorySave').disabled=true;
    el('reportMemorySession').textContent=currentInit?.meta?.name || session;
    if(!dialog.open)dialog.showModal();notice('Читаю итоговый отчёт и сохранённый черновик…');
    try {
      const value=await api('prepare',{});
      if(version!==requestVersion||!dialog.open)return;
      remember(value);renderRows();notice('Пока это предложения. Память изменится только после вашего подтверждения.');
    } catch(error){if(version===requestVersion)notice(error.message);}
  }
  el('reportMemoryOpen').onclick=()=>{
    const state=memoryState?.review;
    if(state?.status==='needs_scope'){el('settingsBtn').click();return;}
    if(state?.status==='reviewed'){el('memoryBtn').click();return;}
    openReview();
  };
  openReportMemoryReview=()=>el('reportMemoryOpen').click();
  function close(){dialog.close();}
  el('reportMemoryClose').onclick=close;el('reportMemoryLater').onclick=close;
  dialog.addEventListener('close',()=>{requestVersion++;});
  el('reportMemoryManual').onclick=()=>{close();el('memoryBtn').click();el('memoryAddText').closest('details').open=true;el('memoryAddText').focus();};
  el('reportMemorySave').onclick=async()=>{
    if(!data||saving)return;
    const entries=[];
    for(const card of el('reportMemoryRows').querySelectorAll('[data-proposal]')){
      if(!card.querySelector('[data-pick]').checked)continue;
      const entry={id:card.dataset.proposal};for(const field of card.querySelectorAll('[data-field]'))entry[field.dataset.field]=field.value;
      if(!entry.text.trim()){notice('Заполните формулировку выбранного пункта.');return;}entries.push(entry);
    }
    if(!entries.length){notice('Выберите хотя бы один пункт.');return;}
    const submission={...stamp(),entries};
    const signature=JSON.stringify(submission);
    if (pendingCommand?.signature!==signature)
      pendingCommand={signature,body:{...submission,request_id:crypto.randomUUID()}};
    const unlock=lockRows(new Set(entries.map(entry=>entry.id)));
    const version=requestVersion;saving=true;updateSelection();notice('Сохраняю выбранные пункты в локальную память…');
    try{
      const value=await api('confirm',pendingCommand.body);
      if(version!==requestVersion||!dialog.open)return;
      remember(value);pendingCommand=null;renderRows(true);notice('Сохранено в память: {saved}. Осталось проверить: {pending}.',{saved:value.review.saved_count,pending:value.review.pending_count});
    }catch(error){if(version===requestVersion)notice('{message} Несохранённые правки оставлены в форме.',{message:error.message});}
    finally{unlock();if(version===requestVersion){saving=false;updateSelection();}}
  };
  async function mutate(action){
    if(!data||saving)return;
    const warning=action==='reject'?'Отклонить все оставшиеся предложения? Отчёт и уже сохранённая память останутся.':'Создать новый черновик по текущему отчёту? Предыдущий сохранится в резервной копии.';
    if(!confirm(meetingUi(warning)))return;
    const unlock=lockRows();
    const version=requestVersion;saving=true;updateSelection();
    try{const value=await api(action,stamp());if(version!==requestVersion||!dialog.open)return;remember(value);renderRows();notice(action==='reject'?'Оставшиеся предложения отклонены.':'Новый черновик подготовлен локально.');}
    catch(error){if(version===requestVersion)notice(error.message);}
    finally{unlock();if(version===requestVersion){saving=false;updateSelection();}}
  }
  el('reportMemoryReject').onclick=()=>mutate('reject');el('reportMemoryRebuild').onclick=()=>mutate('rebuild');
  // Existing entry point now opens the same editable, guarded review.
  el('memoryAccept').onclick=openReview;
  el('memoryExtract').onclick=openReview;
  document.addEventListener('blatero:meeting-view',updateBanner);
  document.addEventListener('blatero:report-view',event=>{displayedReport=event.detail;updateBanner();});
  const previous=handle;
  handle=function(message){
    previous(message);
    if(dialog.open && (currentInit?.current_dir!==session||currentInit?.session_generation!==generation)){close();notice('Встреча изменилась.');}
    if(['init','memory','report_review'].includes(message.type))updateBanner();
  };
  updateBanner();
})();
