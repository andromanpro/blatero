/* Local, server-owned video. Opening the dialog never starts capture. */
(() => {
  const $ = id => document.getElementById(id);
  const phrases = {
    title:["Видеозапись","Video recording"], video:["Видео","Video"], close:["Закрыть","Close"],
    chooseMode:["Способ записи","Recording mode"], audioOnly:["Только аудио","Audio only"],
    withScreen:["Аудио и видео экрана","Audio and screen video"], withWindow:["Аудио и видео окна","Audio and window video"],
    continueStart:["Далее: начать запись","Next: start recording"],
    video_previous_still_finishing:["Предыдущее видео ещё сохраняется. Подождите и повторите предпросмотр.","The previous video is still finishing. Wait, then try preview again."],
    restartRequired:["Для общего запуска обновите сервер и страницу.","Restart the updated server and reload this page to start both."],
    video_failed_audio_continues:["Видео не запущено. Аудио продолжает записываться. Откройте панель видео и проверьте источник.","Video did not start. Audio recording continues. Open the video panel and check the source."],
    audio_failed_video_stopped:["Запись аудио не запустилась. Видео остановлено. Проверьте устройства.","Audio recording did not start. Video has been stopped. Check your devices."],
    together:["Аудио и видео запускаются после подтверждения. Кнопка «Стоп» сохранит оба. Файлы звука и видео остаются отдельными.","Audio and video start after confirmation. Stop saves both. Audio and video files stay separate."],
    videoFiles:["видео и предпросмотры","video and previews"],videoDays:["видео, дней","video, days"],
    kind:["Источник","Source"], window:["Окно","Window"], monitor:["Экран","Display"],
    pick:["Выберите источник","Choose a source"], refresh:["Обновить список","Refresh sources"],
    preview:["Предпросмотр","Preview"], start:["Начать видеозапись","Start video recording"],
    stop:["Остановить видео","Stop video"], cancel:["Отменить выбор","Cancel selection"],
    scope:["Окно может быть неактивным и перекрытым, но не свёрнутым.","The window may be inactive and covered, but not minimized."],
    local:["Локальный MKV, до 1920 × 1080. Звук встречи сохраняется отдельно в WAV. Видео не отправляется в ИИ.","Local MKV, up to 1920 × 1080. Meeting audio is saved separately as WAV. Video is not sent to AI."],
    still:["Видеозапись продолжается после закрытия этой панели.","Video recording continues after you close this panel."],
    history:["Видео встречи","Meeting videos"], empty:["Видеозаписей пока нет.","No video recordings yet."],
    download:["Скачать MKV","Download MKV"], partial:["Скачать сохранённую часть","Download preserved part"],
    preparing:["Готовлю предпросмотр…","Preparing preview…"], ready:["Проверьте выбранный источник и нажмите «Начать видеозапись».","Check the selected source, then choose Start video recording."],
    starting:["Включаю видеозапись…","Starting video recording…"], recording:["Идёт видеозапись","Video recording"],
    stopping:["Сохраняю и проверяю видео…","Saving and checking video…"], completed:["Видео сохранено","Video saved"],
    cancelled:["Выбор отменён","Selection cancelled"], interrupted:["Запись прервана; сохранённая часть оставлена","Recording interrupted; captured part retained"],
    failed:["Ошибка видео. Запись звука не остановлена.","Video error. Audio recording has not been stopped."],
    missing:["Компонент видео не установлен. Инструкция: Помощь → Видеозапись.","Video component is not installed. See Help → Video recording."],
    video_component_missing:["Компонент видео не установлен: установите requirements-video.txt в окружение Blatero.","Video component missing: install requirements-video.txt in the Blatero environment."],
    video_window_unavailable:["Окно закрыто, свёрнуто или недоступно для захвата. Выберите его заново.","Window closed, minimized or unavailable for capture. Select it again."],
    video_source_changed:["Источник изменился. Выберите окно или экран заново.","Source changed. Select the window or display again."],
    video_source_closed:["Выбранное окно закрыто. Другой источник не включался.","Selected window closed. No other source was captured."],
    video_disk_low:["Недостаточно места. Сохранённая часть видео оставлена.","Low disk space. Captured video part retained."],
    video_capture_failed:["Windows не разрешила захват источника или кодирование. Выберите другой источник; рабочий стол автоматически не включается.","Windows could not capture or encode this source. Select another; desktop capture is never enabled automatically."],
    video_worker_timeout:["Видеопроцесс не ответил и остановлен. Сохранённая часть оставлена; аудио не остановлено.","Video worker stopped responding and was stopped. Captured part retained; audio was not stopped."],
    video_preview_expired:["Предпросмотр истёк. Выберите источник заново.","Preview expired. Select the source again."],
    generic:["Не удалось выполнить действие. Обновите состояние; повтор не запускается автоматически.","Action failed. Refresh the status; no automatic retry is made."],
    changed:["Встреча изменилась. Откройте видео заново.","Meeting changed. Reopen video controls."],
    alt:["Предпросмотр выбранного источника","Selected capture source preview"],
    fps:["Частота кадров","Frame rate"], busy:["Сначала остановите текущую видеозапись или отмените предпросмотр.","Stop the current recording or cancel its preview first."],
  };
  const en = () => window.BlateroI18n?.language === "en" || window.BlateroI18n?.getLanguage?.() === "en";
  const t = key => phrases[key]?.[en()?1:0] || phrases.generic[en()?1:0];
  const dialog = document.createElement("dialog");
  dialog.id = "videoCaptureDialog"; dialog.className = "video-capture-dialog";
  dialog.setAttribute("aria-labelledby","videoCaptureTitle");
  dialog.innerHTML = `<header><h2 id="videoCaptureTitle" data-video-text="title"></h2><button type="button" id="videoClose" data-video-text="close"></button></header>
    <p data-video-text="scope"></p><p class="video-note" data-video-text="local"></p>
    <div class="video-source-controls"><label><span data-video-text="kind"></span><select id="videoKind"><option value="window" data-video-text="window"></option><option value="monitor" data-video-text="monitor"></option></select></label>
    <label><span data-video-text="pick"></span><select id="videoSource"></select></label>
    <label><span data-video-text="fps"></span><select id="videoFps"><option value="15">15 FPS</option><option value="30">30 FPS</option></select></label></div>
    <div class="video-actions"><button type="button" id="videoRefresh" data-video-text="refresh"></button><button type="button" id="videoPrepare" data-video-text="preview"></button></div>
    <p id="videoSourceName" class="video-note"></p><img id="videoPreview" hidden><p id="videoState" role="status" aria-live="polite"></p><p id="videoElapsed" role="timer" aria-live="off" hidden></p>
    <div class="video-actions"><button type="button" id="videoStart" class="primary" data-video-text="start" hidden></button><button type="button" id="videoStop" data-video-text="stop" hidden></button><button type="button" id="videoCancel" data-video-text="cancel" hidden></button></div>
    <p id="videoContinues" class="video-note" data-video-text="still" hidden></p>
    <section><h3 data-video-text="history"></h3><div id="videoHistory"></div></section>`;
  document.body.append(dialog);
  const recordActions=$("videoStart").parentElement;recordActions.classList.add("video-record-actions");
  const body=document.createElement("div");body.className="video-capture-body";
  for(const child of [...dialog.childNodes])if(child!==dialog.querySelector("header") && child!==recordActions)body.append(child);
  dialog.append(body,recordActions);
  const open = document.createElement("button"); open.type="button"; open.id="videoCaptureOpen";
  $("liveMaterialCapture")?.after(open);
  const menu=document.createElement("div");menu.id="recordingModeMenu";menu.className="recording-mode-menu";
  menu.setAttribute("popover","auto");menu.setAttribute("role","menu");
  menu.innerHTML='<button type="button" role="menuitem" data-record-mode="audio" data-video-text="audioOnly"></button><button type="button" role="menuitem" data-record-mode="monitor" data-video-text="withScreen"></button><button type="button" role="menuitem" data-record-mode="window" data-video-text="withWindow"></button>';
  document.body.append(menu);
  const groupNote=document.createElement("p");groupNote.className="video-note";groupNote.dataset.videoText="together";groupNote.hidden=true;body.prepend(groupNote);
  const startSummary=document.createElement("p");startSummary.id="recordingVideoSummary";startSummary.className="video-note";$("startMeetingSummary").after(startSummary);
  const groupWarning=document.createElement('p');groupWarning.className='recording-video-warning';groupWarning.hidden=true;groupWarning.setAttribute('role','alert');document.querySelector('.header-context').append(groupWarning);
  const quick = document.createElement("button"); quick.type="button"; quick.id="videoQuickStop"; quick.hidden=true;
  $("recbtn")?.after(quick);
  const materialVideos=document.createElement("section");materialVideos.className="video-material-links";
  const materialHeading=document.createElement("h3"), materialList=document.createElement("div");materialVideos.append(materialHeading,materialList);
  materialVideos.hidden=true;$("liveMaterialDrop")?.after(materialVideos);
  let scope=null, sources=[], items=[], current=null, pending=false, previewLoaded=false, lastPhase="", notice="";
  let pollBusy=false, openEpoch=0, cancelOnReady=false, inFlightAction="";
  let meetingIntent=false, handoff=false, pendingMeetingRun=null;
  const currentScope=()=>typeof currentInit!=="undefined" && currentInit && ({session:currentInit.current_dir,generation:currentInit.session_generation});
  const same=(a,b)=>a && b && a.session===b.session && a.generation===b.generation;
  const active=item=>["starting","preview","recording","stopping"].includes(item?.phase);
  const seconds=item=>Math.max(0,Math.floor(item?.seconds || 0));
  const clock=item=>`${Math.floor(seconds(item)/60)}:${String(seconds(item)%60).padStart(2,"0")}`;
  function translated() {
    document.querySelectorAll("[data-video-text]").forEach(node=>node.textContent=t(node.dataset.videoText));
    open.textContent="▣ "+t("video");$("videoPreview").alt=t("alt");
    menu.setAttribute('aria-label',t('chooseMode'));drawStartSummary();drawGroupWarning();
    renderSources();render();
  }
  function requireScope() {
    if(!same(scope,currentScope()))throw new Error("changed");
    return {...scope};
  }
  async function api(path,body) {
    const expected=requireScope();
    const response=await fetch("/api/video/"+path+(body?"":"?"+new URLSearchParams(expected)),body?
      {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...body,...expected})}:{});
    if(!response.ok)throw new Error(await response.text());
    const value=await response.json();
    if(!same(expected,currentScope()) || !same(expected,scope))throw new Error("changed");
    return value;
  }
  const fileUrl=(item,name)=>`/api/video/file/${encodeURIComponent(item.id)}/${name}?${new URLSearchParams(scope)}`;
  function renderSources() {
    const select=$("videoSource"), previous=select.value;
    select.replaceChildren(new Option(t("pick"),""));
    sources.forEach((source,index)=>{if(source.kind===$("videoKind").value)select.add(new Option(source.label,String(index)));});
    if([...select.options].some(option=>option.value===previous))select.value=previous;
  }
  function stateKey(item) {return ({starting:"preparing",preview:"ready",recording:"recording",stopping:"stopping",completed:"completed",cancelled:"cancelled",failed:"failed",interrupted:"interrupted"})[item?.phase] || "empty";}
  function renderHistory(target,short=false) {
    const rows=items.filter(item=>item.file && !active(item));
    const signature=JSON.stringify([en(),scope,short?rows.slice(0,3):rows]);
    if(target.dataset.videoSignature===signature)return;
    target.dataset.videoSignature=signature;target.replaceChildren();
    if(!rows.length){target.textContent=t("empty");return;}
    for(const item of (short?rows.slice(0,3):rows)) {
      const row=document.createElement("article");row.className="video-history-item";
      const name=document.createElement("strong");name.textContent=item.source?.label || t("video");
      const info=document.createElement("p");info.textContent=`${t(stateKey(item))} · ${clock(item)} · ${item.width || "?"} × ${item.height || "?"}`;
      const link=document.createElement("a");link.href=fileUrl(item,item.file);link.textContent=t(item.phase==="completed"?"download":"partial");
      row.append(name,info,link);target.append(row);
    }
  }
  function render() {
    const live=active(current), recording=["recording","stopping"].includes(current?.phase);
    for(const id of ["videoKind","videoSource","videoFps","videoRefresh"])$(id).disabled=!!live || pending;
    $("videoPrepare").disabled=!!live || pending || $("videoSource").value==="";
    $("videoStart").hidden=current?.phase!=="preview";$("videoStart").disabled=pending || !previewLoaded;
    $("videoStart").textContent=t(meetingIntent?'continueStart':'start');
    groupNote.hidden=!meetingIntent;
    $("videoCancel").hidden=!live || recording;$("videoCancel").disabled=pending;
    $("videoStop").hidden=!recording;$("videoStop").disabled=pending || current?.phase==="stopping";
    $("videoContinues").hidden=!recording;
    const phase=t(stateKey(current));
    const error=current?.error?(phrases[current.error]?t(current.error):t("failed")):"";
    const message=notice?t(notice):`${phase}${error?" — "+error:""}`;
    if($("videoState").textContent!==message)$("videoState").textContent=message;
    $("videoElapsed").hidden=!recording;$("videoElapsed").textContent=clock(current);
    $("videoSourceName").textContent=live?(current?.source?.label || ""):($("videoSource").value!==""?sources[Number($("videoSource").value)]?.label || "":"");
    $("videoState").classList.toggle("video-working",pending || ["starting","stopping"].includes(current?.phase));
    quick.hidden=!recording;quick.textContent="■ "+t("video")+" · "+clock(current);quick.title=t("stop");quick.setAttribute("aria-label",t("stop"));
    quick.disabled=pending || current?.phase==="stopping";
    renderHistory($("videoHistory"));
    materialVideos.hidden=!items.some(item=>item.file && !active(item));
    if(!materialVideos.hidden){materialHeading.textContent=t("history");renderHistory(materialList,true);}
  }
  async function poll() {
    if(pollBusy || !scope || !same(scope,currentScope()))return;
    pollBusy=true;
    try {
      const result=await api("status");items=result.items;
      current=items.find(item=>item.id===current?.id) || items.find(active) || items[0] || null;
      if(current?.phase==="preview" && $("videoPreview").dataset.run!==current.id) {
        previewLoaded=false;$("videoPreview").dataset.run=current.id;
        $("videoPreview").onload=()=>{previewLoaded=true;render();};
        $("videoPreview").onerror=()=>{previewLoaded=false;notice="generic";render();};
        $("videoPreview").src=fileUrl(current,"preview.png");$("videoPreview").hidden=false;
      }
      if(lastPhase!==(current?.phase || "")){notice="";lastPhase=current?.phase || "";}
      render();
    } catch(error){notice=phrases[error.message]?error.message:"generic";render();}
    finally{pollBusy=false;}
  }
  async function show(options={}) {
    if(!currentScope())return;
    meetingIntent=options.meeting===true;groupNote.hidden=!meetingIntent;
    if(options.kind)$("videoKind").value=options.kind;
    const epoch=++openEpoch;
    cancelOnReady=false;
    if(!same(scope,currentScope())){scope=currentScope();items=[];current=null;previewLoaded=false;lastPhase="";notice="";$("videoPreview").hidden=true;delete $("videoPreview").dataset.run;}
    if(!dialog.open)dialog.showModal();
    pending=true;render();
    try {
      const result=await api("sources");if(epoch!==openEpoch)return;
      sources=result.sources;renderSources();if(!active(current))$("videoSource").value="";
      await poll();
      notice=result.available?"":"video_component_missing";
    }catch(error){notice=phrases[error.message]?error.message:"generic";}
    finally{if(epoch===openEpoch){pending=false;render();if(cancelOnReady){cancelOnReady=false;if(["starting","preview"].includes(current?.phase))act("cancel");}}}
  }
  async function act(action) {
    if(pending)return;
    pending=true;inFlightAction=action;notice="";render();
    try {
      if(action==="prepare") {
        const source=sources[Number($("videoSource").value)];
        if(!source || $("videoSource").value==="")throw new Error("generic");
        const id=crypto.randomUUID().replaceAll("-","");
        current=await api("action",{action,id,source,fps:Number($("videoFps").value)});
        previewLoaded=false;$("videoPreview").hidden=true;delete $("videoPreview").dataset.run;
      } else if(current) {
        if(action==="start")notice="starting";
        await api("action",{action,id:current.id});
      }
      await poll();
    }catch(error){notice=phrases[error.message]?error.message:"generic";}
    finally{pending=false;inFlightAction="";render();if(cancelOnReady){cancelOnReady=false;if(["starting","preview"].includes(current?.phase))act("cancel");}}
  }
  function drawStartSummary(){startSummary.textContent=pendingMeetingRun?`${t(pendingMeetingRun.kind==='monitor'?'withScreen':'withWindow')} · ${pendingMeetingRun.label}`:t('audioOnly');}
  function drawGroupWarning(){const code=currentInit?.recording_video_error;groupWarning.hidden=!code;groupWarning.textContent=code?t(code):'';}
  function cancelPending(){
    const previous=pendingMeetingRun;pendingMeetingRun=null;drawStartSummary();
    if(previous && same(previous,currentScope()) && current?.id===previous.video_run && ['starting','preview'].includes(current.phase))act('cancel');
  }
  window.BlateroRecording={
    audioState(live){drawGroupWarning();if(live){$('recbtn').removeAttribute('aria-haspopup');$('recbtn').removeAttribute('aria-expanded');menu.hidePopover();}},
    choose(){
      menu.querySelectorAll('[data-record-mode]').forEach(button=>{
        button.disabled=button.dataset.recordMode!=='audio' && !currentInit?.recording_modes?.combined_video;
        button.title=button.disabled?t('restartRequired'):'';
      });
      const rect=$('recbtn').getBoundingClientRect();
      menu.style.left='8px';menu.style.top='8px';menu.showPopover();
      const size=menu.getBoundingClientRect();
      menu.style.left=Math.max(8,Math.min(rect.left,innerWidth-size.width-8))+'px';menu.style.top=Math.max(8,Math.min(rect.bottom+6,innerHeight-size.height-8))+'px';
      $('recbtn').setAttribute('aria-haspopup','menu');$('recbtn').setAttribute('aria-expanded','true');
      menu.querySelector('button').focus();
    },
    onStartOverlay(value){if(!value)cancelPending();else pendingMeetingRun=value;drawStartSummary();},
    cancelPending,
    submitted(){pendingMeetingRun=null;drawStartSummary();},
    startPayload(){
      if(!pendingMeetingRun)return {};
      if(!same(pendingMeetingRun,currentScope()))throw new Error(t('changed'));
      if(!currentInit?.recording_modes?.combined_video)throw new Error(t('restartRequired'));
      if(current?.id!==pendingMeetingRun.video_run || current?.phase!=='preview')throw new Error(t('video_preview_expired'));
      return {video_run:pendingMeetingRun.video_run,session:pendingMeetingRun.session,generation:pendingMeetingRun.generation};
    }
  };
  menu.addEventListener('toggle',event=>{$('recbtn').setAttribute('aria-expanded',String(event.newState==='open'));});
  menu.querySelectorAll('button').forEach(button=>button.onclick=()=>{
    menu.hidePopover();cancelPending();
    if(button.dataset.recordMode==='audio')openStartOverlay();
    else show({meeting:true,kind:button.dataset.recordMode});
  });
  menu.addEventListener('keydown',event=>{
    const buttons=[...menu.querySelectorAll('button')],index=buttons.indexOf(document.activeElement);
    const next=event.key==='Home'?0:event.key==='End'?2:event.key==='ArrowDown'?(index+1)%3:event.key==='ArrowUp'?(index+2)%3:null;
    if(next!==null){event.preventDefault();buttons[next].focus();}
    if(event.key==='Escape'){$('recbtn').focus();}
  });
  open.onclick=()=>show();$("videoClose").onclick=()=>dialog.close();
  dialog.addEventListener("close",()=>{if(handoff){handoff=false;return;}if(inFlightAction==="start")return;if(pending)cancelOnReady=true;else if(["starting","preview"].includes(current?.phase))act("cancel");});
  $("videoRefresh").onclick=()=>show({meeting:meetingIntent});$("videoKind").onchange=()=>{renderSources();render();};
  $("videoSource").onchange=render;
  for(const [id,action] of [["videoPrepare","prepare"],["videoStart","start"],["videoStop","stop"],["videoCancel","cancel"]])$(id).onclick=()=>act(action);
  $("videoStart").onclick=()=>{
    if(!meetingIntent){act('start');return;}
    if(pending || !previewLoaded || current?.phase!=='preview')return;
    pendingMeetingRun={...requireScope(),video_run:current.id,kind:current.source.kind,label:current.source.label};
    handoff=true;dialog.close();openStartOverlay(null,pendingMeetingRun);
  };
  quick.onclick=()=>act("stop");
  document.addEventListener("blatero:language",translated);
  setInterval(()=>{if(currentScope() && !same(scope,currentScope())){scope=currentScope();items=[];current=null;notice="";lastPhase="";previewLoaded=false;$("videoPreview").hidden=true;delete $("videoPreview").dataset.run;}if(!document.hidden)poll();},1000);
  translated();
})();
