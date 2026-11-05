'use strict';
// Local form drafts never imply server persistence, acceptance or cloud submission.
const taskDrafts = new Map();
const taskExtraForms=['knowledgeForm','sourceForm','taskPlanForm','decisionRequestForm'];
const taskExtraDrafts=new Map();
function taskExtraKey(form){return 'blatero.taskDraft.'+form.dataset.taskId+'.'+form.id;}
function readTaskExtra(key){try{return taskExtraDrafts.get(key)||JSON.parse(sessionStorage.getItem(key)||'null');}catch{return taskExtraDrafts.get(key)||null;}}
function keepTaskExtra(form){
  if(!form?.dataset.taskId||!form.__extraBaseline)return;
  const values=Object.fromEntries(new FormData(form));
  const changes=Object.fromEntries(Object.entries(values).filter(([name,value])=>value!==form.__extraBaseline[name]));
  const key=taskExtraKey(form),old=readTaskExtra(key);
  for(const name of Object.keys(old?.values||{}))if(!Object.hasOwn(values,name))changes[name]=old.values[name];
  if(!Object.keys(changes).length){taskExtraDrafts.delete(key);try{sessionStorage.removeItem(key);}catch{}return;}
  const draft={revision:old?.revision??Number(form.dataset.taskRevision),values:changes};
  taskExtraDrafts.set(key,draft);try{sessionStorage.setItem(key,JSON.stringify(draft));}catch{}
}
function bindTaskExtra(form,task){
  if(!form||form.__extraBaseline)return;
  form.dataset.taskId=task.id;form.dataset.taskRevision=task.revision;
  form.__extraBaseline=Object.fromEntries(new FormData(form));
  const draft=readTaskExtra(taskExtraKey(form));
  if(!draft)return;
  for(const [name,value]of Object.entries(draft.values)){
    const field=form.elements.namedItem(name);
    if(field&&(field.tagName!=='SELECT'||[...field.options].some(option=>option.value===value)))field.value=value;
  }
  if(form.closest('details'))form.closest('details').open=true;
  const note=document.createElement('p');note.className='source-warning';
  projectLabel(note,draft.revision!==task.revision?'Восстановлен черновик. Карточка изменилась; проверьте поля перед сохранением.':'Восстановлен черновик из этой вкладки.');
  form.prepend(note);
}
function clearTaskExtra(form,submitted){
  if(!form?.dataset.taskId)return;
  const key=taskExtraKey(form),draft=readTaskExtra(key);
  if(draft&&Object.entries(draft.values).some(([name,value])=>String(submitted[name]??'')!==value))return;
  form.__extraBaseline=Object.fromEntries(new FormData(form));
  taskExtraDrafts.delete(key);try{sessionStorage.removeItem(key);}catch{}
}
for(const event of ['input','change'])document.addEventListener(event,e=>{
  const form=e.target.closest?.('form');if(taskExtraForms.includes(form?.id))keepTaskExtra(form);
});
function prepareTaskDraftForm(form){
  if(!form?.dataset.taskId)return '';
  if(!form.__draftBaseline){const initial=form.cloneNode(true);initial.reset();form.__draftBaseline=Object.fromEntries(new FormData(initial));form.__draftRevision=Number(form.dataset.taskRevision);}
  return form.dataset.taskId;
}
function readTaskDraft(id){try{return taskDrafts.get(id)||JSON.parse(sessionStorage.getItem('blatero.taskDraft.'+id)||'null');}catch{return taskDrafts.get(id)||null;}}
function keepTaskDraft(){
  const form=$('#editForm'),taskDraftOwner=prepareTaskDraftForm(form);if(!taskDraftOwner)return;
  if(form.elements.namedItem('title')?.disabled)return;
  const values=Object.fromEntries(new FormData(form));
  const baseline=form.__draftBaseline||{};
  const dirty=Object.fromEntries(Object.entries(values).filter(([k,v])=>v!==baseline[k]));
  if(!Object.keys(dirty).length){clearTaskDraft(taskDraftOwner);return;}
  const value={values:dirty,revision:form.__draftRevision};taskDrafts.set(taskDraftOwner,value);
  try{sessionStorage.setItem('blatero.taskDraft.'+taskDraftOwner,JSON.stringify(value));}catch{toast(projectUi('Не удалось сохранить черновик в этой вкладке'));}
}
function clearTaskDraft(id){taskDrafts.delete(id);try{sessionStorage.removeItem('blatero.taskDraft.'+id);}catch{}}
document.addEventListener('input',e=>{if(e.target.closest('#editForm'))keepTaskDraft();});
document.addEventListener('click',()=>keepTaskDraft(),true);
window.addEventListener('beforeunload',keepTaskDraft);
const taskDraftApi=api;
api=async function(path,body){
  const result=await taskDraftApi(path,body);
  if(path==='update'&&body?.work_item_id&&result.state==='applied'&&body.patch?.goal!==undefined){
    const form=$('#editForm');
    if(form&&prepareTaskDraftForm(form)===body.work_item_id){
      form.__draftBaseline={...form.__draftBaseline,...Object.fromEntries(Object.entries(body.patch).map(([k,v])=>[k,v==null?'':String(v)]))};
      form.__draftRevision=result.task?.revision;keepTaskDraft();
    }else{
      const draft=readTaskDraft(body.work_item_id);
      if(draft){for(const [k,v]of Object.entries(body.patch))if(draft.values[k]===String(v??''))delete draft.values[k];taskDrafts.set(body.work_item_id,draft);try{sessionStorage.setItem('blatero.taskDraft.'+body.work_item_id,JSON.stringify(draft));}catch{}}
    }
  }
  return result;
};
// Optional views share the existing task editor and revision/acceptance controls.
const materialKinds = {meeting:'Встреча', commitment:'Договорённость', article:'Статья'};
const materialStatuses = {scheduled:'Запланирована', recorded:'Есть запись', report:'Есть протокол', active:'Открыта', resolved:'Закрыта в источнике', draft:'Черновик', ready:'Готова', published:'Опубликована', idea:'Идея'};
let materialCatalog = null;
let planAnchor = new Date().toLocaleDateString('en-CA', {timeZone:'Europe/Moscow'});
let materialKind = '';

