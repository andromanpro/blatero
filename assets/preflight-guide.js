/* Explicit, keyboard-accessible readiness step; no microphone opens before confirmation. */
let openPreflightGuide;
(() => {
  const guide=document.createElement('dialog');guide.id='preflightGuide';
  guide.setAttribute('aria-labelledby','preflightGuideTitle');
  guide.innerHTML=`<h2 id="preflightGuideTitle">${studioText('Проверим звук перед встречей')}</h2>
    <p>${studioText('Наденьте наушники и убедитесь, что микрофон не выключен.')}</p>
    <ol><li>${studioText('Нажмите «Я готов, начать». После отсчёта скажите обычным голосом:')}</li></ol>
    <blockquote>«Проверяю микрофон перед встречей. Меня хорошо слышно».</blockquote>
    <p>${studioText('На речь будет 8 секунд. Затем замолчите: программа воспроизведёт тестовый сигнал и проверит остальные компоненты.')}</p>
    <p class="privacy-note">${studioText('Голос этой проверки не сохраняется и не отправляется в облако. Для проверки распознавания используется отдельная встроенная фраза; SpeechKit отправляет только её в Яндекс.')}</p>
    <div id="preflightGuideStatus" role="status" aria-live="polite"></div>
    <div class="meter"><div id="preflightGuideMeter" role="progressbar" ${studioAttrs('aria-label','Уровень микрофона')} aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div></div>
    <div id="preflightGuideChecks" class="preflight-checks"></div>
    <div class="quick-meeting-actions"><button id="preflightGuideClose">${studioText('Закрыть')}</button><button id="preflightGuideGo" class="primary"></button></div>`;
  document.body.append(guide);
  let counting=false,running=false,timer=null;
  const status=document.getElementById('preflightGuideStatus'),go=document.getElementById('preflightGuideGo');
  studioLabel(status,'Проверка ещё не началась.');studioLabel(go,'Я готов, начать');
  function cancelCountdown(){clearInterval(timer);counting=false;}
  guide.addEventListener('close',cancelCountdown);
  document.getElementById('preflightGuideClose').onclick=()=>guide.close();
  openPreflightGuide=()=>{
    if(recLive){alert(studioUi('Во время записи проверка оборудования недоступна. Сначала завершите запись.'));return;}
    if(!running&&!counting){
      go.disabled=false;studioLabel(go,'Я готов, начать');
      studioLabel(status,'Проверка ещё не началась. Нажмите кнопку, когда будете готовы говорить.');
    }
    if(!guide.open)guide.showModal();go.focus();
  };
  go.onclick=()=>{
    if(counting||running)return;
    if(!ws||ws.readyState!==WebSocket.OPEN){studioLabel(status,'Нет подключения к серверу. Проверка не началась.');return;}
    counting=true;go.disabled=true;
    let seconds=3;
    studioLabel(status,'Приготовьтесь говорить. Начало через {seconds}…',()=>({seconds}));
    timer=setInterval(()=>{
      seconds-=1;
      if(seconds>0){studioLabel(status,'Начало через {seconds}…',()=>({seconds}));return;}
      cancelCountdown();running=true;studioLabel(go,'Проверяем…');
      document.getElementById('preflightGuideChecks').replaceChildren();
      studioLabel(status,'Говорите сейчас: «Проверяю микрофон перед встречей». 8 секунд.');
      renderPreflight({state:'started',busy:true,text:'Говорите сейчас: «Проверяю микрофон перед встречей». 8 секунд.',checks:[]});
      send({type:'preflight'});
    },1000);
  };
  const previous=handle;
  handle=function(message){
    previous(message);
    if(message.type==='preflight_level'){
      const value=Math.round(Math.max(0,Math.min(1,Number(message.level)||0))*100),meter=document.getElementById('preflightGuideMeter');
      meter.style.width=value+'%';meter.setAttribute('aria-valuenow',String(value));
    }
    if(message.type==='preflight'){
      running=!!message.busy||['started','progress'].includes(message.state);
      studioLabel(status,()=>({source:preflightSummary(message)}));
      go.disabled=running;studioLabel(go,running?'Проверяем…':'Повторить проверку');
      if(!running)document.getElementById('preflightGuideMeter').style.width='0%';
      if(message.checks)renderPreflightChecks(document.getElementById('preflightGuideChecks'),message.checks);
    }
  };
})();
