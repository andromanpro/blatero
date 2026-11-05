'use strict';
// Keyed cards remain under the reader's eyes. Pulses only enqueue unseen cards.
(() => {
  const el=id=>document.getElementById(id), zone=el('hintzone');
  const bar=document.createElement('div');bar.className='hint-queue-bar';bar.id='hintQueueBar';
  bar.innerHTML='<button id="hintShowNew" type="button" class="primary" hidden></button><button id="hintActiveRisks" type="button" hidden></button><span id="hintQueueNotice" role="status" aria-live="polite"></span>';
  el('answers').before(bar);
  const pins=document.createElement('section');pins.id='hintPins';pins.setAttribute('aria-label','Закреплённые подсказки');bar.after(pins);
  const history=document.createElement('section');history.id='hintHistory';history.setAttribute('aria-label','История подсказок и рисков');
  el('uncovered').after(history);
  window.BlateroMeetingI18n?.bindStatic(pins);window.BlateroMeetingI18n?.bindStatic(history);
  let session='',generation=null,data=null,pending=new Set(),shown=new Set(),nodes=new Map(),fading=new Map(),actions=Promise.resolve();
  const groups={answer:el('answers'),question:el('questions'),risk:el('flags')};
  function say(text,params={}){meetingLabel(el('hintQueueNotice'),text,params);}
  function valid(m){return !m.session || (m.session===session && (m.generation==null||m.generation===generation));}
  function reset(){
    data=null;pending.clear();shown.clear();nodes.clear();fading.clear();
    for(const container of Object.values(groups))container.replaceChildren();
    pins.replaceChildren();history.replaceChildren();el('hintShowNew').hidden=true;say('');
  }
  async function perform(id,action,reason){
    const ownSession=session,ownGeneration=generation;
    if(!data)return;
    const response=await fetch('/api/sessions/'+encodeURIComponent(session)+'/hint-action',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,action,reason,revision:data.revision,generation})});
    const result=await response.json();
    if(session!==ownSession||generation!==ownGeneration)return;
    if(!response.ok)throw Error(result.error||meetingUi('Действие не сохранено'));
    accept(result);
  }
  function act(id,action,reason){
    actions=actions.then(()=>perform(id,action,reason)).catch(error=>say(error.message));return actions;
  }
  function button(label,action,card,css='',owned=true){
    const b=document.createElement('button');b.type='button';b.className=css;
    if(owned){meetingLabel(b,label);meetingAttr(b,'title',label);meetingAttr(b,'aria-label',label);}
    else{b.textContent=label;b.title=label;b.setAttribute('aria-label',label);}
    b.onclick=()=>action(card,b);return b;
  }
  function create(card){
    const node=document.createElement('article');node.className=card.kind==='answer'?'answer-card':card.kind==='risk'?'f':'q';
    node.classList.add('persistent-hint');node.dataset.hintId=card.id;
    const text=document.createElement('strong');text.className='hint-card-text';text.textContent=card.text;node.append(text);
    if(card.why){const why=document.createElement('span');why.className='qw';why.textContent='— '+card.why;node.append(why);}
    const controls=document.createElement('span');controls.className='hint-actions';
    if(card.kind!=='risk')controls.append(button('▶',(c,b)=>playQuestion(c.text,b),card,'hint-speak'));
    controls.append(button('Закрепить',c=>act(c.id,c.pinned?'unpin':'pin'),card,'hint-pin'));
    if(card.kind==='answer')controls.append(button('Крупно',c=>openFocusAnswer(c.text),card,'hint-focus'));
    controls.append(button(card.kind==='risk'?'Решён':'Отвечен',c=>act(c.id,'resolve'),card,'hint-resolve'));
    const dismiss=document.createElement('details');dismiss.className='hint-dismiss';
    dismiss.innerHTML='<summary title="Убрать неудачную подсказку" aria-label="Убрать подсказку">×</summary>';
    window.BlateroMeetingI18n?.bindStatic(dismiss);
    for(const [reason,label] of [['irrelevant','Неактуально'],['unhelpful','Бесполезный вопрос'],['duplicate','Повтор']])
      dismiss.append(button(label,c=>act(c.id,'dismiss',reason),card));
    controls.append(dismiss);node.append(controls);
    node.onpointerenter=()=>pause(card.id,true);node.onpointerleave=()=>pause(card.id,false);
    node.onfocusin=()=>pause(card.id,true);node.onfocusout=()=>pause(card.id,false);
    return node;
  }
  function pause(id,paused){const f=fading.get(id);if(!f)return;if(paused&&!f.paused)f.paused=Date.now();else if(!paused&&f.paused){f.end+=Date.now()-f.paused;f.paused=0;}}
  function updateNode(node,card){
    // Never replace the node/text while a user is reading or using its controls.
    const pin=node.querySelector('.hint-pin'),pinLabel=card.pinned?'Открепить':'Закрепить';meetingLabel(pin,pinLabel);meetingAttr(pin,'title',pinLabel);meetingAttr(pin,'aria-label',pinLabel);pin.setAttribute('aria-pressed',String(card.pinned));
    node.classList.toggle('is-pinned',card.pinned);node.classList.toggle('hint-stale',card.stale);
    if(card.pinned){fading.delete(card.id);node.style.opacity='';}
    // The callbacks refer to this same object, so refresh its state after a pulse/action.
    Object.assign(node._card||(node._card=card),card);
  }
  function renderHistory(){
    const sections=[['past','Ранее показанные · не отмечены решёнными',c=>c.kind!=='risk'&&c.status==='active'&&!shown.has(c.id)&&!pending.has(c.id)&&!c.pinned],
      ['activeRisks','Незакрытые риски вне основного экрана',c=>c.kind==='risk'&&c.status==='active'&&!shown.has(c.id)&&!pending.has(c.id)&&!c.pinned],
      ['risks','Решённые риски',c=>c.kind==='risk'&&c.status==='resolved'],
      ['resolved','Решённые вопросы и ответы',c=>c.kind!=='risk'&&c.status==='resolved'],
      ['dismissed','Отклонённые подсказки',c=>c.status==='dismissed']];
    for(const [id,title,test] of sections){
      let section=history.querySelector('[data-history="'+id+'"]');
      if(!section){section=document.createElement('details');section.dataset.history=id;section.innerHTML='<summary></summary><div></div>';history.append(section);}
      const cards=data.cards.filter(test);section.hidden=!cards.length;meetingLabel(section.querySelector('summary'),'{text} · {count}',()=>({text:meetingUi(title),count:cards.length}));
      const body=section.querySelector('div');body.replaceChildren();
      for(const card of cards.slice().reverse()){
        const row=document.createElement('div');row.className='hint-history-row';const text=document.createElement('span');meetingLabel(text,'{prefix}{text}',()=>({prefix:card.kind==='risk'?meetingUi('Риск: '):'',text:card.text}));
        row.append(text,button('Вернуть',c=>{shown.add(c.id);act(c.id,'restore');},card));body.append(row);
      }
    }
  }
  function render(){
    if(!data)return;el('pinnedHint').hidden=true;
    for(const card of data.cards){
      let node=nodes.get(card.id);
      if(card.status!=='active'||card.archived&&!card.pinned){shown.delete(card.id);pending.delete(card.id);fading.delete(card.id);node?.remove();continue;}
      if(!shown.has(card.id)&&!card.pinned)continue;
      if(!node){node=create(card);node._card=card;nodes.set(card.id,node);}
      updateNode(node,card);const parent=card.pinned?pins:groups[card.kind];if(node.parentNode!==parent)parent.prepend(node);
    }
    pins.hidden=!pins.childElementCount;el('hintShowNew').hidden=!pending.size;meetingLabel(el('hintShowNew'),'Показать новые · {count}',{count:pending.size});
    const risks=data.cards.filter(c=>c.kind==='risk'&&c.status==='active').length;
    bar.dataset.activeRisks=String(risks);meetingAttr(bar,'title','Незакрытых рисков: {count}',{count:risks});
    el('hintActiveRisks').hidden=!risks;meetingLabel(el('hintActiveRisks'),'Незакрытые риски · {count}',{count:risks});renderHistory();
  }
  function accept(next){
    if(!next||!Array.isArray(next.cards))return;if(data&&next.revision<data.revision)return;
    // A late-loaded controller can inherit legacy markup rendered before its
    // arrival. The first structured state replaces it, not the next user edit.
    if(!data&&next.cards.length)for(const container of Object.values(groups))container.replaceChildren();
    const first=!data||!data.cards.length,known=new Set(data?.cards.map(c=>c.id)||[]);data=next;
    if(next.error)say('{message} · исходные ответы и записи сохранены',{message:next.error});
    if(first){for(const c of data.cards)if(c.status==='active'&&!c.archived&&(c.last_pulse===data.last_pulse||c.pinned))shown.add(c.id);}
    else {for(const c of data.cards)if(!known.has(c.id)&&c.status==='active'&&!c.archived)pending.add(c.id);}
    render();
  }
  el('hintShowNew').onclick=()=>{
    const old=[...shown];for(const id of pending)shown.add(id);
    // Moving cards is intentional only here, never on a background pulse.
    const newCards=data.cards.filter(c=>pending.has(c.id));pending.clear();render();
    for(const c of newCards){const node=nodes.get(c.id);if(node&&!c.pinned)groups[c.kind].prepend(node);}
    for(const id of old){const c=data.cards.find(c=>c.id===id);if(c&&!c.pinned)fading.set(id,{end:Date.now()+45000,paused:0});}
    say('Новые показаны. Старые незакреплённые уйдут в историю через 45 секунд; наведите курсор, чтобы задержать.');zone.scrollTo({top:0,behavior:'smooth'});
  };
  el('hintActiveRisks').onclick=()=>{const section=history.querySelector('[data-history=activeRisks]');if(section&&!section.hidden){section.open=true;section.scrollIntoView({block:'nearest'});}else say('Риски находятся на экране или ожидают за кнопкой «Показать новые».');};
  setInterval(()=>{
    if(!data||document.hidden)return;
    for(const [id,f] of fading){const node=nodes.get(id),c=data.cards.find(c=>c.id===id);
      if(!node||!c||c.pinned){fading.delete(id);continue;}if(f.paused)continue;
      const left=f.end-Date.now();node.style.opacity=String(Math.max(.08,Math.min(1,left/18000)));
      if(left<=0){fading.delete(id);act(id,'archive');}
    }
  },500);
  const originalRender=renderHints;
  renderHints=function(h,state){
    if(!state){originalRender(h);return;}
    el('empty').style.display='none';syncEmptyLayout();const first=h.answers?.[0];latestAnswer=typeof first==='object'?first.answer:String(first||'');
    el('tags').replaceChildren();for(const tag of h.tags||[])el('tags').append(button(tag,()=>send({type:'tag',tag}),{},'tag',false));
    meetingLabel(el('uncovered'),(h.uncovered||[]).length?'Уточнить: {text}':'',{text:(h.uncovered||[]).join(' · ')});accept(state);
  };
  const priorHandle=handle;
  handle=function(message){
    if(message.type==='init'){
      if(session!==message.current_dir||generation!==message.session_generation){reset();session=message.current_dir;generation=message.session_generation;}
    }else if(['hints','hint_state'].includes(message.type)&&!valid(message))return;
    priorHandle(message);if(message.type==='init')accept(message.hint_state);if(message.type==='hint_state')accept(message.hint_state);
  };
  // The initial WS frame may arrive while later assets are still downloading.
  // Do not replay init (which would reset fields); adopt only this controller's
  // session identity and its durable hint state.
  if(currentInit){
    session=currentInit.current_dir;generation=currentInit.session_generation;
    if(currentInit.hint_state?.cards?.length)accept(currentInit.hint_state);
  }
})();
