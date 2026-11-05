'use strict';
// One stage model drives navigation, empty states and saved read-only results.
let openMeetingResult;
(() => {
  const el = id => document.getElementById(id);
  const zone = el('hintzone');
  const nav = document.createElement('nav'); nav.id='meetingViewTabs';
  nav.setAttribute('aria-label','Разделы встречи');
  nav.innerHTML='<button type="button" data-meeting-view="live">Встреча</button><button type="button" data-meeting-view="report">Отчёт</button><button type="button" data-meeting-view="transcript">Транскрипт</button><button type="button" data-meeting-view="materials">Материалы</button>';
  zone.prepend(nav);
  window.BlateroMeetingI18n?.bindStatic(nav);
  const panel=document.createElement('section');panel.id='meetingReadPanel';panel.hidden=true;
  panel.setAttribute('aria-labelledby','meetingReadTitle');
  panel.innerHTML='<div class="meeting-read-heading"><div><span id="meetingReadKicker"></span><h2 id="meetingReadTitle"></h2></div><div class="meeting-read-actions"><a id="meetingDownload" class="primary" hidden>Скачать DOCX</a><button type="button" id="meetingReadReview" hidden>Проверить черновик</button><button type="button" id="meetingReadNew">Новая встреча</button><details><summary>Ещё</summary><div class="meeting-read-more"><button type="button" id="meetingReadFolder">Открыть папку результатов</button><button type="button" id="meetingReadAudio">Аудио и говорящие</button><button type="button" id="meetingReadContinue">Продолжить запись…</button><button type="button" id="meetingReadRebuild">Сформировать заново…</button><button type="button" id="meetingReadPrint">Печать</button></div></details></div></div><p id="meetingReadNotice" role="status"></p><div id="meetingReadStatus" role="status"></div><button type="button" id="meetingReadRetry" hidden>Повторить загрузку</button><nav id="meetingReportToc" aria-label="Разделы отчёта"></nav><article id="meetingReadBody" class="meeting-paper"></article>';
  nav.after(panel);
  window.BlateroMeetingI18n?.bindStatic(panel);
  const readingFont=document.createElement('div');readingFont.className='meeting-read-actions hint-size';readingFont.setAttribute('role','group');readingFont.setAttribute('aria-label','Размер текста документа');
  readingFont.innerHTML='<button id="readingSmaller" type="button" aria-label="Уменьшить текст документа">A−</button><button id="readingReset" type="button" title="Обычный размер">100%</button><button id="readingLarger" type="button" aria-label="Увеличить текст документа">A+</button>';
  panel.querySelector('.meeting-read-actions').before(readingFont);
  window.BlateroMeetingI18n?.bindStatic(readingFont);
  function syncReadingFont(){
    el('readingReset').textContent=el('hintSizeReset').textContent;
    el('readingSmaller').disabled=el('hintSmaller').disabled;el('readingLarger').disabled=el('hintLarger').disabled;
  }
  for(const [button,target] of [['readingSmaller','hintSmaller'],['readingReset','hintSizeReset'],['readingLarger','hintLarger']])
    el(button).onclick=()=>{el(target).click();syncReadingFont();};
  const overview=document.createElement('section');overview.id='meetingSavedOverview';overview.hidden=true;
  overview.innerHTML='<h2>Запись сохранена</h2><p>Проверьте говорящих и текст, затем подготовьте итог. Подсказки можно открыть отдельно.</p><div><button type="button" id="savedReviewAudio">Аудио и говорящие</button><button type="button" id="savedReviewTranscript">Читать транскрипт</button><button type="button" id="savedReviewReport" class="primary">Подготовить отчёт</button></div>';
  panel.after(overview);
  window.BlateroMeetingI18n?.bindStatic(overview);
  let session='', generation=null, view='live', phase='', manual=false, controller=null, requestVersion=0, loadedKey='', renderedSession='', renderedView='';
  let materialsSignature='', materialsRevision=0;
  const cachedViews=new Map();
  function postStage(stage){return ['done','stale','draft','review'].includes(stage);}
  function defaultView(stage){return ['done','stale','draft'].includes(stage)?'report':postStage(stage)?'overview':'live';}
  function remember(){cachedViews.set(session,view);if(cachedViews.size>30)cachedViews.delete(cachedViews.keys().next().value);}
  function setView(next, explicit=true) {
    if(next==='report'&&!currentMeetingResult.has_final&&!currentMeetingResult.has_draft)next='overview';
    if(view!==next)zone.scrollTop=0;
    view=next;manual=explicit;if(explicit)remember();
    reconcile();
  }
  openMeetingResult=()=>setView('report');
  nav.addEventListener('click',event=>{const button=event.target.closest('[data-meeting-view]');if(button)setView(button.dataset.meetingView);});
  el('meetingReadNew').onclick=()=>el('quickMeetingBtn').click();
  el('meetingReadFolder').onclick=()=>send({type:'open_report_folder'});
  el('meetingReadContinue').onclick=()=>el('recbtn').click();
  el('meetingReadAudio').onclick=()=>el('analysisBtn').click();
  el('meetingReadRebuild').onclick=()=>el('reportReviewRegenerate').click();
  el('meetingReadPrint').onclick=()=>window.print();
  el('meetingReadReview').onclick=()=>send({type:'report_review',action:'open'});
  el('savedReviewAudio').onclick=()=>el('analysisBtn').click();
  el('savedReviewTranscript').onclick=()=>setView('transcript');
  el('savedReviewReport').onclick=()=>el('report').click();
  el('meetingReadRetry').onclick=()=>{loadedKey='';loadReading(true);};
  // A direct request for a live hint deliberately returns to the hint area.
  el('pulse').addEventListener('click',()=>setView('live'));
  for(const id of ['memoryBtn','sideToggleSettings','sideRestore','agendaBtn'])
    el(id)?.addEventListener('click',()=>setView('live'));
  function title() {return currentInit?.meta?.name || currentInit?.session || 'Встреча';}
  function readKey(){return [session,generation,view,currentReportReview.updated_at,currentReportReview.draft_revision,currentReportReview.state,currentMeetingResult.source_revision,JSON.stringify(currentMeetingResult.report_revision),view==='materials'?materialsRevision:''].join('|');}
  function showNotice(data) {
    const notices=[];
    if(data.kind==='draft')notices.push('Черновик — ещё не итоговый документ. Проверьте текст и выводы перед созданием DOCX.');
    else if(!data.confirmed)notices.push('Сохранённый отчёт. Данные о прохождении контроля отсутствуют; подтверждённым он не помечается.');
    if(data.stale===true)notices.push('После создания отчёта исходные данные или настройки изменились. Здесь показана сохранённая версия; автоматической пересборки нет.');
    else if(data.stale===null)notices.push('Актуальность относительно исходных данных не подтверждена.');
    if(data.kind==='final'&&!data.docx_url)notices.push('Файл DOCX не найден; сохранённый текст отчёта доступен ниже.');
    meetingLabel(el('meetingReadNotice'),'{messages}',()=>({messages:notices.map(value=>meetingUi(value)).join(' ')}));
    el('meetingReadNotice').className=notices.length?'reading-warning':'';
  }
  function showReport(data) {
    const top=zone.scrollTop;
    currentMeetingResult={...currentMeetingResult,...data};
    loadedKey=readKey();
    meetingLabel(el('meetingReadKicker'),data.kind==='draft'?'ЧЕРНОВИК':'СОХРАНЁННЫЙ ОТЧЁТ');
    el('meetingReadTitle').textContent=title();
    el('meetingReadBody').innerHTML=data.html;
    el('meetingReportToc').replaceChildren();
    for(const heading of data.headings.filter(item=>item.level===2)){
      const link=document.createElement('a');link.href='#'+heading.id;link.textContent=heading.text;
      link.onclick=event=>{event.preventDefault();el(heading.id)?.scrollIntoView({block:'start'});};el('meetingReportToc').append(link);
    }
    const download=el('meetingDownload');download.hidden=!data.docx_url || data.kind!=='final';
    if(!download.hidden){download.href=data.docx_url;download.download=data.docx_name;}
    el('meetingReadReview').hidden=data.kind!=='draft';
    el('meetingReadReview').classList.toggle('primary',data.kind==='draft');
    showNotice(data);updateReportButton();renderWorkflowNext();reconcile();
    document.dispatchEvent(new CustomEvent('blatero:report-view',{detail:{session,kind:data.kind}}));
    zone.scrollTop=top;
  }
  function showMaterials(){
    meetingLabel(el('meetingReadKicker'),'МАТЕРИАЛЫ');el('meetingReadTitle').textContent=title();
    meetingLabel(el('meetingReadNotice'),'Материалы этой встречи. Исходные файлы и настройки обработки не меняются при просмотре.');
    const memory=memoryState?.entries || currentInit?.memory?.entries || [];
    el('meetingReadBody').innerHTML='<h2>'+meetingText('Досье')+'</h2>'+(currentInit?.dossier?mdLite(currentInit.dossier):meetingText('Досье пока не подготовлено.'))+'<h2>'+meetingText('Контекст проекта')+'</h2>'+(currentInit?.workspace_context?mdLite(currentInit.workspace_context):meetingText('Рабочая папка и контекст не указаны.'))+'<h2>'+meetingText('Память проекта')+'</h2>'+memory.map(item=>'<p>'+esc(item.text||'')+'</p>').join('');
    if(!memory.length)el('meetingReadBody').insertAdjacentHTML('beforeend','<p>'+meetingText('Сохранённых записей памяти пока нет.')+'</p>');
    const actions=document.createElement('div');actions.className='meeting-read-actions';
    for(const [label,id] of [['Открыть память проекта','memoryBtn'],['Повестка и сценарий','agendaBtn'],['Добавить материалы','liveMaterialsOpen']]){
      const target=el(id);if(!target)continue;
      const button=document.createElement('button');button.type='button';meetingLabel(button,label);button.onclick=()=>target.click();actions.append(button);
    }
    el('meetingReadBody').prepend(actions);
  }
  async function loadReading(force=false) {
    const key=readKey();if(!force&&key===loadedKey)return;
    controller?.abort();const own=++requestVersion;controller=new AbortController();loadedKey=key;
    const ownSession=session,ownGeneration=generation,ownView=view;
    if(renderedSession!==session||renderedView!==view){el('meetingReadBody').replaceChildren();el('meetingReportToc').replaceChildren();}
    el('meetingDownload').hidden=true;el('meetingReadReview').hidden=true;el('meetingReadRetry').hidden=true;
    meetingLabel(el('meetingReadNotice'),'');el('meetingReadNotice').className='';meetingLabel(el('meetingReadStatus'),'Загружаю сохранённые данные…');panel.setAttribute('aria-busy','true');
    try {
      if(view==='materials'){showMaterials();renderedSession=session;renderedView=view;return;}
      const response=await fetch('/api/sessions/'+encodeURIComponent(session)+(view==='report'?'/report-view':'/transcript'),{signal:controller.signal});
      if(!response.ok){let message='Не удалось загрузить сохранённые данные';try{message=(await response.json()).error||message;}catch{}throw Error(message);}
      const data=view==='report'?await response.json():await response.text();
      if(own!==requestVersion||session!==ownSession||generation!==ownGeneration||view!==ownView)return;
      // Keep existing reading position when only metadata changed in the background.
      renderedSession=session;renderedView=view;
      if(view==='report')showReport(data);
      else {
        meetingLabel(el('meetingReadKicker'),'ПОЛНЫЙ ТРАНСКРИПТ');el('meetingReadTitle').textContent=title();
        el('meetingReadBody').innerHTML=mdLite(data);
        meetingLabel(el('meetingReadNotice'),'Все сохранённые сегменты встречи. Для исправления текста или говорящих откройте «Ещё → Аудио и говорящие».');
      }
    } catch(error) {
      if(error.name==='AbortError'||own!==requestVersion)return;
      meetingLabel(el('meetingReadStatus'),error.message);el('meetingReadRetry').hidden=false;
    } finally {
      if(own===requestVersion){panel.setAttribute('aria-busy','false');if(el('meetingReadRetry').hidden)meetingLabel(el('meetingReadStatus'),'');}
    }
  }
  function reconcile(){
    if(!currentInit)return;
    const nextSession=currentInit.current_dir,nextGeneration=currentInit.session_generation;
    const changed=session!==nextSession||generation!==nextGeneration;
    const nextPhase=meetingStage();
    if(changed){controller?.abort();requestVersion++;session=nextSession;generation=nextGeneration;loadedKey='';manual=nextPhase!=='recording'&&cachedViews.has(session);view=nextPhase==='recording'?'live':cachedViews.get(session)||defaultView(nextPhase);zone.scrollTop=0;}
    else if(nextPhase!==phase){
      if(nextPhase==='recording'){view='live';manual=false;}
      else if(!manual){view=defaultView(nextPhase);}
    }
    phase=nextPhase;
    if(view==='report'&&!currentMeetingResult.has_final&&!currentMeetingResult.has_draft)view=defaultView(phase);
    if(view==='transcript'&&!currentHasTranscript)view=defaultView(phase);
    syncReadingFont();
    const post=postStage(phase),reading=['report','transcript','materials'].includes(view);
    document.body.dataset.meetingStage=phase;document.body.dataset.meetingView=view;
    document.body.classList.toggle('meeting-post',post);
    document.body.classList.toggle('meeting-reading',reading);
    const hasHints=['answers','questions','tags','flags'].some(id=>el(id).textContent.trim());
    panel.hidden=!reading;overview.hidden=view!=='overview'&&!(post&&view==='live'&&!hasHints);
    document.body.classList.remove('empty-state');
    if(!post&&!reading)syncEmptyLayout();
    for(const button of nav.querySelectorAll('[data-meeting-view]')){
      const selected=button.dataset.meetingView===view || (view==='overview'&&button.dataset.meetingView==='live');
      if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
      button.disabled=(button.dataset.meetingView==='report'&&!currentMeetingResult.has_final&&!currentMeetingResult.has_draft)||(button.dataset.meetingView==='transcript'&&!currentHasTranscript);
    }
    meetingLabel(nav.querySelector('[data-meeting-view=live]'),post?'Разбор':phase==='recording'?'Подсказки':'Подготовка');
    if(post&&!recLive){
      meetingLabel(el('rectext'),'Запись сохранена · исходные аудиофайлы доступны в результатах');
      setIconAction(el('recbtn'),'record','продолжить запись','Продолжить эту встречу новым аудиосегментом');
    }
    if(reading)loadReading();
    else if(controller){controller.abort();requestVersion++;controller=null;loadedKey='';}
    document.dispatchEvent(new CustomEvent('blatero:meeting-view',{detail:{session,view,phase}}));
  }
  const priorHandle=handle;
  handle=function(message){
    priorHandle(message);
    if(['init','memory','workspace'].includes(message.type)){
      const next=JSON.stringify([currentInit?.dossier,currentInit?.workspace_context,memoryState?.entries]);
      if(next!==materialsSignature){materialsSignature=next;materialsRevision++;}
    }
    if(message.type==='report_review'){
      currentMeetingResult.has_draft=!!message.draft_exists;
      if(message.state==='finalized')currentMeetingResult.has_final=true;
      loadedKey='';
    }
    if(message.type==='hints'&&recLive){view='live';}
    reconcile();
  };
  reconcile();
})();
