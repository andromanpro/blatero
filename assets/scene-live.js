'use strict';
// A real, locally recognized transcript, revealed by the saved audio clock.
// Generated actor text is not a transcript and must never be shown in advance.
(() => {
  const $ = id => document.getElementById(id);
  if(!$('sceneCoachNote'))document.querySelector('.scene-coach-note').id='sceneCoachNote';
  if(!$('sceneAidStage')){
    const stage=document.createElement('div');stage.id='sceneAidStage';stage.className='scene-aid-stage';
    stage.setAttribute('role','status');stage.hidden=true;$('sceneCoachNote').after(stage);
  }
  if(!$('sceneContinueAnswer')){
    const button=document.createElement('button');button.id='sceneContinueAnswer';button.type='button';button.hidden=true;
    $('sceneCoachContent').after(button); // Compatibility during a server/assets update.
  }
  const escape = value => String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let state = null, presentation = '', heard = new Set(), guidance = null;
  let playback = null, coachBusy = false, coachError = '', replayEpoch = 0;
  let spoken = new Map(), playedClips = new Map(), continuation=null, coachStarted=0, firstHintSeconds='';
  const streaming=new Set();
  const cues = new Map(), failures = new Map(), pending = new Set();
  const seconds = value => `${Math.floor(value/60)}:${String(Math.floor(value%60)).padStart(2,'0')}`;

  function reset(data) {
    state = data; presentation = ''; heard = new Set(); guidance = null;
    playback = null; coachBusy = false; coachError=''; spoken=new Map(); playedClips=new Map(); continuation=null; firstHintSeconds=''; replayEpoch++;
    $('sceneSourceText').open = false;
  }
  function begin() {
    if (presentation) return;
    presentation = crypto.randomUUID().replaceAll('-','');
    send({type:'tts_playback',phase:'presentation',session:currentInit.current_dir,
      scene_run_id:state.run_id,presentation_id:presentation});
  }
  function requestCues(clip) {
    if (!clip || streaming.has(clip.name) || cues.has(clip.name) || pending.has(clip.name) || failures.has(clip.name)) return;
    pending.add(clip.name);
    const run = state.run_id;
    fetch('/scene-audio-transcript',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:clip.name,scene_run_id:run})})
      .then(async response => {if(!response.ok)throw new Error(await response.text());return response.json();})
      .then(value => {if(!Array.isArray(value.words))throw new Error(studioUi("Нет временных отметок слов"));cues.set(clip.name,value.words);})
      .catch(error => failures.set(clip.name,error.message))
      .finally(() => {pending.delete(clip.name);if(state?.run_id===run)draw();});
  }
  function drawTranscript() {
    if (!state) return;
    const zone = $('sceneDialogue'), nearBottom = zone.scrollHeight-zone.scrollTop-zone.clientHeight<60;
    const clips = state.audio_clips || [], turns = state.turns || [];
    const shown = turns.filter(turn => turn.source==='takeover' || heard.has(turn.id) || spoken.has(turn.id) || playback?.turn.id===turn.id);
    const html = shown.map(turn => {
      const clip = playedClips.has(turn.id) ? {name:playedClips.get(turn.id)}
        : clips.find(item=>item.turn_id===turn.id);
      const playing = playback?.turn.id===turn.id;
      let time = playing ? playback.audio.currentTime : heard.has(turn.id) ? Infinity : spoken.get(turn.id) || 0;
      if (clip) requestCues(clip);
      const words = clip && cues.get(clip.name);
      const visible = words ? words.filter(word=>word.end<=time+.015) : [];
      const recognized = turn.source==='takeover' ? turn.text : visible.map(word=>word.text).join('').trim();
      const note = failures.get(clip?.name) ? escape(failures.get(clip.name)) : studioText(playing ? "Слушаем и распознаём звук…" : "Локальная расшифровка готовится…");
      return `<article class="scene-turn ${turn.speaker}" data-turn="${escape(turn.id)}" data-speaking="${!!playing}">
        <header><b>${turn.speaker==='interviewer'?studioText("Интервьюер"):studioText("Кандидат")}</b><span>${studioText("раунд ")}${escape(turn.round)}</span>
        ${turn.answer_phase?`<em class="scene-aid-label">${turn.answer_phase==='intro'?studioText("Первые мысли"):studioText("С подсказкой")}</em>`:''}
        <time>${playing?seconds(time):'✓'}</time></header>
        <p class="scene-recognized">${recognized?escape(recognized):`<span class="scene-asr-note">${note}</span>`}${playing&&recognized?'<i class="scene-caret" aria-hidden="true"></i>':''}</p>
        ${heard.has(turn.id)&&turn.source!=='takeover'?`<button class="scene-replay speak-q" data-turn-id="${escape(turn.id)}" ${studioAttrs("aria-label","Повторить реплику")}>${studioText("↻ повторить")}</button>`:''}
      </article>`;
    }).join('');
    // Keep existing cards/buttons alive: word updates must not steal keyboard focus.
    if(html){
      zone.querySelector('.scene-listening-empty')?.remove();
      const template=document.createElement('div');template.innerHTML=html;
      const wanted=new Set();
      for(const fresh of [...template.children]){
        const id=fresh.dataset.turn;wanted.add(id);
        const current=[...zone.children].find(e=>e.dataset.turn===id);
        if(!current){zone.append(fresh);continue;}
        current.dataset.speaking=fresh.dataset.speaking;
        const content=current.querySelector('.scene-recognized'), replacement=fresh.querySelector('.scene-recognized');
        if(content.innerHTML!==replacement.innerHTML)content.innerHTML=replacement.innerHTML;
        studioValue(current.querySelector('time'),fresh.querySelector('time').textContent);
        if(fresh.querySelector('.scene-replay')&&!current.querySelector('.scene-replay'))current.append(fresh.querySelector('.scene-replay'));
      }
      for(const card of [...zone.children])if(!wanted.has(card.dataset.turn))card.remove();
    }else if(!zone.querySelector('.scene-listening-empty')){
      zone.innerHTML=`<div class="scene-listening-empty"><span class="scene-listening-orbit" aria-hidden="true">◌</span><h3>${studioText("Сначала — голос")}</h3><p>${studioText("Расшифровка появится по мере разговора.")}</p></div>`;
    }
    zone.querySelectorAll('.scene-replay').forEach(button=>button.onclick=()=>{
      const turn = turns.find(t=>t.id===button.dataset.turnId);if(turn)playSceneTurn(turn);
    });
    if (nearBottom && html) zone.scrollTop=zone.scrollHeight;
    const complete = turns.length && turns.every(t=>t.source==='takeover'||heard.has(t.id));
    $('sceneSourceText').hidden = !complete;
    $('sceneReview').hidden = !complete || !state.review;
    if(complete)studioValue($('sceneSourceContent'),turns.map(t=>`${t.speaker==='interviewer'?studioUi("Интервьюер"):studioUi("Кандидат")}: ${t.text}`).join('\n\n'));
    studioLabel($('sceneLiveStatus'),()=>({source:"{value}",values:{value:playback ? (playback.turn.speaker==='interviewer'?studioUi("Вопрос звучит"):studioUi("Кандидат отвечает"))
      : complete ? studioUi("Диалог прослушан") : shown.length ? studioUi("Пауза") : studioUi("Готовы слушать")}}));
  }
  function drawCoach() {
    const candidate=state?.coach_audience==='candidate';
    studioLabel($('sceneCoachTitle'),()=>({source:"{value}",values:{value:candidate?studioUi("Подсказка кандидату"):studioUi("Помощь интервьюеру")}}));
    studioLabel($('sceneCoachNote'),()=>({source:"{value}",values:{value:candidate
      ?studioUi("Учебная постановка. Кандидат может использовать опору; это не самостоятельный ответ.")
      :studioUi("Только по услышанному. Участники не получают подсказку.")}}));
    const stage=$('sceneAidStage');stage.hidden=!candidate;
    if(candidate)studioLabel(stage,()=>({source:"{value}",values:{value:playback?.turn.answer_phase==='intro'?studioUi("01 · Первые мысли")
      :playback?.turn.answer_phase==='assisted'?studioUi("03 · Развивает ответ с подсказкой")
      :continuation?studioUi("02 · Читает подсказку"):guidance?studioUi("Опора готова"):studioUi("Слушает вопрос")}}));
    const canAsk = (state?.turns || []).some(t=>t.speaker==='interviewer' && (heard.has(t.id)||t.source==='takeover'));
    const button=$('sceneCoach');
    button.disabled=!canAsk || coachBusy;
    studioLabel(button,()=>({source:"{value}",values:{value:coachBusy?studioUi("Готовлю по услышанному…"):guidance?studioUi("Обновить подсказки"):studioUi("Получить подсказки")}}));
    const zone=$('sceneCoachContent');
    const next=$('sceneContinueAnswer');next.hidden=!continuation;
    next.disabled=candidate ? !(guidance?.answer&&!guidance.partial&&!coachBusy)
      : !(guidance?.answer || (!coachBusy&&guidance) || coachError);
    studioLabel(next,()=>({source:"{value}",values:{value:candidate?studioUi("Прочитал · ответить с подсказкой")
      :coachError?studioUi("Продолжить без подсказки"):studioUi("Прочитал · продолжить ответ")}}));
    if(!canAsk){zone.innerHTML=`<div class="scene-coach-wait"><span>01</span><p>${studioText("Сначала прослушайте вопрос.")}<br>${studioText("Затем появятся ориентиры для ответа.")}</p></div>`;return;}
    if(coachError){zone.innerHTML=`<p class="scene-asr-note">${escape(coachError)}</p>`;return;}
    if(!guidance){zone.innerHTML=coachBusy?`<div class="scene-coach-wait is-working"><span>◌</span><p>${studioText("Разбираю услышанный вопрос…")}</p></div>`:`<p class="scene-asr-note">${studioText("Можно запросить подсказку по услышанному.")}</p>`;return;}
    const model=guidance.model==='deepseek/deepseek-v4-flash'?'DeepSeek Flash':guidance.model||studioUi("ИИ");
    const timing=guidance.replay?studioText(" · исходная подсказка"):firstHintSeconds?studioText(" · за ")+firstHintSeconds+studioText(" с"):'';
    zone.innerHTML=(guidance.answer?`<article class="scene-answer-help"><span class="scene-eyebrow">${studioText("Опора для ответа · ")}${escape(model)}${timing}${guidance.partial?studioText(" · дополняю"):''}</span><p>${escape(guidance.answer)}</p></article>`:'')
      +`<div class="scene-coach-focus"><span class="scene-eyebrow">${candidate?studioText("Суть ответа"):studioText("Сейчас проверяем")}</span><p>${escape(guidance.focus)}</p></div>`
      +(guidance.watch_for?.length?`<section><h4>${candidate?studioText("Не забыть"):studioText("На что обратить внимание")}</h4><ul>`+guidance.watch_for.map(t=>`<li>${escape(t)}</li>`).join('')+'</ul></section>':'')
      +(guidance.questions||[]).map(item=>`<article><span class="scene-eyebrow">${candidate?studioText("Проверка решения"):studioText("Можно уточнить")}</span><strong>${escape(item.q)}</strong><p>${escape(item.why)}</p></article>`).join('');
  }
  function draw(){drawTranscript();drawCoach();}
  function render(data) {
    if(!state || state.run_id!==data.run_id || state.session!==data.session)reset(data);
    state=data;
    if(!presentation && data.run_id && (data.turns||[]).some(t=>t.source==='takeover'))begin();
    if('coach_busy' in data){coachBusy=!!data.coach_busy;if(coachBusy)coachError='';}
    if(data.coach_error)coachError=data.coach_error;
    if(data.coach?.presentation_id===presentation && heard.has(data.coach.based_on_turn)){
      const fresh=!guidance?.answer&&data.coach.answer;guidance=data.coach;
      if(fresh&&coachStarted)firstHintSeconds=((performance.now()-coachStarted)/1000).toFixed(1);
    }
    $('sceneReplayRun').hidden=!(data.turns||[]).some(t=>t.source!=='takeover');
    $('sceneReplayRun').disabled=!!recLive;
    draw();
  }
  function attach(audio, meta) {
    const turn=state?.turns?.find(t=>t.id===meta.turnId);
    if(!turn || state.run_id!==meta.runId)return;
    begin();
    const run=state.run_id, pid=presentation;
    playedClips.set(turn.id,meta.name);
    if(meta.streaming)streaming.add(meta.name);
    const entry={audio,turn,name:meta.name};
    audio.addEventListener('playing',()=>{if(state?.run_id===run && presentation===pid){
      playback=entry;if(activeQuestionAudio?.button===$('sceneReplayRun'))studioLabel($('sceneReplayRun'),"■ Остановить");draw();
    }});
    audio.addEventListener('timeupdate',()=>{if(playback===entry){spoken.set(turn.id,audio.currentTime);drawTranscript();}});
    audio.addEventListener('ended',()=>{
      if(state?.run_id!==run || presentation!==pid)return;
      heard.add(turn.id);if(playback===entry)playback=null;
      send({type:'tts_playback',phase:'complete',text:turn.text,voice:meta.voice,
        session:currentInit.current_dir,scene_turn_id:turn.id,scene_run_id:run,
        presentation_id:pid,played_ms:Math.round(audio.duration*1000)});
      if(turn.speaker==='interviewer'){coachBusy=true;coachStarted=performance.now();guidance=null;}
      draw();
    });
    audio.addEventListener('pause',()=>{if(playback===entry){playback=null;draw();}});
    audio.addEventListener('error',()=>{if(playback===entry){playback=null;draw();}});
    audio.addEventListener('clipready',()=>{streaming.delete(meta.name);failures.delete(meta.name);requestCues({name:meta.name});});
    requestCues({name:meta.name});
  }
  function replay() {
    if(!state?.turns?.length)return;
    if(activeQuestionAudio){replayEpoch++;stopQuestionAudio();studioLabel($('sceneReplayRun'),"▶ Прослушать диалог");return;}
    reset(state);begin();
    const epoch=replayEpoch, run=state.run_id, turns=[...state.turns].filter(t=>t.source!=='takeover');
    studioLabel($('sceneReplayRun'),"■ Остановить");draw();
    const next=index=>{
      if(epoch!==replayEpoch || state.run_id!==run)return;
      const turn=turns[index];if(!turn){studioLabel($('sceneReplayRun'),"↻ Прослушать заново");return;}
      playQuestion(turn.text,$('sceneReplayRun'),{sceneTurnId:turn.id,sceneRunId:run,
        sceneSpeaker:turn.speaker,voice:sceneVoice(turn),onDone:()=>{
          if(turns[index+1])afterTurn(turn,()=>next(index+1));
          else setTimeout(()=>next(index+1),400);
        }});
    };next(0);
  }
  $('sceneReplayRun').onclick=replay;
  function afterQuestion(next){continuation=next;studioLabel($('sceneReplayRun'),"Пауза для подсказки");drawCoach();}
  function afterTurn(turn,next){
    const aided=state?.coach_audience==='candidate'&&state?.takeover!=='candidate';
    if(aided&&turn.answer_phase==='intro')afterQuestion(next);
    else if(!aided&&turn.speaker==='interviewer')afterQuestion(next);
    else setTimeout(next,400);
  }
  $('sceneContinueAnswer').onclick=()=>{const next=continuation;continuation=null;drawCoach();
    document.querySelector('.scene-coach').scrollTop=0;next?.();};
  setInterval(()=>{if(coachBusy&&coachStarted){const label=currentInit?.config?.scene_coach_route==='openrouter_flash'?'DeepSeek Flash':studioUi("ИИ");
    studioLabel($('sceneCoach'),()=>({source:"{value}",values:{value:studioUi("{p0} · {p1} · готовлю",{p0:label,p1:seconds((performance.now()-coachStarted)/1000)})}})); }},500);
  function words(name,value){if(!Array.isArray(value))return;cues.set(name,[...(cues.get(name)||[]),...value]);drawTranscript();}
  window.BlateroSceneLive={render,attach,words,afterQuestion,afterTurn,reset:()=>{if(state)reset(state);draw();}};
})();