function materialActions(material) {
  if (material.kind !== 'article') return material.open_url ? `<a href="${esc(material.open_url)}">${projectText("Открыть встречу ↗")}</a>` : '';
  const edit = material.available && material.open_url && !material.source_error ?
    `<a class="material-edit" href="${esc(material.open_url)}" target="_blank" rel="noopener noreferrer">${projectText("Редактировать в Гранке ↗")}</a>` : '';
  const published = material.publication_url ?
    `<a class="material-publication" href="${esc(material.publication_url)}" target="_blank" rel="noopener noreferrer">${projectText("Читать публикацию ↗")}</a>` : '';
  return `<div class="material-links">${edit}${published}</div>`;
}

const baseProjectFiltered = filtered;
const generalTaskIds = ()=>new Set((state.triage || []).filter(x=>x.kind==='general').map(x=>x.work_item_id));
filtered = function() {
  const general = generalTaskIds();
  if ($('#projectFilter').value === '__general') {
    const query = $('#search').value.toLowerCase();
    return state.tasks.filter(t=>taskInView(t) && !t.project_id && general.has(t.id) && (!query || [t.title,t.goal,t.method,t.rationale,t.next_step,t.closed_reason].join(' ').toLowerCase().includes(query)));
  }
  return baseProjectFiltered().filter(t=>(view==='closed' && !$('#projectFilter').value) || t.project_id || !general.has(t.id));
};
const baseProjectNav = renderProjectNav;
renderProjectNav = function() {
  baseProjectNav();
  const general = generalTaskIds();
  const filter = $('#projectFilter');
  if (!filter.querySelector('option[value="__general"]')) filter.insertAdjacentHTML('beforeend',`<option value="__general" ${projectBind("Общие и личные вопросы")}>${projectUi("Общие и личные вопросы")}</option>`);
  const unbound = $('#projectNav').querySelector('[data-project="__unbound"]');
  projectValue(unbound.querySelector('.project-count'),state.tasks.filter(t=>taskInView(t) && !t.project_id && !general.has(t.id)).length);
  unbound.insertAdjacentHTML('afterend',`<button class="project-link" data-project="__general" ${filter.value==='__general'?'aria-current="page"':''}><span class="project-letter">·</span><span class="project-label">${projectText("Общие и личные вопросы")}</span><span class="project-count">${state.tasks.filter(t=>taskInView(t) && !t.project_id && general.has(t.id)).length}</span></button>`);
};
const baseProjectRefresh = refresh;
refresh = async function(force=false) {
  const general = $('#projectFilter').value==='__general';
  await baseProjectRefresh(force);
  if (general && $('#projectFilter').value!=='__general') { $('#projectFilter').value='__general';render(); }
  if (general) $('#projectInfo').hidden=true;
};
const baseProjectOverview = renderOverview;
renderOverview = function(tasks) {
  baseProjectOverview(tasks);
  const general=generalTaskIds();
  if ($('#projectFilter').value==='__general') { $('#projectInfo').hidden=true;projectLabel($('#projectDescription'),()=>({source:"Разовые и личные вопросы из истории. Источники сохранены; рабочий проект им не приписан.",values:{}})); }
  if (state.import_summary?.session_count) projectLabel($('#importBanner'),()=>({source:"Восстановлено по {p0} локальным сессиям. Исторические статусы предварительные. Нужно уточнить проект: {p1}; общих и личных вопросов: {p2}.",values:{p0:state.import_summary.session_count,p1:state.tasks.filter(t=>taskInView(t) && !t.project_id && !general.has(t.id)).length,p2:state.tasks.filter(t=>taskInView(t) && !t.project_id && general.has(t.id)).length}}));
};

