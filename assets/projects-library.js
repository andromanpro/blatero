'use strict';
// Search reads the independent index. Render never scans files or translates source text.
const libraryCatalog = {
  title:['Библиотека знаний','Knowledge library'], kicker:['ЗНАНИЯ / ИСТОЧНИКИ','KNOWLEDGE / SOURCES'],
  intro:['Документы, обсуждения и основания решений. Выберите проект или найдите фрагмент.','Documents, discussions and decision rationale. Choose a project or search for an excerpt.'],
  context:['КОНТЕКСТ','CONTEXT'], indexed:['записей в поиске','searchable entries'], health:['Состояние базы знаний','Knowledge library status'],
  manual:['Пауза по вашему выбору','Paused by you'], recording:['Пауза на время записи встречи','Paused while recording a meeting'],
  systemLoad:['Пауза: компьютер занят','Paused: system load'], setup:['Нужно подключить базу','Library setup required'],
  offline:['Обработчик не отвечает','Worker is not responding'], background:['Обновление в фоне','Updating in the background'],
  processed:['Последняя обработка:','Last processed:'], queued:['в очереди','queued'], attention:['требуют внимания','need attention'],
  resume:['Продолжить обновление','Resume updates'], pause:['Приостановить','Pause'], opening:['Открываю библиотеку…','Opening library…'],
  search:['Поиск по общей базе знаний','Search the knowledge library'], placeholder:['Задача, метод или фрагмент документа…','Task, method or document excerpt…'],
  find:['Найти ↗','Search ↗'], materials:['Материалы','Materials'], all:['Всё','All'], freshness:['Актуальность','Freshness'],
  allStates:['Все состояния','All states'], found:['Найдено: {count}','Found: {count}'], oneTask:['одна задача','one task'], allTasks:['Все задачи проекта','All project tasks'],
  passport:['Паспорт проекта','Project overview'], task:['Досье задачи','Task dossier'], decision:['Решение','Decision'], fact:['Факт','Fact'],
  constraint:['Ограничение','Constraint'], question:['Открытый вопрос','Open question'], document:['Документ','Document'], session:['Обсуждение','Discussion'], material:['Материал','Material'],
  source:['Источник','Source'], draft:['Предложение','Proposal'], confirmed:['Подтверждено','Confirmed'],
  current:['По последнему снимку','As last indexed'], pending:['Изменение в очереди','Change queued'], needsReview:['Нужна перепроверка','Needs review'],
  missing:['Источник недоступен','Source unavailable'], error:['Ошибка обновления','Update error'],
  noMatches:['Совпадений пока нет','No matches yet'], notConnected:['Библиотека ещё не подключена','Library is not connected'],
  trySearch:['Измените запрос или фильтр. Новые материалы появятся после фоновой обработки.','Change the query or filter. New materials appear after background processing.'],
  connectHelp:['Настройте источники и запустите обработчик. Порядок — в справке «Библиотека знаний».','Configure sources and start the worker. See Knowledge Library in Help.'],
  previous:['← Предыдущие','← Previous'], next:['Следующие →','Next →'], range:['{start}–{end} из {total}','{start}–{end} of {total}'],
  details:['Как обновляется библиотека · источники и ограничения','Library updates · sources and limits'], independent:['Независимо от открытого окна','Independent of the open window'],
  workerHelp:['Обработчик читает выбранные документы и доступную историю приложений. Изменения объединяются; текст извлекается последовательно. Во время записи встречи или высокой нагрузки — пауза.','The worker reads selected documents and available app history. Changes are coalesced and text is extracted sequentially. Processing pauses during recording or high system load.'],
  trees:['Документальных деревьев: {count}.','Document trees: {count}.'], treeLimit:['Достигнут лимит обхода некоторых деревьев.','Some trees reached the scan limit.'],
  folder:['Папка знаний:','Knowledge folder:'], notConfigured:['не настроена','not configured'], git:['Git-снимок:','Git snapshot:'], notCreated:['Ещё не создан','Not created yet'],
  originFreshness:['Происхождение и свежесть','Provenance and freshness'], freshnessHelp:['«По последнему снимку» означает, что источник проиндексирован. Это не проверка правильности и не приёмка. При изменении основания связанное знание получает отметку «Нужна перепроверка».','“As last indexed” means the source has been indexed, not that it is correct or accepted. If supporting evidence changes, related knowledge is marked “Needs review”.'],
  connected:['подключён','connected'], unavailable:['недоступен','unavailable'], journals:['журналов: {count}','journals: {count}'],
  limits:['Без OCR; до 10 МБ на файл, до 250 000 символов извлечения и до 32 000 символов на сообщение. Ограничение показывается в материале. Приложения без доступной истории требуют адаптера или экспорта.','No OCR; up to 10 MB per file, 250,000 extracted characters and 32,000 characters per message. Truncation is marked on the item. Apps without accessible history need an adapter or export.'],
  workerError:['Сбой обработчика:','Worker failure:'], processingErrors:['Ошибки обработки · {count}','Processing errors · {count}'], firstTen:['(первые 10)','(first 10)'],
  attempts:['попыток: {count}','attempts: {count}'], retry:['Повторить ошибки','Retry failed items'], close:['Закрыть','Close'], revision:['редакция {count}','revision {count}'],
  truncated:['Текст сокращён по лимиту. Полный оригинал находится по пути ниже.','Text was truncated to the limit. The full original is at the path below.'],
  historicalVersion:['Архивная редакция. Для актуального содержания откройте материал заново из поиска.','Archived revision. Open the item again from search for its current content.'],
  summaryOnly:['Снимок описания материала. Полный текст может быть отдельным документом в библиотеке.','Snapshot of the item description. The full text may be a separate library document.'],
  provenance:['Происхождение','Provenance'], historical:['Восстановлено из истории. Актуальность содержания требует сверки.','Recovered from history. Check whether the content is still current.'],
  evidenceMatches:['Основание совпадает с прочитанной версией','Evidence matches the version read'], evidenceChanged:['Основание изменилось или недоступно','Evidence changed or is unavailable'],
  linkedTask:['Связанная задача','Linked task'], openTask:['Открыть связанную задачу ↗','Open linked task ↗'], proposeSource:['Зафиксировать знание по этому источнику','Propose knowledge from this source'],
  confirm:['Подтвердить содержание','Confirm content'], versions:['Предыдущие версии · {count}','Previous revisions · {count}'], latest:['(последние)','(latest)'],
  confirmedNotice:['Содержание подтверждено. Приёмка задачи выполняется отдельно.','Content confirmed. Task acceptance is separate.'],
  propose:['Зафиксировать знание','Propose knowledge'], proposeHelp:['Предложение сохранится с прочитанной версией источника. Подтверждение — отдельное действие.','The proposal keeps the source version you read. Confirmation is a separate action.'],
  name:['Название','Title'], type:['Тип','Type'], body:['Содержание','Content'], saveProposal:['Сохранить предложение','Save proposal'],
  taskHelp:['Документы, обсуждения и объяснения решений, связанные с задачей.','Documents, discussions and decision rationale linked to this task.'], openDossier:['Открыть досье в библиотеке ↗','Open dossier in library ↗'],
  saveError:['Не удалось сохранить знание','Could not save knowledge'], waitingCommand:['Запрос сохранён в очереди. Дождитесь обработчика; повторно отправлять не нужно. Код: {id}','The request is queued. Wait for the worker; do not submit it again. ID: {id}'],
  edit:['Изменить знание','Edit knowledge'], editHelp:['Изменение сохранится новой редакцией как предложение. Прежняя редакция останется в истории; содержание нужно подтвердить заново.','Changes become a new proposal revision. The previous revision stays in history; confirm the content again.'],
  discard:['Отменить изменения знания?','Discard changes to this knowledge?'],
  saving:['Сохраняем…','Saving…'],
  never:['Ещё не было','Not yet'], msk:['МСК','MSK']
};
window.BlateroI18n?.register(Object.fromEntries(Object.entries(libraryCatalog).map(([key,pair])=>['library.'+key,pair])));
function libraryUI(key,values={}) {
  if(window.BlateroI18n)return window.BlateroI18n.t('library.'+key,values);
  return (libraryCatalog[key]?.[0]??key).replace(/\{(\w+)\}/g,(match,name)=>Object.hasOwn(values,name)?String(values[name]):match);
}
function libraryHTML(key,values={}) {
  return `<span data-library-key="${key}" data-library-params="${esc(JSON.stringify(values))}" lang="${window.BlateroI18n?.language||'ru'}">${esc(libraryUI(key,values))}</span>`;
}
function libraryAttr(name,key) {return `${name}="${esc(libraryUI(key))}" data-library-${name}="${key}"`;}
function libraryOption(value,key,selected='') {return `<option value="${value}" data-library-key="${key}" ${selected===value?'selected':''}>${esc(libraryUI(key))}</option>`;}
function libraryLocale(){return window.BlateroI18n?.locale||'ru-RU';}
const libraryKinds={passport:'passport',task:'task',decision:'decision',fact:'fact',constraint:'constraint',open_question:'question',document:'document',session:'session',material:'material'};
const libraryStates={source:'source',draft:'draft',confirmed:'confirmed',accepted:'confirmed'};
const libraryFreshnessLabels={current:'current',pending:'pending',needs_review:'needsReview',missing:'missing',error:'error'};
function libraryMapped(map,value){return map[value]?libraryHTML(map[value]):esc(value);}
function libraryDateText(value){return new Date(value).toLocaleString(libraryLocale(),{timeZone:'Europe/Moscow',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' '+libraryUI('msk');}
function libraryDate(value){return value?`<time data-library-date="${esc(value)}">${esc(libraryDateText(value))}</time>`:libraryHTML('never');}
function libraryApply(scope=document){
  for(const node of scope.querySelectorAll('[data-library-key]')){
    node.textContent=libraryUI(node.dataset.libraryKey,JSON.parse(node.dataset.libraryParams||'{}'));
    node.lang=window.BlateroI18n?.language||'ru';
  }
  for(const name of ['aria-label','placeholder'])for(const node of scope.querySelectorAll('[data-library-'+name+']'))node.setAttribute(name,libraryUI(node.getAttribute('data-library-'+name)));
  for(const node of scope.querySelectorAll('[data-library-date]'))node.textContent=libraryDateText(node.dataset.libraryDate);
  for(const node of scope.querySelectorAll('[data-library-count]'))node.textContent=Number(node.dataset.libraryCount).toLocaleString(libraryLocale());
}
document.addEventListener('blatero:language',()=>libraryApply());
let libraryQuery='',libraryKind='',libraryFreshness='',libraryOffset=0,libraryTask=new URLSearchParams(location.search).get('ktask')||'';
let libraryCache=null,libraryKey='',libraryFetched=0,libraryVersion=0,libraryItem=null,libraryReference=null,libraryProject=null;
const libraryCommands=new Map();
async function libraryWrite(path,body){
  const bytes=new TextEncoder().encode(JSON.stringify([path,body]));
  const key='blatero.libraryCommand.'+[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
  let id=libraryCommands.get(key);try{id||=sessionStorage.getItem(key);}catch{}
  id||=crypto.randomUUID();libraryCommands.set(key,id);try{sessionStorage.setItem(key,id);}catch{}
  const clear=()=>{libraryCommands.delete(key);try{sessionStorage.removeItem(key);}catch{}};
  let command=await api(path,{...body,command_id:id});
  for(let attempt=0;attempt<60;attempt++){
    if(command.state==='complete'){clear();return command.result;}
    if(command.state==='failed'){clear();throw Error(command.error?.message||libraryUI('saveError'));}
    await new Promise(resolve=>setTimeout(resolve,500));
    command=await api('library/commands/'+command.command_id);
  }
  throw Error(libraryUI('waitingCommand',{id:command.command_id}));
}
const libraryOriginalRender=render;
render=function(){
  document.body.classList.toggle('library-view',view==='knowledge');
  if(view!=='knowledge'){libraryKey='';libraryVersion++;return libraryOriginalRender();}
  document.body.classList.remove('daily-view');renderOverview(filtered());
  const project=$('#projectFilter').value;
  if(libraryProject!==project){libraryOffset=0;libraryProject=project;}
  const key=JSON.stringify([project,libraryQuery,libraryKind,libraryFreshness,libraryOffset,libraryTask]);
  if(key===libraryKey&&Date.now()-libraryFetched<15000&&$('#libraryScreen'))return;
  const scopeChanged=key!==libraryKey;libraryKey=key;const version=++libraryVersion;
  if(scopeChanged||!$('#libraryScreen'))$('#content').innerHTML=`<p class="quiet">${libraryHTML('opening')}</p>`;
  action(async()=>{
    const query=new URLSearchParams({q:libraryQuery,offset:String(libraryOffset),limit:'24'});
    if(project)query.set('project_id',project==='__general'?'__unbound':project);
    if(libraryKind)query.set('kind',libraryKind);if(libraryFreshness)query.set('freshness',libraryFreshness);if(libraryTask)query.set('task_id',libraryTask);
    const [result,health]=await Promise.all([api('library?'+query),api('library/status')]);
    if(view!=='knowledge'||version!==libraryVersion)return;
    libraryFetched=Date.now();libraryCache={result,health};
    if($('#libraryScreen')?.contains(document.activeElement)&&document.activeElement.matches('input,textarea'))return;
    drawLibrary(result,health);
  });
};
function drawLibrary(result,health){
  const worker=health.worker||{},coverage=health.coverage||{},documents=Object.values(coverage.documents||{});
  const reason={manual:'manual',recording:'recording',system_load:'systemLoad'}[worker.paused_reason];
  const status=!health.configured?'setup':reason||(!health.running?'offline':'background');
  const total=health.items||0,stale=Object.entries(health.freshness||{}).filter(([k])=>!['current','pending'].includes(k)).reduce((n,[,v])=>n+v,0)+Math.max(0,(health.error_count||0)-(health.freshness?.error||0));
  $('#content').innerHTML=`<div id="libraryScreen">
    <section class="library-banner"><div><span class="library-kicker">${libraryHTML('kicker')}</span><h3>${libraryHTML('title')}</h3><p>${libraryHTML('intro')}</p></div><div class="library-orbit" aria-hidden="true">${libraryHTML('context')}<i></i><b data-library-count="${total}">${total.toLocaleString(libraryLocale())}</b><small>${libraryHTML('indexed')}</small></div></section>
    <section class="library-health" ${libraryAttr('aria-label','health')}><div><span class="library-dot ${health.running&&!reason?'live':''}" aria-hidden="true"></span><strong>${libraryHTML(status)}</strong><small>${libraryHTML('processed')} ${libraryDate(health.last_success?.at)}</small></div><div class="library-health-count"><b>${health.pending||0}</b>${libraryHTML('queued')}</div><div class="library-health-count"><b>${stale}</b>${libraryHTML('attention')}</div>${health.configured?`<button id="libraryPause">${libraryHTML(health.paused?'resume':'pause')}</button>`:''}</section>
    <form id="librarySearchForm" class="library-search"><label class="sr-only" for="librarySearch">${libraryHTML('search')}</label><input id="librarySearch" type="search" value="${esc(libraryQuery)}" ${libraryAttr('placeholder','placeholder')} maxlength="300"><button class="primary">${libraryHTML('find')}</button></form>
    <div class="library-filters"><label>${libraryHTML('materials')}<select id="libraryKind">${libraryOption('','all',libraryKind)}${Object.entries(libraryKinds).map(([k,v])=>libraryOption(k,v,libraryKind)).join('')}</select></label><label>${libraryHTML('freshness')}<select id="libraryFreshness">${libraryOption('','allStates',libraryFreshness)}${Object.entries(libraryFreshnessLabels).map(([k,v])=>libraryOption(k,v,libraryFreshness)).join('')}</select></label><span class="quiet library-found">${libraryHTML('found',{count:result.total})}${libraryTask?' · '+libraryHTML('oneTask'):''}${libraryQuery?' · «'+esc(libraryQuery)+'»':''}</span>${libraryTask?`<button id="libraryClearTask">${libraryHTML('allTasks')}</button>`:''}</div>
    <div class="library-results">${result.items.map(item=>`<article class="library-card"><div class="library-card-meta">${libraryMapped(libraryKinds,item.kind)}<span class="library-freshness ${item.freshness!=='current'?'attention':''}">${libraryMapped(libraryFreshnessLabels,item.freshness)}</span></div><button class="library-title" data-library-id="${esc(item.id)}">${esc(item.title)} <span aria-hidden="true">↗</span></button><p class="library-snippet">${esc(item.snippet)}</p><div class="library-card-footer"><span>${esc(projectName(item.project_id))} · ${libraryMapped(libraryStates,item.state)}</span>${libraryDate(item.indexed_at)}</div></article>`).join('')||`<div class="library-empty"><span aria-hidden="true">◇</span><h3>${libraryHTML(health.configured?'noMatches':'notConnected')}</h3><p>${libraryHTML(health.configured?'trySearch':'connectHelp')}</p></div>`}</div>
    <div class="library-pagination"><button id="libraryPrevious" ${result.offset===0?'disabled':''}>${libraryHTML('previous')}</button>${libraryHTML('range',{start:result.total?result.offset+1:0,end:Math.min(result.offset+result.limit,result.total),total:result.total})}<button id="libraryNext" ${result.offset+result.limit>=result.total?'disabled':''}>${libraryHTML('next')}</button></div>
    <details class="library-details"><summary>${libraryHTML('details')}</summary><div class="library-detail-grid"><div><h4>${libraryHTML('independent')}</h4><p>${libraryHTML('workerHelp')}</p><p>${libraryHTML('trees',{count:documents.length})} ${documents.some(d=>d.truncated)?libraryHTML('treeLimit'):''}</p><p>${libraryHTML('folder')} <code>${health.notes_root?esc(health.notes_root):libraryHTML('notConfigured')}</code></p><p>${libraryHTML('git')} ${health.git?.ok?libraryDate(health.git.at):health.git?.error?esc(health.git.error):libraryHTML('notCreated')}.</p></div><div><h4>${libraryHTML('originFreshness')}</h4><p>${libraryHTML('freshnessHelp')}</p>${Object.entries(coverage.sessions||{}).map(([k,v])=>`<p><b>${esc(k)}</b>: ${v.available?libraryHTML('connected')+(v.files!==undefined?' · '+libraryHTML('journals',{count:v.files}):''):libraryHTML('unavailable')+' · '+esc(v.error||'')}</p>`).join('')}<p>${libraryHTML('limits')}</p></div></div>${worker.error?`<p class="source-warning">${libraryHTML('workerError')} ${esc(worker.error)}</p>`:''}${health.errors?.length?`<div class="library-errors"><h4>${libraryHTML('processingErrors',{count:health.errors.length})} ${health.errors.length===10?libraryHTML('firstTen'):''}</h4>${health.errors.map(e=>`<p><b>${esc(e.path||e.kind)}</b> · ${esc(e.error)} · ${libraryHTML('attempts',{count:e.attempts})}</p>`).join('')}<button id="libraryRetry">${libraryHTML('retry')}</button></div>`:''}</details>
  </div>`;
  $('#librarySearchForm').onsubmit=e=>{e.preventDefault();libraryQuery=$('#librarySearch').value;libraryOffset=0;libraryKey='';render();};
  $('#libraryKind').onchange=e=>{libraryKind=e.target.value;libraryOffset=0;libraryKey='';render();};
  $('#libraryFreshness').onchange=e=>{libraryFreshness=e.target.value;libraryOffset=0;libraryKey='';render();};
  $('#libraryPrevious').onclick=()=>{libraryOffset=Math.max(0,libraryOffset-24);libraryKey='';render();};
  $('#libraryNext').onclick=()=>{libraryOffset+=24;libraryKey='';render();};
  if($('#libraryClearTask'))$('#libraryClearTask').onclick=()=>{libraryTask='';const url=new URL(location.href);url.searchParams.delete('ktask');history.replaceState({},'',url);libraryKey='';render();};
  if($('#libraryPause'))$('#libraryPause').onclick=()=>action(async()=>{await api('library/pause',{paused:!health.paused});libraryKey='';render();});
  if($('#libraryRetry'))$('#libraryRetry').onclick=()=>action(async()=>{await api('library/retry',{});libraryKey='';render();});
}
let libraryItemEpoch=0;
function libraryDialog(){
  let dialog=$('#libraryDialog');
  if(!dialog){dialog=document.createElement('dialog');dialog.id='libraryDialog';dialog.className='task-dialog';dialog.innerHTML=`<div class="dialog-heading"><h2 id="libraryDetailTitle"></h2><button data-close ${libraryAttr('aria-label','close')}>×</button></div><div id="libraryDetail"></div>`;document.body.append(dialog);}
  if(!dialog.__guardedClose){
    dialog.__guardedClose=true;const close=dialog.close.bind(dialog);
    dialog.close=(...args)=>{libraryItemEpoch++;close(...args);};
    dialog.addEventListener('cancel',()=>libraryItemEpoch++);
  }
  return dialog;
}
async function openLibraryItem(id,revision){
  const ticket=++libraryItemEpoch;
  const item=await api('library/item/'+encodeURIComponent(id)+(revision?'?revision='+encodeURIComponent(revision):''));
  if(ticket!==libraryItemEpoch)return;
  libraryItem=item;
  const dialog=libraryDialog();$('#libraryDetailTitle').textContent=item.title;
  const isNote=/^[a-f0-9-]{36}$/.test(item.id)&&!item.metadata.historical_version;
  const linked=[...new Set(item.linked_tasks||[])].filter(id=>id!==item.task_id);
  $('#libraryDetail').innerHTML=`<div class="library-detail-tags">${libraryMapped(libraryKinds,item.kind)}${libraryMapped(libraryStates,item.state)}<span class="${item.freshness!=='current'?'source-warning':''}">${libraryMapped(libraryFreshnessLabels,item.freshness)}</span></div><p class="quiet">${esc(projectName(item.project_id))} · ${libraryHTML('revision',{count:item.revision})} · ${libraryDate(item.indexed_at)}</p>${item.metadata.truncated?`<p class="source-warning">${libraryHTML('truncated')}</p>`:''}${item.metadata.historical_version?`<p class="source-warning">${libraryHTML('historicalVersion')}</p>`:''}${item.metadata.summary_only?`<p class="quiet">${libraryHTML('summaryOnly')}</p>`:''}<pre class="library-text">${esc(item.body)}</pre>
    <section class="detail-section"><h3>${libraryHTML('provenance')}</h3><p class="library-locator">${esc(item.locator)}</p>${item.metadata.historical?`<p class="source-warning">${libraryHTML('historical')}</p>`:''}${item.dependencies.map(ref=>`<div class="entry"><button data-library-id="${esc(ref.source_id)}">${esc(ref.title||ref.source_id)} ↗</button><small>${libraryHTML(ref.source_hash===ref.current_hash&&ref.freshness==='current'?'evidenceMatches':'evidenceChanged')}</small></div>`).join('')}${item.task_id?`<button data-open="${esc(item.task_id)}">${libraryHTML('openTask')}</button>`:''}${linked.map(id=>`<p><button data-open="${esc(id)}">${state.tasks.find(t=>t.id===id)?.title?esc(state.tasks.find(t=>t.id===id).title):libraryHTML('linkedTask')} ↗</button></p>`).join('')}</section>
    <div class="library-note-actions">${item.freshness==='current'&&!item.metadata.historical_version?`<button id="libraryPropose">${libraryHTML('proposeSource')}</button>`:''}${isNote&&item.state==='draft'&&item.freshness==='current'?`<button id="libraryConfirm" class="primary">${libraryHTML('confirm')}</button>`:''}</div>${item.history.length?`<details class="library-history"><summary>${libraryHTML('versions',{count:item.history.length})} ${item.history.length===20?libraryHTML('latest'):''}</summary>${item.history.map(h=>`<p><button data-library-id="${esc(item.id)}" data-library-revision="${h.revision}">${libraryHTML('revision',{count:h.revision})} · ${libraryDate(h.recorded_at)} ↗</button></p>`).join('')}</details>`:''}`;
  if(!dialog.open)dialog.showModal();
  $('#libraryPropose')?.addEventListener('click',()=>openLibraryNote(item));
  if(isNote){const edit=document.createElement('button');edit.id='libraryEdit';edit.innerHTML=libraryHTML('edit');edit.onclick=()=>openLibraryNote(item,true);$('#libraryDetail .library-note-actions').prepend(edit);}
  $('#libraryConfirm')?.addEventListener('click',()=>action(async()=>{await libraryWrite('library/confirm',{id:item.id,revision:item.revision});if(ticket===libraryItemEpoch)await openLibraryItem(item.id);libraryKey='';render();toast(libraryUI('confirmedNotice'));}));
}
let libraryNoteEpoch=0;
function openLibraryNote(item,editing=false){
  libraryReference={item,editing,epoch:++libraryNoteEpoch};
  let dialog=$('#libraryNoteDialog');
  if(!dialog){
    dialog=document.createElement('dialog');dialog.id='libraryNoteDialog';
    dialog.innerHTML=`<form id="libraryNoteForm"><div class="dialog-heading"><h2>${libraryHTML('propose')}</h2><button type="button" data-close ${libraryAttr('aria-label','close')}>×</button></div><p class="quiet">${libraryHTML('proposeHelp')}</p><label>${libraryHTML('name')}<input name="title" required maxlength="240"></label><label>${libraryHTML('type')}<select name="kind">${['decision','fact','constraint','open_question'].map(k=>libraryOption(k,libraryKinds[k])).join('')}</select></label><label>${libraryHTML('body')}<textarea name="body" required maxlength="20000" rows="8"></textarea></label><button class="primary">${libraryHTML('saveProposal')}</button></form>`;
    document.body.append(dialog);
    const close=dialog.close.bind(dialog);
    dialog.close=()=>{if(dialog.__saving)return;if(dialog.__dirty?.()&&!confirm(libraryUI('discard')))return;close();};
    dialog.addEventListener('cancel',e=>{e.preventDefault();dialog.close();});
    $('#libraryNoteForm').onsubmit=e=>{
      e.preventDefault();const form=e.target,fields=Object.fromEntries(new FormData(form)),context=libraryReference,ref=context.item,button=form.querySelector('button.primary');
      action(async()=>{const controls=[...form.querySelectorAll('input,textarea,select,button')];dialog.__saving=true;controls.forEach(node=>node.disabled=true);button.innerHTML=libraryHTML('saving');try{
        const references=context.editing?ref.dependencies.map(x=>({id:x.source_id,content_hash:x.source_hash})):[{id:ref.id,content_hash:ref.content_hash}];
        const result=await libraryWrite('library/notes',{...fields,project_id:ref.project_id,task_id:ref.task_id,references,...(context.editing?{id:ref.id,revision:ref.revision}:{})});
        if(libraryReference.epoch!==context.epoch)return;
        dialog.__saving=false;dialog.__dirty=()=>false;dialog.close();await openLibraryItem(result.id);libraryKey='';render();
      }finally{if(libraryReference.epoch===context.epoch){dialog.__saving=false;controls.forEach(node=>node.disabled=false);button.innerHTML=libraryHTML('saveProposal');}}});
    };
    window.addEventListener('beforeunload',e=>{if(dialog.open&&dialog.__dirty?.()){e.preventDefault();e.returnValue='';}});
  }
  const form=$('#libraryNoteForm');form.reset();form.querySelector('button.primary').disabled=false;
  form.querySelector('h2').innerHTML=libraryHTML(editing?'edit':'propose');form.querySelector('p.quiet').innerHTML=libraryHTML(editing?'editHelp':'proposeHelp');
  form.elements.title.value=item.title.slice(0,240);
  if(editing){form.elements.kind.value=item.kind;form.elements.body.value=item.body;}
  const baseline=JSON.stringify(Object.fromEntries(new FormData(form)));
  dialog.__dirty=()=>JSON.stringify(Object.fromEntries(new FormData(form)))!==baseline;
  if(!dialog.open)dialog.showModal();
}
document.addEventListener('click',e=>{const button=e.target.closest('[data-library-id]');if(button)action(()=>openLibraryItem(button.dataset.libraryId,button.dataset.libraryRevision));if(e.target.closest('#libraryDetail [data-open]'))$('#libraryDialog').close();});
const libraryOpenTask=openTask;
openTask=async function(id){const opening=libraryOpenTask(id),ticket=taskOpenEpoch;await opening;if(ticket!==taskOpenEpoch||selected?.task.id!==id)return;const t=selected.task;$('#detail').insertAdjacentHTML('beforeend',`<section class="detail-section"><h3>${libraryHTML('title')}</h3><p class="quiet">${libraryHTML('taskHelp')}</p><a class="library-task-link" href="/projects?${new URLSearchParams({view:'knowledge',ktask:t.id,...(t.project_id?{project:t.project_id}:{})})}">${libraryHTML('openDossier')}</a></section>`);};
setInterval(()=>{if(view==='knowledge'&&!document.hidden)render();},15000);
