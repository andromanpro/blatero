'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const strings = {
    now:['Записать сейчас','Record now'], context:['Контекст записи','Recording context'],
    title:['Подключить контекст к записи','Connect recording context'], close:['Закрыть','Close'],
    meeting:['Подготовленная встреча','Prepared meeting'], none:['Выбрать позже','Choose later'],
    name:['Тема разговора','Conversation topic'], project:['Проект','Project'], task:['Задача','Task'],
    folder:['Рабочая папка','Workspace folder'], apply:['Подключить материалы','Connect materials'],
    recognize:['Определить по разговору','Identify from conversation'],
    pending:['Собираю контекст… Запись продолжается.','Collecting context… Recording continues.'],
    success:['Контекст подключён. Следующие подсказки учитывают материалы.','Context connected. The next hints use these materials.'],
    quick:['Новый разговор. Папку и задачу можно выбрать во время записи.','New conversation. Choose a folder and task during recording.'],
    automatic:['Тема и задача появятся по содержанию разговора. Контекст можно выбрать вручную.','The topic and task will be identified from the conversation. You can also choose context manually.'],
    source:['Использовать материалы подготовленной встречи','Use materials from a prepared meeting'],
    ai:['Для определения темы используется выбранный ИИ. По разговору создаётся входящая задача или подключается существующая.','Topic identification uses the selected AI. It creates an inbox task from the conversation or links an existing task.'],
    on:['Фоновый помощник работает','Background helper is running'],
    off:['Автоматическая запись выключена','Automatic recording is off'],
    waiting:['Для запуска сохраните выбранные приложения и разрешение автоматической записи.','Save the selected apps and automatic recording permission to start.'],
    unavailable:['Автозапуск по звонку доступен в Windows.','Call-triggered recording is available on Windows.'],
    starting:['Фоновый помощник запускается. Обновите настройки через несколько секунд.','The background helper is starting. Refresh settings in a few seconds.'],
    changed:['Выбрана другая встреча. Откройте контекст заново.','The meeting changed. Open context again.']
  };
  const t = key => strings[key][document.documentElement.lang === 'en' ? 1 : 0];
  const dialog = document.createElement('dialog');
  dialog.id = 'captureContextDialog';
  dialog.setAttribute('aria-labelledby','captureContextTitle');
  dialog.innerHTML = `<form id="captureContextForm">
    <div class="capture-heading"><h2 id="captureContextTitle" data-capture-label="title"></h2><button type="button" id="captureClose" data-capture-label="close"></button></div>
    <label><span data-capture-label="meeting"></span><select id="captureMeeting"></select></label>
    <label><span data-capture-label="name"></span><input id="captureName" maxlength="200"></label>
    <label><span data-capture-label="project"></span><select id="captureProject"></select></label>
    <label><span data-capture-label="task"></span><select id="captureTask"></select></label>
    <label><span data-capture-label="folder"></span><input id="captureFolder" maxlength="1000" autocomplete="off"></label>
    <p class="settings-help" data-capture-label="ai"></p><p id="captureNotice" role="status"></p>
    <div class="capture-actions"><button id="captureRecognize" type="button" data-capture-label="recognize"></button><button id="captureApply" class="primary" type="submit" data-capture-label="apply"></button></div>
  </form>`;
  document.body.append(dialog);
  let catalog = null, scope = null, busy = false, noticeKey = '', watchState = null;
  const sameScope = () => scope && scope.session === currentInit?.current_dir && scope.generation === currentInit?.session_generation && scope.server_epoch === currentInit?.server_epoch;
  function notice(text,key='') { noticeKey=key; $('captureNotice').textContent=text; }
  function translate() {
    $('recordNow').textContent=t('now'); $('captureContextButton').textContent=t('context');
    dialog.querySelectorAll('[data-capture-label]').forEach(el=>{el.textContent=t(el.dataset.captureLabel);});
    for(const id of ['captureMeeting','captureProject','captureTask']) if($(id).options[0])$(id).options[0].textContent=t('none');
    if(noticeKey)notice(t(noticeKey),noticeKey);
    showWatch();
  }
  function showWatch() {
    if(!watchState)return;
    const {config:c,call_watch:w={}}=watchState;
    $('callWatchStatus').textContent=w.error || t(!w.supported?'unavailable':
      !(c.call_auto_telemost || c.call_auto_talk)?'off':!c.call_auto_record_acknowledged?'waiting':w.running?'on':'starting');
  }
  function fillTasks(selected='') {
    const project=$('captureProject').value;
    $('captureTask').replaceChildren(new Option(t('none'),''));
    for(const task of catalog.tasks.filter(task=>task.project_id===project || (!project && !task.project_id)))
      $('captureTask').add(new Option(task.title,task.id));
    $('captureTask').value=selected;
  }
  function render(init) {
    watchState=init; showWatch();
    $('recordNow').hidden=!!init.rec_running;
    if(dialog.open && (scope.session!==init.current_dir || scope.generation!==init.session_generation || scope.server_epoch!==init.server_epoch)){dialog.close();busy=false;}
    $('captureContextButton').hidden=!init.rec_running && !init.capture_context?.origin && !init.capture_context?.automatic;
  }
  $('recordNow').onclick=()=>{
    openStartOverlay('встреча');
    speechStartRequest={...speechStartRequest,unplanned:true,request_id:crypto.randomUUID().replaceAll('-','')};
    pendingStartMode='встреча';updateStartConfirmState();
    $('startMeetingSummary').textContent=t('quick');
    $('startTitle').textContent=t('now');
  };
  $('captureContextButton').onclick=async()=>{
    scope={session:currentInit.current_dir,generation:currentInit.session_generation,server_epoch:currentInit.server_epoch};
    try {
      const response=await fetch('/api/capture/options');
      if(!response.ok)throw new Error(await response.text());
      catalog=await response.json();
      if(!sameScope())throw new Error(t('changed'));
      $('captureMeeting').replaceChildren(new Option(t('none'),''));
      for(const item of catalog.sessions.filter(item=>item.dir!==scope.session))$('captureMeeting').add(new Option(item.label,item.dir));
      $('captureProject').replaceChildren(new Option(t('none'),''));
      for(const project of catalog.projects)$('captureProject').add(new Option(project.name,project.id));
      const meta=currentInit.meta;
      $('captureProject').value=meta.project_id || '';
      $('captureName').value=meta.name || '';
      $('captureFolder').value=meta.workspace_path || '';
      fillTasks(currentInit.capture_context?.task_ids?.[0] || '');
      busy=false;$('captureApply').disabled=$('captureRecognize').disabled=false;
      notice(currentInit.capture_context?.error || t('automatic'),currentInit.capture_context?.error?'':'automatic');
      dialog.showModal();
    }catch(error){$('status').textContent=error.message;}
  };
  $('captureProject').onchange=()=>{
    fillTasks();
    $('captureFolder').value=catalog.projects.find(p=>p.id===$('captureProject').value)?.workspace || '';
  };
  $('captureMeeting').onchange=()=>{
    const meta=catalog.sessions.find(item=>item.dir===$('captureMeeting').value)?.meta;
    if(!meta)return;
    $('captureName').value=meta.name || '';
    $('captureProject').value=meta.project_id || '';
    $('captureFolder').value=meta.workspace_path || '';
    fillTasks(meta.task_ids?.[0] || '');
  };
  function submit(recognize=false) {
    if(busy || !sameScope())return;
    const body=recognize?{recognize:true}:{name:$('captureName').value.trim(),
      project_id:$('captureProject').value || null,task_id:$('captureTask').value || null,
      task_ids:[],workspace_path:$('captureFolder').value.trim(),source_session:$('captureMeeting').value || null};
    if(!send({type:'capture_context',...body,...scope}))return;
    busy=true;$('captureApply').disabled=$('captureRecognize').disabled=true;
    notice(t('pending'),'pending');
  }
  $('captureContextForm').onsubmit=event=>{event.preventDefault();submit();};
  $('captureRecognize').onclick=()=>submit(true);
  $('captureClose').onclick=()=>dialog.close();
  window.addEventListener('blatero:brand-message',event=>{
    const m=event.detail;
    if(m.type==='init')render(m);
    if(m.type==='capture_context_result' && !m.ok && m.session===currentInit?.current_dir && currentInit.capture_context)currentInit.capture_context.error=m.message;
    if(m.type==='call_watch_status' && watchState){watchState={...watchState,call_watch:m};showWatch();}
    if(m.type==='capture_context_result' && m.session===scope?.session){
      busy=false;$('captureApply').disabled=$('captureRecognize').disabled=false;
      notice(m.ok?(m.warnings?.join('\n') || t('success')):m.message,m.ok && !m.warnings?.length?'success':'');
    }
    if(m.type==='status' && busy && m.text){busy=false;$('captureApply').disabled=$('captureRecognize').disabled=false;notice(m.text);}
  });
  document.addEventListener('blatero:language',translate);
  translate();if(typeof currentInit!=='undefined' && currentInit)render(currentInit);
})();