const baseProjectRender = render;
render = function() {
  if ($('#projectFilter').value==='__general' && ['planning','materials','efficiency'].includes(view)) {
    renderOverview(filtered());generation++;
    $('#content').innerHTML=`<div class="welcome"><h2>${projectText("Здесь собраны общие и личные вопросы")}</h2><p class="quiet">${projectText("Откройте доску или список, чтобы прочитать историю. Для планирования рабочих задач выберите проект.")}</p></div>`;
    return;
  }
  if (view !== 'materials' && view !== 'planning') return baseProjectRender();
  renderOverview(filtered());
  generation++;
  const current = generation;
  $('#content').innerHTML = `<p class="quiet">${projectText("Загружаю локальный план…")}</p>`;
  action(async () => {
    if (view === 'materials') await renderMaterials(current);
    else await renderPlanning(current);
  });
};

const baseProjectCard = card;
card = function(task) {
  const tags = [...new Set((state.material_links || []).filter(l=>l.work_item_id===task.id).map(l=>l.material_id.split(':')[0]))];
  const badges = tags.map(kind=>`<span class="tag">${(materialKinds[kind]?projectText(materialKinds[kind]):esc(kind))}</span>`).join('');
  const slot = task.planned_start ? `<p>${projectText("В плане:")} ${projectTime(task.planned_start)} · ${task.estimate_minutes || 30} ${projectText("мин")}</p>` : '';
  return baseProjectCard(task).replace('<div class="card-foot">', `${badges}${slot}<div class="card-foot">`);
};

function materialProjectOptions(value) {
  return `<option value="" ${projectBind("Выберите проект")}>${projectUi("Выберите проект")}</option>`+state.projects.map(p=>`<option value="${p.id}" ${value===p.id?'selected':''}>${esc(p.name)}</option>`).join('');
}

