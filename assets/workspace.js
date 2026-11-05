'use strict';
// A shared shell around both applications. All task writes keep the source/revision contract.
(() => {
  const root = document.documentElement;
  const q = selector => document.querySelector(selector);
  const projectPage = location.pathname === '/projects';
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const params = new URLSearchParams(location.search);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let preferredMotion = setting('motion') !== 'off';
  let session = '', context = null, contextVersion = 0, initialRoute = false, routePanelApplied=false, allTasks = [];
  let materialScope = projectPage ? params.get('material') || '' : '', applyingRoute=false;
  const statuses = {inbox:'Входящие',active:'В работе',waiting:'Ожидает',review:'На проверке',done:'Завершено'};
  function setting(name, value) {
    try {
      if (value !== undefined) localStorage.setItem('blatero.projects.'+name, value);
      return localStorage.getItem('blatero.projects.'+name);
    } catch { return null; }
  }
  function notice(message) {
    let element = q('.space-toast');
    if (!element) { element = document.createElement('div'); element.className='space-toast'; element.setAttribute('role','status'); document.body.append(element); }
    element.textContent=message; element.hidden=false;
    clearTimeout(notice.timer); notice.timer=setTimeout(()=>element.hidden=true,6500);
  }
  async function request(path, body) {
    const response = await fetch('/api/projects/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
    const value = await response.json();
    if (!response.ok) throw Error(value.error || 'Не удалось прочитать рабочее пространство');
    return value;
  }
  function href(view, project='') {
    const search=new URLSearchParams();
    if(view && view!=='board')search.set('view',view);
    if(project)search.set('project',project);
    return '/projects'+(search.size?'?'+search:'');
  }
  function taskHref(task) { const url=new URL(href('board',task.project_id),location.origin);url.searchParams.set('task',task.id);return url.pathname+url.search; }
  const shell=document.createElement('div');
  shell.className='workspace-shell'; shell.setAttribute('role','banner');
  shell.innerHTML='<a class="space-brand" href="/" aria-label="Blatero — рабочее пространство"><span class="brand-emblem" aria-hidden="true"><img src="/assets/blatero-mark.svg" alt="" width="34" height="34"></span><span class="brand-wordmark">blatero</span></a><nav class="space-nav" aria-label="Рабочее пространство"><a data-space="daily" href="/projects?view=daily">Сегодня</a><a data-space="meeting" href="/">Встречи</a><a data-space="board" href="/projects">Проекты</a><a data-space="planning" href="/projects?view=planning">План</a><a data-space="materials" href="/projects?view=materials">Материалы</a><a data-space="knowledge" href="/projects?view=knowledge">Библиотека</a><a data-space="archive" href="/?panel=archive">Архив</a></nav><div class="space-actions"></div>';
  document.body.prepend(shell); document.body.classList.add(projectPage?'space-projects':'space-meeting');
  const navElement=shell.querySelector('.space-nav'), navFrame=document.createElement('div');
  navFrame.className='space-nav-frame';navElement.before(navFrame);navFrame.append(navElement);
  function navArrow(direction,key,glyph){
    const button=document.createElement('button');button.type='button';button.className='space-nav-arrow';
    button.dataset.i18nAria=key;button.dataset.i18nTitle=key;button.textContent=glyph;
    button.setAttribute('aria-label',direction<0?'Предыдущие разделы':'Следующие разделы');
    button.onclick=()=>navElement.scrollBy({left:direction*Math.max(120,navElement.clientWidth*.7),behavior:'auto'});
    return button;
  }
  const navPrevious=navArrow(-1,'navPrevious','‹'),navNext=navArrow(1,'navNext','›');
  navFrame.prepend(navPrevious);navFrame.append(navNext);
  function updateNavArrows(){
    navPrevious.hidden=navElement.scrollLeft<=1;
    navNext.hidden=navElement.scrollLeft+navElement.clientWidth>=navElement.scrollWidth-1;
  }
  navElement.addEventListener('scroll',updateNavArrows,{passive:true});
  new ResizeObserver(updateNavArrows).observe(navFrame);
  document.addEventListener('blatero:language',()=>queueMicrotask(updateNavArrows));
  queueMicrotask(updateNavArrows);
  if(projectPage)window.BlateroProjectsI18n?.bindStatic(shell);
  shell.querySelectorAll('[data-space]').forEach(link => {
    link.dataset.i18n = ({meeting:'meetings',board:'projects',daily:'today',knowledge:'library'})[link.dataset.space] || link.dataset.space;
  });
  window.BlateroBrand?.mount(shell.querySelector('.brand-emblem'));
  if (!projectPage && q('.header-primary')) {
    const compact=document.createElement('a'); compact.className='compact-brand';
    compact.href='/'; compact.setAttribute('aria-label','Blatero — рабочее пространство');
    compact.innerHTML='<span class="brand-emblem" aria-hidden="true"><img src="/assets/blatero-mark.svg" alt="" width="34" height="34"></span>';
    q('.header-primary').prepend(compact); window.BlateroBrand?.mount(compact.querySelector('.brand-emblem'));
  }
  const actions=shell.querySelector('.space-actions');
  for(const [id,html] of [['motionToggle','Движение <span aria-hidden="true">◉</span>'],['themeToggle','Тема']]) {
    let button=document.getElementById(id);
    if(!button){button=document.createElement('button');button.id=id;button.innerHTML=html;}
    if(projectPage || !q('#workspaceAppearanceSettings')) actions.append(button);
  }
  if(projectPage && q('#newProject'))actions.append(q('#newProject'));
  if(projectPage) {
    const appearance=document.createElement('dialog'); appearance.id='workspaceAppearanceDialog';
    appearance.className='meeting-work-dialog'; appearance.setAttribute('aria-labelledby','workspaceAppearanceTitle');
    appearance.innerHTML='<div class="meeting-work-heading"><h2 id="workspaceAppearanceTitle" data-i18n="appearance">Настройки вида</h2><button type="button" data-close-appearance aria-label="Закрыть">×</button></div><div class="space-appearance-controls"></div>';
    if(projectPage)projectAttr(appearance.querySelector('button'),'aria-label','Закрыть');
    appearance.querySelector('.space-appearance-controls').append(q('#themeToggle'),q('#motionToggle'));
    appearance.querySelector('button').onclick=()=>appearance.close(); document.body.append(appearance);
    const button=document.createElement('button');button.id='workspaceAppearanceButton';button.innerHTML='⚙ <span data-i18n="appearance">Настройки вида</span>';button.onclick=()=>appearance.showModal();actions.append(button);
  }
  for (const [id,key] of [['themeToggle','theme'],['motionToggle','motion'],['newProject','newProject']]) {
    const el=q('#'+id);if(el)el.dataset.i18n=key;
  }
  window.BlateroI18n?.apply();
  new ResizeObserver(()=>root.style.setProperty('--workspace-height',shell.getBoundingClientRect().height+'px')).observe(shell);
  function syncMotion() {
    const enabled=preferredMotion&&!reduced.matches;
    root.dataset.motion=enabled?'on':'off';
    const button=q('#motionToggle');button.setAttribute('aria-pressed',String(enabled));button.disabled=reduced.matches;
    const label=reduced.matches?'Анимации отключены настройкой системы':enabled?'Выключить анимации':'Включить анимации';
    const title=reduced.matches?'Учитывается системная настройка уменьшения движения':'Включить или выключить анимации';
    if(projectPage){projectAttr(button,'aria-label',label);projectAttr(button,'title',title);}
    else{button.setAttribute('aria-label',label);button.title=title;}
    document.querySelectorAll('svg').forEach(svg=>{if(enabled)svg.unpauseAnimations?.();else svg.pauseAnimations?.();});
    if(!enabled)document.getAnimations().forEach(animation=>animation.cancel());
    document.dispatchEvent(new CustomEvent('workspace:motion',{detail:{enabled}}));
  }
  root.dataset.theme=setting('theme')==='light'?'light':'dark';
  q('#themeToggle').onclick=()=>{root.dataset.theme=root.dataset.theme==='light'?'dark':'light';setting('theme',root.dataset.theme);};
  if(projectPage)projectAttr(q('#themeToggle'),'aria-label','Переключить тему');else q('#themeToggle').setAttribute('aria-label','Переключить тему');
  q('#motionToggle').onclick=()=>{preferredMotion=!preferredMotion;setting('motion',preferredMotion?'on':'off');syncMotion();};
  reduced.addEventListener('change',syncMotion);syncMotion();
  window.addEventListener('storage',event=>{if(event.key==='blatero.projects.theme')root.dataset.theme=setting('theme')==='light'?'light':'dark';if(event.key==='blatero.projects.motion'){preferredMotion=setting('motion')!=='off';syncMotion();}});

  function nav(current, project='') {
    shell.querySelectorAll('[data-space]').forEach(link=>{
      const key=link.dataset.space;
      if(key===current)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
      if(['daily','board','planning','materials','knowledge'].includes(key))link.href=href(key,project);
    });
    try {
      const last=JSON.parse(sessionStorage.getItem('blatero.lastMeeting')||'null');
      if(last?.session)shell.querySelector('[data-space=meeting]').href='/?'+new URLSearchParams({session:last.session});
    } catch { /* Navigation remains usable without storage. */ }
  }
  function mainSpace(){return q('#archOverlay')?.classList.contains('show')?'archive':q('#calendarOverlay')?.classList.contains('show')?'planning':'meeting';}
  function updateProjectRoute() {
    const search=new URLSearchParams(location.search),project=q('#projectFilter').value;
    if(project)search.set('project',project);else search.delete('project');
    if(view==='board')search.delete('view');else search.set('view',view);
    if(materialScope)search.set('material',materialScope);else search.delete('material');
    history.replaceState({},'',location.pathname+(search.size?'?'+search:'')+location.hash);
    nav(['daily','planning','materials','knowledge'].includes(view)?view:'board',project);
  }
  if(projectPage) {
    const originalFiltered=filtered;
    filtered=function(){const tasks=originalFiltered();if(!materialScope)return tasks;const ids=new Set((state.material_links||[]).filter(link=>link.material_id===materialScope).map(link=>link.work_item_id));return tasks.filter(task=>ids.has(task.id));};
    document.addEventListener('projects:render',()=>{
      if(!initialRoute){
        initialRoute=true;
        queueMicrotask(()=>{
        applyingRoute=true;
        const project=params.get('project');
        if(project && [...q('#projectFilter').options].some(option=>option.value===project)){q('#projectFilter').value=project;q('#projectFilter').dispatchEvent(new Event('change'));}
        const target=params.get('view');
        if(['daily','board','planning','materials','list','knowledge','recall','efficiency','closed','merge'].includes(target))q(`[data-view="${target}"]`)?.click();
        // Resolve the source directly: filtering must never silently swallow a deep link.
        const task=params.get('task');if(task)action(()=>openTask(task));
        if(materialScope)notice('Показаны только карточки выбранной встречи. Фильтр снимается выбором проекта.');
        applyingRoute=false;
        updateProjectRoute();
        });
        return;
      }
      updateProjectRoute();
    });
    q('#projectFilter').addEventListener('change',()=>{if(materialScope && !applyingRoute){materialScope='';render();}updateProjectRoute();});
    q('#taskDialog').addEventListener('close',()=>{const search=new URLSearchParams(location.search);search.delete('task');history.replaceState({},'',location.pathname+(search.size?'?'+search:''));});
    const railTools=document.createElement('div');railTools.className='space-task-visibility';
    railTools.innerHTML='<button id="showAllProjectTasks">Все задачи проекта</button><button id="showClosedProjectTasks">Показать закрытые</button><p>Снимает поиск и ограничение истории. Закрытие не удаляет карточку.</p>';
    window.BlateroProjectsI18n?.bindStatic(railTools);
    q('#projectNav').after(railTools);
    function revealTasks(closed) {
      materialScope='';q('#search').value='';q('#historyFilter').value='all';
      q(`[data-view="${closed?'closed':'list'}"]`).click();
    }
    q('#showAllProjectTasks').onclick=()=>revealTasks(false);
    q('#showClosedProjectTasks').onclick=()=>revealTasks(true);
    const sourceOpenTask=openTask;
    openTask=async function(id) {
      await sourceOpenTask(id);
      if(selected?.task?.id!==id)return;
      const task=selected.task;
      const section=document.createElement('section');section.className='detail-section';
      const meeting=document.createElement('a');meeting.className='space-primary';
      meeting.href='/?'+new URLSearchParams({quick_task:task.id});projectLabel(meeting,'Обсудить на новой встрече ↗');section.append(meeting);
      if(!filtered().some(item=>item.id===task.id)) {
        const note=document.createElement('p');note.className='quiet';
        projectLabel(note,task.status==='closed'?'Эта карточка закрыта и скрыта на обычной доске.':'Карточка не видна из-за выбранного проекта, поиска или фильтра истории.');
        const show=document.createElement('button');projectLabel(show,task.status==='closed'?'Показать в закрытых':'Показать в списке задач');
        show.onclick=()=>{q('#projectFilter').value=task.project_id||'';revealTasks(task.status==='closed');q('#taskDialog').close();};section.append(note,show);
      }
      q('#detail').prepend(section);
    };
    document.addEventListener('click',event=>{const button=event.target.closest('[data-open]');if(button){const search=new URLSearchParams(location.search);search.set('task',button.dataset.open);history.replaceState({},'',location.pathname+'?'+search);}});
    nav('board');
    return;
  }

  const strip=document.createElement('div');strip.className='meeting-project-strip';strip.innerHTML='<a id="meetingProjectLink" href="/projects">Проекты и задачи</a><span class="context-note" id="meetingProjectNote"></span><button id="meetingWorkButton">Задачи встречи</button>';
  q('#workflowNext').after(strip);
  const dialog=document.createElement('dialog');dialog.id='meetingWorkDialog';dialog.className='meeting-work-dialog';dialog.setAttribute('aria-labelledby','meetingWorkTitle');dialog.innerHTML='<div class="meeting-work-heading"><div><small>ВСТРЕЧА → РАБОТА</small><h2 id="meetingWorkTitle">Задачи встречи</h2></div><button aria-label="Закрыть" data-close-work>×</button></div><div id="meetingWorkContent"></div>';
  document.body.append(dialog);dialog.querySelector('[data-close-work]').onclick=()=>dialog.close();
  window.BlateroMeetingI18n?.bindStatic(strip);window.BlateroMeetingI18n?.bindStatic(dialog);
  async function loadContext(dir) {
    const version=++contextVersion;
    try {
      const next=await request('meeting-context?session='+encodeURIComponent(dir));
      if(version!==contextVersion || dir!==session)return;
      context=next;
      const link=q('#meetingProjectLink');link.href=href('board',next.project?.id);
      if(next.project?.name){window.BlateroMeetingI18n?.forget(link);link.textContent=next.project.name;}
      else meetingLabel(link,'Связать встречу с проектом');
      meetingLabel(q('#meetingProjectNote'),next.project_basis==='linked'?'по связанным задачам':next.project_basis==='workspace'?'предложение по рабочей папке':next.project_basis==='name'?'предложение по названию':'');
      meetingLabel(q('#meetingWorkButton'),'Задачи встречи · {count}',{count:next.tasks.length});
      nav(mainSpace(),next.project?.id);
    } catch(error){if(version===contextVersion)meetingLabel(q('#meetingProjectNote'),'Контекст задач недоступен');}
  }
  function workCard(task) {return `<a class="meeting-work-card" href="${safe(taskHref(task))}"><strong>${safe(task.title)} ↗</strong><span>${safe(statuses[task.status])} · ${safe(context.projects.find(project=>project.id===task.project_id)?.name||'Без проекта')}</span>${task.next_step?`<p>Далее: ${safe(task.next_step)}</p>`:''}</a>`;}
  async function openWork() {
    if(!session){notice('Сначала выберите встречу');return;}
    if(!dialog.open)dialog.showModal();
    q('#meetingWorkContent').textContent='Читаю задачи встречи…';
    try {
      await loadContext(session);
      if(!context || context.session!==session)throw Error('Не удалось прочитать контекст встречи');
      allTasks=(await request('state')).tasks;
      q('#meetingWorkTitle').textContent=context.title;
      q('#meetingWorkContent').innerHTML=`<p>Здесь показаны явные связи с этой встречей и подтверждёнными договорённостями. Новая карточка сохраняет снимок источника.</p><div id="meetingLinkedTasks">${context.tasks.map(workCard).join('')||'<p>Связанных задач пока нет.</p>'}</div><section class="meeting-work-section"><h3>Связать с работой</h3><label>Проект<select id="meetingWorkProject"><option value="">Выберите проект</option>${context.projects.map(project=>`<option value="${project.id}" ${context.project?.id===project.id?'selected':''}>${safe(project.name)}</option>`).join('')}</select></label><div class="meeting-work-actions"><button class="space-primary" id="meetingCreateCard">Создать карточку встречи</button><button id="meetingSyncSource">Обновить источник</button></div><label>Или существующая задача<select id="meetingExistingTask"></select></label><button id="meetingLinkTask">Связать с выбранной задачей</button><p id="meetingWorkStatus" role="status"></p></section><section class="meeting-work-section"><h3>Другие задачи этого проекта</h3><p>Они не привязаны к встрече автоматически.</p>${context.related_tasks.slice(0,12).map(workCard).join('')||'<p>Других задач для выбранного контекста нет.</p>'}</section>`;
      function taskOptions(){const project=q('#meetingWorkProject').value;q('#meetingExistingTask').innerHTML='<option value="">Выберите карточку</option>'+allTasks.filter(task=>task.status!=='done' && (!project||task.project_id===project)).map(task=>`<option value="${task.id}">${safe(task.title)}</option>`).join('');}
      q('#meetingWorkProject').onchange=taskOptions;taskOptions();
      async function mutate(button,mode){
        const dir=session,project=q('#meetingWorkProject').value,task=allTasks.find(item=>item.id===q('#meetingExistingTask').value);
        if(mode==='create'&&!project){notice('Выберите проект новой карточки');return;}
        if(mode==='link'&&!task){notice('Выберите существующую задачу');return;}
        button.disabled=true;
        try {
          const fresh=await request('meeting-sync',{session:dir});
          if(!fresh.material?.available)throw Error('Источник встречи пока недоступен');
          if(mode==='sync'){await openWork();notice('Снимок встречи обновлён');return;}
          const body={material_id:fresh.material.id,snapshot_sha256:fresh.material.snapshot_sha256};
          if(mode==='create')body.project_id=project;else{body.work_item_id=task.id;body.revision=task.revision;}
          const result=await request('materials/link',body);
          await openWork();notice('Связь сохранена. Карточка доступна на доске.');
          const link=document.createElement('a');link.className='meeting-work-card';link.href=taskHref(result.task);link.textContent='Открыть карточку «'+result.task.title+'» ↗';q('#meetingWorkStatus').append(link);
        } catch(error){q('#meetingWorkStatus').textContent=error.message;q('#meetingWorkStatus').className='workspace-error';}
        finally{button.disabled=false;}
      }
      q('#meetingCreateCard').onclick=event=>mutate(event.currentTarget,'create');q('#meetingSyncSource').onclick=event=>mutate(event.currentTarget,'sync');q('#meetingLinkTask').onclick=event=>mutate(event.currentTarget,'link');
    } catch(error){q('#meetingWorkContent').textContent=error.message;}
  }
  q('#meetingWorkButton').onclick=openWork;
  for(const id of ['archOverlay','calendarOverlay'])if(document.getElementById(id))new MutationObserver(()=>nav(mainSpace(),context?.project?.id)).observe(document.getElementById(id),{attributes:true,attributeFilter:['class']});
  document.addEventListener('blatero:meeting',event=>queueMicrotask(()=>{
    const info=event.detail;
    if(session!==info.current_dir){session=info.current_dir;context=null;if(dialog.open)dialog.close();}
    try{sessionStorage.setItem('blatero.lastMeeting',JSON.stringify({session}));}catch{}
    loadContext(session);
    const target=params.get('session');
    if(!initialRoute){
      initialRoute=true;
      if(target && target!==session){if(info.rec_running)notice('Идёт запись текущей встречи. Остановите её перед переходом к другой.');else send({type:'session',dir:target});return;}
    }
    if(!routePanelApplied && (!target || target===session)){
      routePanelApplied=true;
      const panel=params.get('panel');
      if(['archive','calendar','settings'].includes(panel))document.getElementById({archive:'archiveBtn',calendar:'calendarBtn',settings:'settingsBtn'}[panel])?.click();
      if(panel==='calendar' && /^\d{4}-\d{2}-\d{2}$/.test(params.get('date')||''))calendarRequest(params.get('date'),'day');
      if(panel==='tasks')openWork();
    }
    // A reload must return to the meeting just selected/created, not an old link.
    const currentRoute=new URLSearchParams(location.search);
    currentRoute.set('session',session);
    history.replaceState({},'',location.pathname+'?'+currentRoute+location.hash);
  }));
  setInterval(()=>{if(!document.hidden && session && !dialog.open)loadContext(session);},15000);
  const questions=q('#questions');
  if(questions)new MutationObserver(()=>{if(root.dataset.motion==='off')return;questions.querySelectorAll('.q').forEach((card,index)=>{card.style.animationDelay=Math.min(index,4)*55+'ms';card.classList.add('workspace-enter');});}).observe(questions,{childList:true});
  document.addEventListener('pointermove',event=>{if(root.dataset.motion==='off'||event.pointerType==='touch')return;const card=event.target.closest('#questions .q');if(!card)return;const rect=card.getBoundingClientRect();card.style.setProperty('--pointer-x',event.clientX-rect.left+'px');card.style.setProperty('--pointer-y',event.clientY-rect.top+'px');},{passive:true});
  const ambient=document.createElement('div');ambient.className='console-ambient';ambient.setAttribute('aria-hidden','true');const orbit=document.createElement('div');orbit.className='console-orbit';ambient.append(orbit);q('#hintzone').append(ambient);
  if(typeof currentInit!=='undefined' && currentInit)document.dispatchEvent(new CustomEvent('blatero:meeting',{detail:currentInit}));
  nav('meeting');
})();
