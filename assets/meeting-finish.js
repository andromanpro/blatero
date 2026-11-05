'use strict';
// Use durable report job stages, not the generic status line that other jobs clear.
(() => {
  const el=id=>document.getElementById(id);
  const strip=document.createElement('section');strip.id='meetingFinish';strip.hidden=true;
  strip.innerHTML='<div><strong>Запись сохранена</strong><p>Подготовим итог автоматически. Уточнить потребуется только спорные имена и выводы.</p></div><div class="meeting-finish-actions"><button type="button" id="meetingFinishReport" class="primary">Завершить и создать отчёт</button><button type="button" id="meetingFinishSpeakers">Участники и банк голосов</button><details><summary>Дополнительно</summary><button type="button" id="meetingFinishDetails">Подробный разбор фраз и аудио</button><button type="button" id="meetingFinishContinue">Продолжить запись</button></details></div>';
  el('meetingViewTabs').after(strip);
  const progress=document.createElement('section');progress.id='reportProgress';progress.hidden=true;progress.setAttribute('aria-label','Подготовка отчёта');
  progress.innerHTML='<div class="report-orbit" aria-hidden="true"><span></span></div><div class="report-progress-copy"><strong id="reportProgressTitle">Готовим отчёт</strong><p id="reportProgressStage" role="status" aria-live="polite"></p><span id="reportProgressElapsed"></span><p id="reportProgressEstimate"></p><ol><li>Проверка записи и материалов</li><li>Черновик и контроль выводов</li><li>Итоговый документ</li></ol><button type="button" id="reportProgressOpen" hidden>Открыть черновик</button></div>';
  strip.after(progress);
  window.BlateroMeetingI18n?.bindStatic(strip);window.BlateroMeetingI18n?.bindStatic(progress);
  let session='',generation=null,epoch=0,activity=null,optimistic=0,baselineId='',own=false,polling=false,lastFetch=0;
  const stages={starting:'Запускаем подготовку',inspect_inputs:'Проверяем транскрипт и материалы',prepare_draft:'ИИ анализирует встречу и пишет черновик',build_review:'Проверяем выводы и качество данных',validate_draft:'Проверяем сохранённый черновик',finalize_outputs:'Собираем итоговый DOCX',publish_review:'Сохраняем результаты'};
  function draw(){
    if(!activity&&!optimistic)return;
    const waiting=optimistic&&(!activity?.job_id||activity.phase==='idle'||activity.job_id===baselineId),running=!!waiting||activity?.phase==='running';
    const sec=Math.floor(waiting?(Date.now()-optimistic)/1000:(activity?.elapsed_seconds||0));
    progress.dataset.phase=running?'running':activity?.phase||'idle';progress.setAttribute('aria-busy',String(running));
    meetingLabel(el('reportProgressElapsed'),'Прошло {time}',{time:Math.floor(sec/60)+':'+String(sec%60).padStart(2,'0')});
    const unknown=activity?.operation_status?.state==='outcome_unknown';
    meetingLabel(el('reportProgressTitle'),running?'Готовим отчёт':unknown?'Результат запроса неизвестен':activity?.phase==='failed'?'Не удалось подготовить отчёт':activity?.phase==='interrupted'?'Подготовка прервана':'Этап завершён');
    meetingLabel(el('reportProgressStage'),waiting?'Запрос отправлен. Ожидаем начало обработки…':stages[activity?.stage]||'Проверяем состояние задачи');
    meetingLabel(el('reportProgressEstimate'),'{messages}',()=>{
      if(!running)return {messages:''};
      if(activity?.operation==='finalize')return {messages:meetingUi('Локальная сборка без нового обращения к ИИ. Точное время заранее неизвестно.')};
      return {messages:meetingUi('Ориентир для черновика — 1–3 минуты, не гарантия. Модель не сообщает процент готовности.')+(sec>180?meetingUi(' Запрос выполняется дольше ориентира.'):'')};
    });
    const review=currentReportReview?.state;
    el('reportProgressOpen').hidden=running||!['ready','needs_review','finalized'].includes(review);
    meetingLabel(el('reportProgressOpen'),review==='finalized'?'Открыть отчёт':'Проверить готовый черновик');
    if(!running&&activity?.phase==='completed')meetingLabel(el('reportProgressStage'),review==='finalized'?'Отчёт сохранён. Можно проверить и сохранить договорённости.':currentReportReview.draft_exists?'Черновик сохранён. Проверьте только отмеченные сомнения перед DOCX.':'Проверка завершена. Для продолжения откройте замечания к данным встречи.');
    if(!running&&['failed','interrupted'].includes(activity?.phase))meetingLabel(el('reportProgressStage'),unknown?'Откройте восстановление в настройках и проверьте сохранённый результат перед повтором. Запрос мог завершиться у провайдера; повтор может потребовать оплаты.':'Исходные записи сохранены. Откройте восстановление в настройках перед повтором.');
    for(const id of ['meetingFinishReport','report','savedReviewReport'])el(id).disabled=running;
    progress.querySelectorAll('li').forEach((node,i)=>node.classList.toggle('current',i===(activity?.operation==='finalize'?2:activity?.stage==='inspect_inputs'?0:1)));
  }
  async function check(force=false){
    if(!session||polling||!force&&Date.now()-lastFetch<1700)return;
    polling=true;lastFetch=Date.now();const owner=epoch,which=session;
    try{
      const response=await fetch('/api/sessions/'+encodeURIComponent(session)+'/report-activity',{cache:'no-store'});
      if(!response.ok)throw Error('Нет связи с сервером');const next=await response.json();if(owner!==epoch||which!==session)return;
      activity=next;if(optimistic&&activity.job_id!==baselineId&&activity.phase!=='idle')optimistic=0;
      if(activity.phase==='running'){progress.hidden=false;own=true;}
      if(optimistic&&Date.now()-optimistic>20000){optimistic=0;activity={phase:'interrupted',elapsed_seconds:20};}
      if(own)draw();
    }catch(error){if(owner===epoch&&own)meetingLabel(el('reportProgressStage'),'{message} · повторяем проверку состояния',{message:error.message});}
    finally{polling=false;}
  }
  function start(){if(recLive)return;own=true;optimistic=Date.now();baselineId=activity?.job_id||'';progress.hidden=false;draw();check(true);}
  function sync(){
    if(!currentInit)return;
    if(session!==currentInit.current_dir||generation!==currentInit.session_generation){session=currentInit.current_dir;generation=currentInit.session_generation;epoch++;activity=null;optimistic=0;own=false;progress.hidden=true;check(true);}
    strip.hidden=!currentHasTranscript||recLive||document.body.dataset.meetingView==='report';
    meetingLabel(el('meetingFinishReport'),currentMeetingResult?.stale?'Обновить отчёт после продолжения встречи':currentMeetingResult?.has_final?'Открыть готовый отчёт':'Завершить и создать отчёт');
    if(!strip.hidden)el('meetingSavedOverview').hidden=true;
    meetingLabel(el('meetingSavedOverview').querySelector('p'),'Отчёт готовится автоматически. Если имя участника неизвестно, можно назвать голос и сохранить его в банк; подробный разбор фраз необязателен.');
    meetingLabel(el('savedReviewReport'),'Завершить и создать отчёт');if(own)draw();
  }
  el('meetingFinishReport').onclick=()=>currentMeetingResult?.stale?el('reportReviewRegenerate').click():currentMeetingResult?.has_final?openMeetingResult():el('report').click();
  el('meetingFinishDetails').onclick=()=>el('analysisBtn').click();el('meetingFinishContinue').onclick=()=>el('recbtn').click();
  el('meetingFinishSpeakers').onclick=()=>document.dispatchEvent(new CustomEvent('blatero:review-speakers'));
  meetingLabel(el('meetingReadAudio'),'Участники и банк голосов');el('meetingReadAudio').onclick=el('meetingFinishSpeakers').onclick;
  meetingLabel(el('savedReviewAudio'),'Участники и банк голосов');el('savedReviewAudio').onclick=el('meetingFinishSpeakers').onclick;
  el('reportProgressOpen').onclick=()=>currentReportReview.state==='finalized'?openMeetingResult():send({type:'report_review',action:'open'});
  const priorSend=send;send=function(message){
    if(message.type==='report'||message.type==='report_review'&&['regenerate','approve','skip'].includes(message.action))start();
    return priorSend(message);
  };
  document.addEventListener('blatero:meeting-view',sync);
  const prior=handle;handle=function(message){prior(message);if(['init','report_review'].includes(message.type)){sync();if(own)check(true);}};
  setInterval(()=>{if(!document.hidden&&(own||activity?.phase==='running'))check();if(optimistic)draw();},1000);
})();