async function renderMaterials(current, force=false) {
  materialCatalog = await api(force ? 'materials/refresh' : 'materials', force ? {} : undefined);
  if (current !== generation || view !== 'materials') return;
  const project = $('#projectFilter').value;
  const query = $('#search').value.toLowerCase();
  const entries = materialCatalog.entries.filter(m=>(!materialKind || m.kind===materialKind)
    && (!query || [m.title,m.summary,m.scope_label].join(' ').toLowerCase().includes(query))
    && (!project || (project==='__unbound' ? !m.links.length : m.links.some(l=>state.tasks.some(t=>t.id===l.work_item_id && t.project_id===project)))));
  const defaultProject = state.projects.some(p=>p.id===project) ? project : '';
  $('#content').innerHTML = `<div class="integration-toolbar"><button id="refreshMaterials">${projectText("Обновить источники")}</button><label>${projectText("Вид")} <select id="materialKind"><option value="" ${projectBind("Все материалы")}>${projectUi("Все материалы")}</option>${Object.entries(materialKinds).map(([k,v])=>`<option value="${k}" ${materialKind===k?'selected':''} ${projectBind(v)}>${esc(projectUi(v))}</option>`).join('')}</select></label><span class="quiet">${projectText("Материалов: {count} ·",{count:entries.length})} ${materialCatalog.observed_at ? projectText("обновлено ")+projectTime(materialCatalog.observed_at) : projectText("источники ещё не прочитаны")}</span></div>
    <p class="quiet">${projectText("Встречи, договорённости и статьи остаются в своих приложениях. Связь сохраняет снимок источника; обновление не меняет ваши решения и статус карточки.")}</p>
    ${materialCatalog.errors.map(e=>`<p class="source-warning">${esc(e)}</p>`).join('')}
    <div class="material-grid">${entries.slice(0,200).map(m=>`<article class="material" data-material="${esc(m.id)}"><span class="tag">${projectText(materialKinds[m.kind])}</span><span class="tag">${(materialStatuses[m.source_status]?projectText(materialStatuses[m.source_status]):esc(m.source_status))}</span><h3>${esc(m.title)}</h3>
      ${m.date?`<p>${projectText(m.kind==='article'?'Публикация':'Дата')}: ${esc(m.date)}${m.start?' · '+projectTime(new Date(m.start),{hour:'2-digit',minute:'2-digit'}):''}</p>`:''}
      ${m.scope_label?`<p class="quiet">${esc(m.scope_label)}${m.owner?' · '+esc(m.owner):''}</p>`:''}
      ${m.kind==='article' && Number.isFinite(m.readiness?.percent)?`<label>${projectText("Готовность в Гранке:")} ${m.readiness.percent}%<progress max="100" value="${m.readiness.percent}"></progress></label>`:''}
      ${m.summary?`<details><summary>${m.kind==='meeting'?projectText("Протокол"):projectText("Содержание")}</summary><p class="material-preview">${esc(m.summary)}</p></details>`:''}
      <p class="meta">${esc(m.locator)}</p>
      ${!m.available?`<p class="source-warning">${projectText("Источник больше не найден. Снимок и связи сохранены.")}</p>`:''}
      ${m.connection_disabled?`<p class="quiet">${projectText("Подключение выключено. Снимок и связи сохранены.")}</p>`:''}
      ${m.source_error?`<p class="source-warning">${esc(m.source_error)}</p>`:''}
      ${m.links.map(l=>`<div class="entry"><button data-open="${l.work_item_id}">${(state.tasks.find(t=>t.id===l.work_item_id)?.title?esc(state.tasks.find(t=>t.id===l.work_item_id)?.title):projectText("Открыть связанную задачу"))}</button>${l.changed?`<p class="source-warning">${projectText("Источник обновился после привязки. Сверьте новое содержание.")}</p>`:''}</div>`).join('')}
      ${materialActions(m)}
      ${m.available&&!m.connection_disabled?`<label>${projectText("Создать задачу в проекте")}<select class="material-project">${materialProjectOptions(defaultProject)}</select></label><button data-create-material="${esc(m.id)}">${projectText("Создать карточку")}</button><label>${projectText("Или связать с задачей")}<select class="material-task"><option value="" ${projectBind("Выберите карточку")}>${projectUi("Выберите карточку")}</option>${state.tasks.filter(t=>!['done','closed'].includes(t.status) && (!defaultProject || t.project_id===defaultProject)).map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join('')}</select></label><button data-link-material="${esc(m.id)}">${projectText("Связать с карточкой")}</button>`:''}
      </article>`).join('')}</div>${!entries.length?`<div class="welcome"><h2>${projectText("Материалов в этом представлении нет")}</h2><p class="quiet">${projectText("Обновите источники или выберите все проекты. Привязанные материалы появятся в своём проекте.")}</p></div>`:''}${entries.length>200?`<p class="quiet">${projectText("Показаны первые 200. Используйте поиск или фильтр вида.")}</p>`:''}`;
}

function clockLabel(item) {
  if (item.all_day || !item.start) return item.kind==='due' ? projectUi("Срок задачи") : projectUi("На этот день");
  const fmt={hour:'2-digit',minute:'2-digit',timeZone:'Europe/Moscow'};
  return new Date(item.start).toLocaleTimeString('ru-RU',fmt)+'–'+new Date(item.end).toLocaleTimeString('ru-RU',fmt);
}

