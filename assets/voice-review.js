'use strict';
(() => {
  const dialog=document.createElement('dialog');dialog.id='voiceReviewDialog';
  dialog.innerHTML='<div class="voice-review-heading"><div><h2>Кто участвовал во встрече?</h2><p>Технический разбор выполняется локально. Вам — только узнать неизвестный голос.</p></div><button type="button" id="voiceReviewClose">Готово</button></div><p id="voiceReviewStatus" role="status" aria-live="polite"></p><button type="button" id="voiceReviewPrepare" class="primary">Автоматически найти голоса</button><div id="voiceReviewRows"></div><details><summary>Что происходит с данными?</summary><p>Все дорожки звука встречи обрабатываются локально. Исходные WAV и транскрипты не изменяются. Совпадение с банком — предположение, которое может быть ошибочным. Имя сохраняется в этом разборе; само по себе оно не переименовывает реплики и не пересобирает уже готовый отчёт. Голосовой отпечаток хранится в банке только по отдельному согласию. Удалить его можно в настройках банка голосов.</p></details>';
  document.body.append(dialog);
  dialog.querySelector('h2').id='voiceReviewTitle';
  dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');dialog.setAttribute('aria-labelledby','voiceReviewTitle');
  const progress=document.createElement('progress');progress.id='voiceReviewProgress';progress.hidden=true;progress.style.width='100%';
  const elapsed=document.createElement('p');elapsed.id='voiceReviewElapsed';elapsed.setAttribute('role','timer');elapsed.setAttribute('aria-live','off');
  const units=document.createElement('p');units.id='voiceReviewUnits';
  const warning=document.createElement('div');warning.id='voiceReviewWarning';warning.className='warning';
  const timings=document.createElement('details');timings.id='voiceReviewTimings';
  const operationError=document.createElement('p');operationError.id='voiceReviewError';operationError.setAttribute('role','alert');operationError.hidden=true;
  dialog.querySelector('#voiceReviewStatus').after(operationError);
  dialog.querySelector('#voiceReviewStatus').after(progress,units,elapsed,warning,timings);
  window.BlateroMeetingI18n?.bindStatic(dialog);
  const el=id=>document.getElementById(id);let session='',epoch=0,busy=false,timer=null,player=null,sequence=0,loading=false;
  const drafts=new Map();
  function stopPlayer(){player?.pause();player=null;}
  function stop(){stopPlayer();clearTimeout(timer);timer=null;}
  function schedule(data){clearTimeout(timer);timer=null;if(data.state==='running')timer=setTimeout(()=>{timer=null;return load();},2000);}
  el('voiceReviewClose').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{if(dialog.open)return;epoch++;busy=false;stop();});
  function render(data){
    const stages={bank:'Читаем банк голосов',diarization:'Разделяем голоса',load_audio:'Читаем аудио',embeddings:'Вычисляем голосовые признаки',matching:'Сравниваем с банком',samples:'Готовим образцы'};
    const running=data.state==='running';
    if(running&&stages[data.stage])meetingLabel(el('voiceReviewStatus'),'{stage} · дорожка {track} из {total}',()=>({stage:meetingUi(stages[data.stage]),track:data.track_index||1,total:data.track_total||1}));
    else meetingLabel(el('voiceReviewStatus'),data.message||'');
    progress.hidden=!running;
    if(running&&Number(data.stage_total)>0){progress.max=Number(data.stage_total);progress.value=Number(data.stage_done)||0;}
    else progress.removeAttribute('value');
    units.hidden=!running||!Number(data.stage_total);
    meetingLabel(units,'Обработано: {done} из {total}',{done:data.stage_done||0,total:data.stage_total||0});
    window.BlateroMeetingI18n?.attr(progress,'aria-label','Прогресс текущего этапа');
    elapsed.hidden=!data.started_at;
    const seconds=Math.max(0,Math.floor(Number(data.elapsed_seconds)||0));
    meetingLabel(elapsed,running?'Прошло {time} · общее время заранее неизвестно':'Время разбора: {time}',{time:Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')});
    for(const child of warning.querySelectorAll('*'))window.BlateroMeetingI18n?.forget(child);
    warning.replaceChildren();
    for(const item of data.warnings||[]){if(item.code==='many_clusters'){const note=document.createElement('p');meetingLabel(note,'Дорожка {track}: найдено {count} голосовых кластеров. Это не число участников; возможна избыточная разбивка.',{track:item.track,count:item.clusters});warning.append(note);}}
    for(const child of timings.querySelectorAll('*'))window.BlateroMeetingI18n?.forget(child);
    timings.replaceChildren();timings.hidden=running||!data.timings?.length;
    if(!timings.hidden){const summary=document.createElement('summary');meetingLabel(summary,'Время по этапам');timings.append(summary);const sums={};for(const row of data.timings||[])sums[row.stage]=(sums[row.stage]||0)+Number(row.seconds||0);for(const [stage,time] of Object.entries(sums)){const line=document.createElement('p');meetingLabel(line,'{stage}: {seconds} с',()=>({stage:meetingUi(stages[stage]||stage),seconds:time.toFixed(2)}));timings.append(line);}}
    meetingLabel(el('voiceReviewClose'),running?'Скрыть':'Готово');
    el('voiceReviewPrepare').hidden=data.state==='ready'||running;el('voiceReviewPrepare').disabled=busy||running||data.state==='needs_models';
    if(data.state==='running')return;
    el('voiceReviewRows').replaceChildren();
    const known=document.createElement('details');known.className='voice-review-known';known.innerHTML='<summary>Предположения банка и уже названные голоса</summary>';
    window.BlateroMeetingI18n?.bindStatic(known);
    let knownCount=0;
    for(const voice of data.voices||[]){
      const card=document.createElement('article');card.className='voice-review-card';
      const title=document.createElement('strong');if(voice.name)title.textContent=voice.name;else meetingLabel(title,'Неизвестный участник');
      const note=document.createElement('p');
      if(voice.name_source==='bank_suggestion')meetingLabel(note,'Предположение банка · {reason}',()=>({reason:voice.match?.reason||meetingUi('проверьте на слух')}));
      else if(voice.name_source==='operator_confirmed')meetingLabel(note,'Имя подтверждено вами');
      else if(voice.match?.state==='stale')meetingLabel(note,'Повторите сравнение с банком голосов');
      else if(voice.match?.reason)note.textContent=voice.match.reason;
      else meetingLabel(note,'Назовите участника по короткому образцу');
      const play=document.createElement('button');play.type='button';meetingLabel(play,'▶ Послушать голос');
      play.onclick=()=>{stopPlayer();player=new Audio('/files/'+encodeURIComponent(session)+'/'+encodeURIComponent(voice.audio));player.preload='metadata';player.onloadedmetadata=()=>{player.currentTime=Number(voice.start_ms)/1000;player.play().catch(e=>{meetingLabel(el('voiceReviewStatus'),'Не удалось воспроизвести: {message}',{message:e.message});});};player.ontimeupdate=()=>{if(player&&player.currentTime>=Number(voice.end_ms)/1000)player.pause();};};
      const draft=drafts.get(voice.id);
      const label=document.createElement('label'),nameLabel=document.createElement('span');meetingLabel(nameLabel,'Имя участника');label.append(nameLabel);const input=document.createElement('input');input.maxLength=80;input.value=draft?.name??voice.name??'';label.append(input);
      const consent=document.createElement('label');consent.className='voice-review-consent';const check=document.createElement('input');check.type='checkbox';
      check.disabled=!!voice.enrollment_active&&!voice.enrollment_recovered;
      check.checked=!check.disabled&&draft?.consentRevision===voice.consent_revision&&!!draft?.consent;
      const consentText=document.createElement('span');meetingLabel(consentText,check.disabled?'Голос уже сохранён в банке':'Есть согласие участника: сохранить голосовой отпечаток в банке для следующих встреч');consent.append(check,consentText);
      const save=document.createElement('button');save.type='button';meetingLabel(save,'Сохранить имя');
      const labelSave=()=>meetingLabel(save,check.checked?'Сохранить имя и голос в банк':'Сохранить имя');
      const keep=()=>drafts.set(voice.id,{name:input.value,consent:check.checked,consentRevision:voice.consent_revision});
      input.oninput=keep;check.onchange=()=>{keep();labelSave();};labelSave();
      save.onclick=async()=>{if(busy)return;keep();const draft=drafts.get(voice.id);save.disabled=true;
        try{await request('save',{id:voice.id,name:draft.name,enroll:draft.consent,consent:draft.consent,consent_revision:draft.consentRevision},draft);}
        finally{save.disabled=false;}};
      card.append(title,note,play,label,consent,save);
      if(voice.name){known.append(card);knownCount++;}else el('voiceReviewRows').append(card);
    }
    if(knownCount){meetingLabel(known.querySelector('summary'),'{text} · {count}',()=>({text:meetingUi('Предположения банка и уже названные голоса'),count:knownCount}));el('voiceReviewRows').append(known);}
  }
  async function load(){if(loading)return;const owner=epoch,ticket=++sequence;loading=true;try{const response=await fetch('/api/sessions/'+encodeURIComponent(session)+'/voice-review',{cache:'no-store'});const data=await response.json();if(owner!==epoch||ticket!==sequence)return;if(!response.ok)throw Error(data.error);render(data);schedule(data);}catch(e){if(owner===epoch&&ticket===sequence){meetingLabel(el('voiceReviewStatus'),'{messages}',{messages:e.message});schedule({state:'running'});}}finally{if(owner===epoch)loading=false;}}
  async function request(action,body={},draft=null){
    if(busy)return;const owner=epoch,which=session;++sequence;busy=true;operationError.hidden=true;el('voiceReviewPrepare').disabled=true;meetingLabel(el('voiceReviewStatus'),action==='prepare'?'Ищем голоса во всех дорожках; это может занять несколько минут…':'Сохраняем локально…');
    if(action==='prepare')schedule({state:'running'});
    try{const response=await fetch('/api/sessions/'+encodeURIComponent(which)+'/voice-review/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(owner!==epoch)return;++sequence;if(!response.ok){if(data.code==='consent_changed'&&draft&&drafts.get(body.id)===draft){draft.consent=false;loading=false;void load();}throw Error(data.error);}if(draft&&drafts.get(body.id)===draft)drafts.delete(body.id);busy=false;render(data);schedule(data);}
    catch(e){if(owner===epoch){operationError.hidden=false;meetingLabel(operationError,'{messages}',{messages:e.message});meetingLabel(el('voiceReviewStatus'),'Операция не завершена');}}
    finally{if(owner===epoch){busy=false;el('voiceReviewPrepare').disabled=false;}}
  }
  el('voiceReviewPrepare').onclick=()=>request('prepare');
  document.addEventListener('blatero:review-speakers',()=>{if(recLive)return;session=currentInit?.current_dir;epoch++;stop();drafts.clear();loading=false;busy=false;operationError.hidden=true;el('voiceReviewRows').replaceChildren();dialog.showModal();load();});
  document.addEventListener('blatero:meeting',event=>{if(dialog.open&&event.detail.current_dir!==session){epoch++;dialog.close();}});
})();