async function renderPlanning(current) {
  const project = $('#projectFilter').value;
  const plan = await api('planning?anchor='+encodeURIComponent(planAnchor)+(project && project!=='__unbound'?'&project_id='+project:''));
  if (current !== generation || view !== 'planning') return;
  planAnchor = plan.anchor;
  const visible = new Set(filtered().map(t=>t.id));
  const items = plan.items.filter(item=>!item.task_id || visible.has(item.task_id));
  const conflicting = new Set(plan.conflicts.flatMap(c=>[c.left,c.right]));
  const days = Array.from({length:7},(_,i)=>{const day=new Date(plan.anchor+'T12:00:00+03:00');day.setUTCDate(day.getUTCDate()+i);return day.toISOString().slice(0,10);});
  $('#content').innerHTML = `<div class="integration-toolbar"><button data-plan-shift="-7" ${projectAttrs("aria-label","Предыдущая неделя")}>←</button><label>${projectText("Неделя")} <input id="planDate" type="date" value="${plan.anchor}"></label><button data-plan-shift="7" ${projectAttrs("aria-label","Следующая неделя")}>→</button><button id="planToday">${projectText("Сегодня")}</button><span class="quiet">${projectText("Время: Москва · встречи и задачи")}</span></div>
    <p class="quiet">${projectText("Назначьте начало и длительность в карточке. Срок задачи и дата публикации показаны отдельно. Внешние календари читаются из последнего снимка Blatero.")}</p>
    ${plan.errors.map(e=>`<p class="source-warning">${esc(e)}</p>`).join('')}
    ${plan.conflicts.length?`<div class="planning-conflicts"><b>${projectText("Пересечения в плане:")} ${plan.conflicts.length}</b>${plan.conflicts.slice(0,12).map(c=>`<p>${c.titles.map(esc).join(' ↔ ')}</p>`).join('')}</div>`:''}
    <div class="week-grid">${days.map(day=>`<section class="plan-day"><h3>${projectTime(new Date(day+'T12:00:00+03:00'),{weekday:'short',day:'numeric',month:'short'})}</h3>${items.filter(x=>x.date===day).sort((a,b)=>(a.start||'').localeCompare(b.start||'')).map(item=>`<${item.task_id?'button':'div'} class="plan-item ${esc(item.kind)} ${conflicting.has(item.id)?'conflict':''}" ${item.task_id?`data-open="${item.task_id}"`:''}><small>${projectClockLabel(item)} · ${(materialKinds[item.kind]?projectText(materialKinds[item.kind]):item.kind==='task'?projectText("Задача"):item.kind==='due'?projectText("Срок"):projectText("Календарь"))}</small>${esc(item.title)}</${item.task_id?'button':'div'}>${item.kind==='meeting'&&item.open_url?`<a class="plan-source" href="${esc(item.open_url)}">${projectText("К встрече ↗")}</a>`:''}`).join('') || `<p class="quiet">${projectText("Есть место в плане")}</p>`}</section>`).join('')}</div>
    <section class="detail-section"><h3>${projectText("Назначить время")}</h3><div class="knowledge-grid">${plan.unscheduled.filter(t=>visible.has(t.id)).slice(0,24).map(t=>`<article class="knowledge-block"><button data-open="${t.id}">${esc(t.title)}</button><p class="quiet">${projectNameText(t.project_id)}</p><small>${t.due?projectText("Срок: ")+esc(t.due):projectText("Срок ещё не задан")}</small></article>`).join('')}</div></section>`;
}

const baseOpenProjectTask = openTask;
openTask = async function(id) {
  const previousTaskId=selected?.task?.id;
  const opening=baseOpenProjectTask(id),ticket=taskOpenEpoch;
  await opening;
  if (ticket!==taskOpenEpoch||selected?.task.id !== id) return;
  if (selected.task.merged_into) return;
  const task = selected.task;
  for(const id of ['knowledgeForm','sourceForm'])bindTaskExtra($('#'+id),task);
  if (previousTaskId!==id) $('#taskDialog').scrollTop=0;
  const triage = (state.triage || []).find(x=>x.work_item_id===id);
  if (triage) $('#detail').insertAdjacentHTML('afterbegin',`<div class="import-note">${triage.kind==='general'?projectText("Общий или личный вопрос"):projectText("Нужен дополнительный контекст")}: ${esc(triage.reason)}</div>`);
  const local = task.planned_start ? new Date(Date.parse(task.planned_start)-new Date(task.planned_start).getTimezoneOffset()*60000).toISOString().slice(0,16) : '';
  $('#detail').insertAdjacentHTML('beforeend', `<section class="detail-section"><h3>${projectText("Место в плане")}</h3><form id="taskPlanForm"><div class="grid2"><label>${projectText("Начало работы")}<input name="planned_start" type="datetime-local" value="${local}"></label><label>${projectText("Длительность, минут")}<input name="estimate_minutes" type="number" min="1" max="1440" value="${task.estimate_minutes || ''}" placeholder="30"></label></div><p class="quiet">${projectText("Время ввода — часовой пояс вашего компьютера. Пустое начало снимает задачу с расписания.")}</p><button>${projectText("Сохранить план")}</button></form></section><section class="detail-section integration-detail" id="taskMaterials"><h3>${projectText("Встречи и статьи")}</h3><p class="quiet">${projectText("Читаю связи…")}</p></section>`);
  bindTaskExtra($('#taskPlanForm'),task);
  $('#taskPlanForm').onsubmit = e=>{e.preventDefault();const form=e.target,values=Object.fromEntries(new FormData(form));action(async()=>{
    await api('update',{work_item_id:task.id,revision:task.revision,patch:{planned_start:values.planned_start?new Date(values.planned_start).toISOString():null,estimate_minutes:values.estimate_minutes?Number(values.estimate_minutes):null}});
    clearTaskExtra(form,values);await refresh(true);if(ticket===taskOpenEpoch)await openTask(task.id);
  });};
  const snapshot=await api('materials');
  if (ticket!==taskOpenEpoch||selected?.task.id!==id || selected.task.revision!==task.revision) return;
  const linked=snapshot.entries.filter(m=>m.links.some(l=>l.work_item_id===id));
  $('#taskArticleActions')?.remove();
  const articles = linked.filter(m=>m.kind==='article');
  if (articles.length) {
    const shortcuts=document.createElement('section');shortcuts.id='taskArticleActions';shortcuts.className='task-article-actions';
    shortcuts.innerHTML=`<h3>${projectText("Статьи задачи")}</h3>`+articles.map(m=>`<div><b>${esc(m.title)}</b>${materialActions(m)}</div>`).join('');
    $('#editForm').before(shortcuts);
  }
  const candidates=snapshot.entries.filter(m=>m.kind==='article' && m.available && m.open_url && !m.source_error && !articles.some(a=>a.id===m.id));
  $('#taskMaterials').innerHTML=`<h3>${projectText("Встречи и статьи")}</h3>`+linked.map(m=>`<div class="entry"><b>${esc(m.title)}</b><p>${projectText(materialKinds[m.kind])} · ${(materialStatuses[m.source_status]?projectText(materialStatuses[m.source_status]):esc(m.source_status))}${m.date?' · '+esc(m.date):''}</p>${m.links.find(l=>l.work_item_id===id).changed?`<p class="source-warning">${projectText("Источник изменился. Первоначальное основание сохранено.")}</p>`:''}${!m.available?`<p class="source-warning">${projectText("Источник сейчас недоступен.")}</p>`:''}<p class="meta">${esc(m.locator)}</p>${materialActions(m)}${m.summary?`<details><summary>${projectText("Содержание источника")}</summary><p class="material-preview">${esc(m.summary)}</p></details>`:''}<button data-unlink-material="${esc(m.id)}">${projectText("Снять связь")}</button></div>`).join('')+
    `<details class="task-article-link"><summary>${projectText("Связать статью с задачей")}</summary>${candidates.length?`<label>${projectText("Статья в Гранке")}<select id="taskArticleSource"><option value="" ${projectBind("Выберите статью")}>${projectUi("Выберите статью")}</option>${candidates.map(m=>`<option value="${esc(m.id)}">${esc(m.title)}</option>`).join('')}</select></label><button id="linkTaskArticle" type="button">${projectText("Связать статью")}</button>`:`<p class="quiet">${projectText("Нет новых доступных исходников. Добавьте статью в библиотеку Гранки и обновите источники во вкладке «Материалы».")}</p>`}</details>`;
  $('#linkTaskArticle')?.addEventListener('click',()=>action(async()=>{
    const material=candidates.find(m=>m.id===$('#taskArticleSource').value);
    if (!material) throw Error(projectUi("Выберите статью"));
    if ([...new FormData($('#editForm'))].some(([key,value])=>value!==String(task[key]??''))) {
      throw Error(projectUi("Сначала сохраните изменения карточки, затем свяжите статью"));
    }
    await api('materials/link',{material_id:material.id,snapshot_sha256:material.snapshot_sha256,work_item_id:task.id,revision:task.revision});
    await refresh(true);await openTask(task.id);
    $('#taskDialog').scrollTop=0;
  }));
};

document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.id==='refreshMaterials')action(()=>renderMaterials(++generation,true));
  if(b.dataset.createMaterial || b.dataset.linkMaterial)action(async()=>{
    const article=b.closest('[data-material]'), material=materialCatalog.entries.find(m=>m.id===article.dataset.material);
    const body={material_id:material.id,snapshot_sha256:material.snapshot_sha256};
    if(b.dataset.createMaterial){body.project_id=article.querySelector('.material-project').value;if(!body.project_id)throw Error(projectUi("Выберите проект новой карточки"));}
    else {body.work_item_id=article.querySelector('.material-task').value;const task=state.tasks.find(t=>t.id===body.work_item_id);if(!task)throw Error(projectUi("Выберите задачу"));body.revision=task.revision;}
    const result=await api('materials/link',body);await refresh(true);await openTask(result.task.id);
  });
  if(b.dataset.unlinkMaterial)action(async()=>{const task=selected.task;await api('materials/unlink',{material_id:b.dataset.unlinkMaterial,work_item_id:task.id,revision:task.revision});await refresh(true);await openTask(task.id);});
  if(b.dataset.planShift){const day=new Date(planAnchor+'T12:00:00+03:00');day.setUTCDate(day.getUTCDate()+Number(b.dataset.planShift));planAnchor=day.toISOString().slice(0,10);render();}
  if(b.id==='planToday'){planAnchor=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Moscow'});render();}
});
document.addEventListener('change',e=>{
  if(e.target.id==='materialKind'){materialKind=e.target.value;render();}
  if(e.target.id==='planDate'){planAnchor=e.target.value;render();}
});

const taskDraftOpen=openTask;
openTask=async function(id){
  keepTaskDraft();const opening=taskDraftOpen(id),ticket=taskOpenEpoch;await opening;
  if(ticket!==taskOpenEpoch)return;
  const form=$('#editForm');if(!form||selected?.task.id!==id||prepareTaskDraftForm(form)!==id)return;
  const draft=readTaskDraft(id);
  if(draft){
    for(const [name,value] of Object.entries(draft.values||{})){const field=form.elements.namedItem(name);if(field&&!field.disabled)field.value=value;}
    const note=document.createElement('p');note.className='source-warning';note.dataset.taskDraft='';
    projectLabel(note,draft.revision!==selected.task.revision?'Восстановлен черновик. Карточка изменилась; проверьте поля перед сохранением.':'Восстановлен черновик из этой вкладки.');
    const reset=document.createElement('button');reset.type='button';projectLabel(reset,'Сбросить черновик');
    reset.onclick=()=>{if(!confirm(projectUi('Удалить несохранённый черновик?')))return;for(const [name,value]of Object.entries(form.__draftBaseline)){const field=form.elements.namedItem(name);if(field)field.value=value;}clearTaskDraft(id);note.remove();};
    note.append(' ',reset);form.prepend(note);
  }
  installHistoryPages(id);
};

function installHistoryPages(id){
  $('#taskHistoryPages')?.remove();
  const labels={sources:'Источники',events:'События',knowledge:'Знания',checks:'Проверки',sessions:'Сессии',recalls:'Повторения'};
  const box=document.createElement('details');box.id='taskHistoryPages';box.className='detail-section';
  box.innerHTML=`<summary>${projectText('Вся история карточки')}</summary><label>${projectText('Раздел истории')}<select>${Object.entries(labels).map(([k,v])=>`<option value="${k}">${projectText(v)}</option>`).join('')}</select></label><p role="status"></p><div class="history-page-items"></div><button type="button">${projectText('Показать ещё')}</button>`;
  $('#detail').append(box);
  const select=box.querySelector('select'),status=box.querySelector('p'),list=box.querySelector('.history-page-items'),more=box.querySelector('button');
  let cursor=null,count=0,loading=false,owner=0;
  async function load(reset){
    if(loading&&!reset)return;
    const ticket=++owner,section=select.value;if(reset){cursor=null;count=0;list.replaceChildren();}
    loading=true;more.disabled=true;
    try{
      const q=new URLSearchParams({section});if(cursor)q.set('cursor',cursor);
      const page=await api('tasks/'+id+'/history?'+q);
      if(ticket!==owner||selected?.task.id!==id||!box.isConnected)return;
      for(const row of page.items){const node=document.createElement('article');node.className='entry';const title=document.createElement('b');title.textContent=row.label||row.text||row.event_type||row.name||row.kind||row.id;const body=document.createElement('pre');body.style.whiteSpace='pre-wrap';body.style.overflowWrap='anywhere';body.textContent=row.locator||row.text||JSON.stringify(row.payload||row,null,2);node.append(title,body);list.append(node);}
      count+=page.items.length;cursor=page.next_cursor;more.hidden=!page.has_more;projectLabel(status,'Показано {count} из {total}',{count,total:page.total});
    }catch(error){if(ticket===owner)status.textContent=error.message;}
    finally{if(ticket===owner){loading=false;more.disabled=false;}}
  }
  select.onchange=()=>load(true);more.onclick=()=>load(false);box.ontoggle=()=>{if(box.open&&!count&&!loading)load(true);};
}

let passportBusy=false;
async function installProjectPassport(){
  const dialog=$('#projectInfoDialog'),id=$('#projectFilter').value;
  if(!dialog?.open||!id||$('#projectPassportForm')||passportBusy)return;
  passportBusy=true;
  try{
    const data=await api('projects/'+id),p=data.project;
    if(!dialog.open||$('#projectFilter').value!==id||$('#projectPassportForm'))return;
    const form=document.createElement('form');form.id='projectPassportForm';form.className='detail-section';
    form.innerHTML=`<h3>${projectText('Паспорт проекта')}</h3><label>${projectText('Название')}<input name="name" required maxlength="160"></label><label>${projectText('Описание')}<textarea name="description" maxlength="8000" rows="3"></textarea></label><label>${projectText('Рабочая папка')}<input name="workspace"></label><p>${projectText('Файлы и записи не перемещаются. Меняется путь проекта; его ID, задачи и история сохраняются.')}</p><p role="status"></p><button class="primary">${projectText('Проверить и сохранить проект')}</button>`;
    for(const key of ['name','description','workspace'])form.elements[key].value=p[key]||'';
    const original=JSON.stringify(Object.fromEntries(new FormData(form)));
    const dirty=()=>form.isConnected&&!form.__saved&&JSON.stringify(Object.fromEntries(new FormData(form)))!==original;
    dialog.__passportDirty=dirty;
    if(!dialog.__passportGuard){const close=dialog.close.bind(dialog);dialog.close=()=>{if(dialog.__passportDirty?.()&&!confirm(projectUi('Отменить изменения проекта?')))return;close();};dialog.addEventListener('cancel',e=>{e.preventDefault();dialog.close();});dialog.__passportGuard=true;}
    form.onsubmit=e=>{e.preventDefault();action(async()=>{const button=form.querySelector('button');button.disabled=true;try{const body={...Object.fromEntries(new FormData(form)),project_id:id,revision:p.revision};const preview=await api('project-preview',body);projectLabel(form.querySelector('[role=status]'),'Задач: {tasks} · документов: {documents}. Файлы не перемещаются.',preview);if(!confirm(projectUi('Сохранить изменения проекта?')+'\n'+preview.before.workspace+' → '+preview.project.workspace))return;await api('project-update',{...body,confirmation:preview.confirmation});form.__saved=true;await refresh(true);dialog.close();toast(projectUi('Проект сохранён'));}finally{button.disabled=false;}});};
    $('#projectInfoContent').append(form);
    if(data.history?.length){const history=document.createElement('details');const title=document.createElement('summary');projectLabel(title,'Изменения проекта');history.append(title);for(const entry of data.history){const row=document.createElement('p');row.textContent=entry.at+' · '+entry.after.name+' · '+entry.before.workspace+' → '+entry.after.workspace;history.append(row);}form.append(history);}
  }finally{passportBusy=false;}
}
new MutationObserver(()=>{installProjectPassport().catch(e=>toast(e.message));}).observe($('#projectInfoDialog'),{attributes:true,childList:true,subtree:true});
window.addEventListener('beforeunload',e=>{if($('#projectInfoDialog')?.open&&$('#projectInfoDialog').__passportDirty?.()){e.preventDefault();e.returnValue='';}});
