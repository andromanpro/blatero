'use strict';
// Daily projections never move cards or accept an agent's result implicitly.
let dailySnapshot = null, dailySignature = '';
const dailyBaseRender = render;
render = function() {
  document.body.classList.toggle('daily-view', view==='daily');
  if (view!=='daily') { dailySignature='';return dailyBaseRender(); }
  renderOverview(filtered());generation++;
  const current=generation, project=$('#projectFilter').value;
  if(!$('#dailyScreen'))$('#content').innerHTML=`<p class="quiet">${projectText("Собираю сегодняшний день…")}</p>`;
  action(async()=>{
    const data=await api('daily'+(project?'?project_id='+encodeURIComponent(project):''));
    if(current!==generation || view!=='daily')return;
    dailySnapshot=data;
    const signature=JSON.stringify(data)+JSON.stringify(state.tasks.map(t=>[t.id,t.revision]));
    if(signature===dailySignature && $('#dailyScreen'))return;
    if($('#dailyScreen')?.contains(document.activeElement) && document.activeElement.matches('input,select,textarea'))return;
    dailySignature=signature;
    renderDaily(data);
  });
};
function dailyTaskLabel(t) {return `<span class="daily-meta">${projectNameText(t.project_id)} · ${projectText(labels[t.status])}${t.origin==='history'?projectText(" · из истории, требует сверки"):''}</span>`;}
function dailySmallTask(t) {return `<article class="daily-row">${dailyTaskLabel(t)}<button data-open="${t.id}">${esc(t.title)} <span aria-hidden="true">↗</span></button>${t.next_step?`<p>${esc(t.next_step)}</p>`:''}</article>`;}
function dailyAnsweredGroup(rows, showTask=false) {
  const answers=(rows||[]).filter(r=>['answered','resolved'].includes(r.state));
  return `<details class="daily-answered-group"><summary>${projectText("Отвеченные ·")} ${answers.length}</summary>${answers.map(r=>`<article class="daily-answer-history">${showTask&&r.task?`<button data-open="${esc(r.task.id)}">${esc(r.task.title)} ↗</button>`:''}<p><b>${projectText("Вопрос:")}</b> ${esc(r.question)}</p><p><b>${projectText("Ответ:")}</b> ${esc(r.answer)}</p><small>${projectTime(r.resolved_at)} · ${r.origin?projectText("Записан агентом из чата"):projectText("Сохранён в интерфейсе")}</small>${r.origin?`<details><summary>${projectText("Источник ответа")}</summary><p><b>${projectText("Исходная цитата:")}</b> ${esc(r.origin.quote)}</p><p>${projectText("Чат Codex ·")} <code>${esc(r.origin.session_id)}</code></p><p class="quiet">${esc(r.origin.locator)}</p></details>`:''}</article>`).join('')||`<p class="quiet">${projectText("Отвеченных вопросов пока нет.")}</p>`}</details>`;
}
function renderDaily(data) {
  const focus=data.focus, task=focus.task, current=task&&!focus.inactive;
  const project=$('#projectFilter').value;
  const general=generalTaskIds();
  const choices=state.tasks.filter(t=>!['done','closed'].includes(t.status) && (!project||t.project_id===project||(project==='__unbound'&&!t.project_id&&!general.has(t.id))||(project==='__general'&&!t.project_id&&general.has(t.id))));
  if(current && !choices.some(t=>t.id===task.id))choices.unshift(task);
  choices.sort((a,b)=>(a.status!=='active')-(b.status!=='active')||a.title.localeCompare(b.title,'ru'));
  $('#content').innerHTML=`<div id="dailyScreen">
    <div class="daily-date"><span>${projectTime(new Date(data.date+'T12:00:00+03:00'),{weekday:'long',day:'numeric',month:'long'})} ${projectText("/ МСК")}</span><span class="daily-signal"><i aria-hidden="true"></i>${projectText("КОНТЕКСТ НА СВЯЗИ")}</span></div>
    <div class="daily-grid">
      <section class="daily-panel daily-focus" aria-labelledby="dailyFocusTitle"><div class="daily-section-label"><span>${projectText("01 / ФОКУС")}</span><span>${projectText("ОДНА ЗАДАЧА")}</span></div>
        <h3 id="dailyFocusTitle">${current?esc(task.title):projectText("Выбери, с чего продолжить")}</h3>
        ${current?`${dailyTaskLabel(task)}<p class="daily-goal">${(task.goal?esc(task.goal):projectText("Суть ещё не записана. Дополните карточку."))}</p><div class="daily-next"><span>${projectText("СЛЕДУЮЩИЙ ШАГ")}</span><p>${(task.next_step?esc(task.next_step):projectText("Определите следующий шаг в карточке."))}</p></div><div class="daily-actions"><button class="primary" data-open="${task.id}">${projectText("Продолжить задачу ↗")}</button><button data-recall="${task.id}">${projectText("Вспомнить метод")}</button></div><details class="daily-method"><summary>${projectText("Метод и причина выбора")}</summary><p><b>${projectText("Метод:")}</b> ${(task.method?esc(task.method):projectText("Ещё не выбран"))}</p><p><b>${projectText("Почему:")}</b> ${(task.rationale?esc(task.rationale):projectText("Ещё не записано"))}</p></details>`:`<p class="quiet">${focus.inactive?projectText("Предыдущая задача завершена или связана с другой карточкой. Выберите новый фокус."):projectText("Один явный выбор поможет вернуться к сути после переключения.")}</p>`}
        <details class="daily-focus-picker" ${current?'':'open'}><summary>${current?projectText("Сменить текущую задачу"):projectText("Выбрать текущую задачу")}</summary><form id="dailyFocusForm"><label for="dailyFocusSelect">${projectText("Текущая задача")}</label><div class="daily-select-row"><select id="dailyFocusSelect" required><option value="" ${projectBind("Выберите задачу")}>${projectUi("Выберите задачу")}</option>${choices.map(t=>`<option value="${t.id}" ${current&&task.id===t.id?'selected':''}>${esc(projectName(t.project_id)+' / '+t.title)}</option>`).join('')}</select><button>${projectText("Сохранить фокус")}</button></div></form><div class="daily-actions"><button data-new-task>${projectText("Новая задача")}</button>${focus.work_item_id?`<button class="daily-text-button" id="dailyClearFocus">${projectText("Снять фокус")}</button>`:''}</div></details><p class="daily-footnote">${projectText("Фокус общий для всего пространства. Выбор сохраняется в базе и не меняет статус карточки.")}</p>
      </section>
      <section class="daily-panel daily-attention" aria-labelledby="dailyAttentionTitle"><div class="daily-section-label"><span>${projectText("02 / ТВОЁ РЕШЕНИЕ")}</span><span>${data.attention_count}</span></div><h3 id="dailyAttentionTitle">${projectText("Ждут твоего ответа")}</h3>
        <div class="daily-questions">${data.attention.map(r=>`<article class="daily-question">${dailyTaskLabel(r.task)}<h4>${esc(r.question)}</h4><p class="daily-question-task">${esc(r.task.title)}</p>${r.recommendation?`<details><summary>${projectText("Рекомендация агента")}</summary><p>${esc(r.recommendation)}</p></details>`:''}${r.changed?`<p class="source-warning">${projectText("Контекст изменился после вопроса. Сверьте актуальную карточку.")}</p>`:''}<button data-open="${r.task.id}">${projectText("Ответить в карточке ↗")}</button></article>`).join('')||`<div class="daily-empty"><span aria-hidden="true">◇</span><p>${projectText("Открытых вопросов нет.")}</p><small>${projectText("Агент может оставить вопрос и рекомендацию в карточке.")}</small></div>`}</div>
        ${data.attention_count>3?`<p class="quiet">${projectText("Показаны 3 из")} ${data.attention_count}${projectText(". После ответа появится следующий вопрос.")} <button id="dailyAllQuestions">${projectText("Все вопросы")}</button></p>`:''}
        ${dailyAnsweredGroup(data.answered,true)}
        <details class="daily-reviews"><summary>${projectText("Результаты на проверке ·")} ${data.review_count}</summary><p class="quiet">${projectText("Это готовность к проверке. Приёмка результата — отдельное действие.")}</p>${data.reviews.map(dailySmallTask).join('')||`<p>${projectText("Новых результатов на проверке нет.")}</p>`}${data.review_count>3?`<button data-view="list">${projectText("Открыть список задач")}</button>`:''}</details>
      </section>
      <section class="daily-panel daily-plan" aria-labelledby="dailyPlanTitle"><div class="daily-section-label"><span>${projectText("03 / БЛИЖАЙШЕЕ")}</span><span>${projectText("7 ДНЕЙ")}</span></div><h3 id="dailyPlanTitle">${projectText("Место для важного")}</h3>
        <div class="daily-timeline">${data.plan.map(item=>`<article class="daily-slot"><time>${projectTime(new Date(item.date+'T12:00:00+03:00'),{day:'numeric',month:'short'})}<b>${projectClockLabel(item)}</b></time><div><span class="daily-meta">${(materialKinds[item.kind]?projectText(materialKinds[item.kind]):item.kind==='due'?projectText("Срок задачи"):item.kind==='calendar'?projectText("Личный календарь"):projectText("Задача"))}</span>${item.task_id?`<button data-open="${item.task_id}">${esc(item.title)} ↗</button>`:`<strong>${esc(item.title)}</strong>`}${item.open_url&&item.kind==='meeting'?`<a href="${esc(item.open_url)}">${projectText("К встрече ↗")}</a>`:''}</div></article>`).join('')||`<p class="quiet">${projectText("Ближайшее время свободно. Назначьте начало работы в карточке или добавьте встречу.")}</p>`}</div>
        ${data.conflicts.length?`<p class="source-warning">${projectText("Пересечения в ближайшем плане:")} ${data.conflicts.length}${projectText(". Проверьте расписание.")}</p>`:''}${data.errors.map(e=>`<p class="source-warning">${(e.includes('BLATERO_GRANKA_ROOT')?projectText("Гранка пока не подключена."):esc(e))}</p>`).join('')}
        <div class="daily-actions"><button data-view="planning">${projectText("Открыть весь план ↗")}</button><span class="quiet">${data.plan_count>6?projectText("Показаны 6 из {p0}.",{p0:data.plan_count}):''}${projectText("Календари — из последнего снимка.")}</span></div>
      </section>
      <section class="daily-panel daily-memory" aria-labelledby="dailyMemoryTitle"><div class="daily-section-label"><span>${projectText("04 / ЗАКРЕПИТЬ")}</span><span>${projectText("ДО 5 МИНУТ")}</span></div><h3 id="dailyMemoryTitle">${projectText("Сначала вспомни сам")}</h3><p class="quiet">${projectText("Суть → метод → почему. Затем сверься с карточкой.")}</p>
        ${data.recall.map((r,i)=>`<article class="daily-retrieval"><span class="daily-memory-index">0${i+1}</span><div><span class="daily-meta">${projectNameText(r.task.project_id)} · ${esc(r.reason)}</span><h4>${esc(r.task.title)}</h4><button data-recall="${r.task.id}">${projectText("Попробовать вспомнить")}</button></div></article>`).join('')||`<p class="daily-empty-text">${data.recall_pinned?projectText("На сегодня возвращений нет."):projectText("Отметь важную задачу для закрепления в её карточке.")}</p>`}
        ${data.recall_count>2?`<p class="quiet">${projectText("Сейчас 2 темы из")} ${data.recall_count}${projectText(". После самооценки очередь обновится.")}</p>`:''}${data.recall_incomplete?`<p class="source-warning">${projectText("Отмеченных задач без сути, метода или причины: {count}. Дополните карточки.",{count:data.recall_incomplete})}</p>`:''}
        <p class="daily-footnote">${projectText("Самооценка назначает возвращение через 1, 3 или 7 дней. Пересказ не сохраняется; уведомлений нет.")}</p><button data-view="recall">${projectText("Выбрать другую задачу ↗")}</button>
      </section>
    </div><p class="daily-scope">${projectText("Фокус — во всём пространстве; вопросы, проверка, план и закрепление — в выбранном проекте. Поиск и период истории здесь не применяются.")}</p>
  </div>`;
  const grid=$('#dailyScreen .daily-grid'), left=document.createElement('div'), right=document.createElement('div');
  left.className=right.className='daily-column';
  left.append(grid.querySelector('.daily-focus'),grid.querySelector('.daily-plan'));
  right.append(grid.querySelector('.daily-attention'),grid.querySelector('.daily-memory'));
  grid.replaceChildren(left,right);
  const focusSearchLabel=document.createElement('label'), focusSearch=document.createElement('input');
  projectLabel(focusSearchLabel,()=>({source:"Найти задачу для фокуса",values:{}}));focusSearch.id='dailyFocusSearch';focusSearch.type='search';projectAttr(focusSearch,"placeholder","Название, суть или метод");
  focusSearchLabel.append(focusSearch);$('#dailyFocusForm').prepend(focusSearchLabel);
  focusSearch.oninput=()=>{
    const query=focusSearch.value.trim().toLowerCase(), selected=$('#dailyFocusSelect').value;
    const matches=choices.filter(t=>[projectName(t.project_id),t.title,t.goal,t.method].join(' ').toLowerCase().includes(query));
    $('#dailyFocusSelect').innerHTML='<option value="" '+projectBind(matches.length?'Выберите задачу':'Совпадений нет')+'>'+esc(projectUi(matches.length?'Выберите задачу':'Совпадений нет'))+'</option>'+matches.map(t=>`<option value="${t.id}">${esc(projectName(t.project_id)+' / '+t.title)}</option>`).join('');
    $('#dailyFocusSelect').value=matches.some(t=>t.id===selected)?selected:'';
  };
  $('#dailyFocusForm').onsubmit=e=>{e.preventDefault();action(async()=>{const t=state.tasks.find(t=>t.id===$('#dailyFocusSelect').value);await api('daily/focus',{work_item_id:t.id,revision:t.revision,focus_revision:focus.revision});dailySignature='';render();toast(projectUi("Фокус сохранён"));});};
  $('#dailyClearFocus')?.addEventListener('click',()=>action(async()=>{await api('daily/focus',{work_item_id:null,focus_revision:focus.revision});dailySignature='';render();toast(projectUi("Фокус снят"));}));
  $('#dailyAllQuestions')?.addEventListener('click',()=>action(async()=>{
    const full=await api('daily?questions=all'+(project?'&project_id='+encodeURIComponent(project):''));
    if(view==='daily'&&$('#projectFilter').value===project)$('#dailyScreen .daily-questions').innerHTML=full.attention.map(r=>`<article class="daily-question">${dailyTaskLabel(r.task)}<h4>${esc(r.question)}</h4><button data-open="${r.task.id}">${esc(r.task.title)} ↗</button></article>`).join('');
  }));
}
const dailyBaseOpenTask=openTask;
openTask=async function(id) {
  const opening=dailyBaseOpenTask(id),ticket=taskOpenEpoch;await opening;
  if(ticket!==taskOpenEpoch||selected?.task.id!==id || selected.task.merged_into)return;
  const task=selected.task, details=await api('daily/task/'+id);
  if(ticket!==taskOpenEpoch||selected?.task.id!==id || selected.task.revision!==task.revision)return;
  const open=details.decisions.find(r=>r.state==='open');
  $('#editForm').insertAdjacentHTML('afterend',`<section class="detail-section daily-task-tools"><h3>${projectText("Сегодня: фокус и решения")}</h3><div class="daily-actions"><button id="taskSetFocus">${projectText("Сделать текущей задачей")}</button><button id="taskPinRecall">${details.recall.recall_enabled?projectText("Убрать из ежедневного закрепления"):projectText("Закреплять важное решение")}</button></div>${!task.goal||!task.method||!task.rationale?`<p class="quiet">${projectText("Для ежедневного закрепления заполните суть, метод и причину выбора.")}</p>`:''}${open?`<form id="decisionAnswerForm"><h4>${projectText("Нужен твой ответ")}</h4><p>${esc(open.question)}</p>${open.context_hash?`<p class="quiet">${projectText("Сверьте текущие суть, метод и следующий шаг перед ответом.")}</p>`:''}${open.recommendation?`<p><b>${projectText("Рекомендация:")}</b> ${esc(open.recommendation)}</p>`:''}<label>${projectText("Моё решение")}<textarea name="answer" required maxlength="4000"></textarea></label><button class="primary">${projectText("Сохранить решение")}</button><p class="quiet">${projectText("Ответ сохраняется в истории. Статус и метод агент обновит отдельно.")}</p></form>`:`<details><summary>${projectText("Запросить решение")}</summary><form id="decisionRequestForm"><label>${projectText("Вопрос пользователю")}<textarea name="question" required maxlength="2000"></textarea></label><label>${projectText("Рекомендация и причина")}<textarea name="recommendation" maxlength="2000"></textarea></label><button>${projectText("Добавить в очередь внимания")}</button></form></details>`}${dailyAnsweredGroup(details.decisions)}</section>`);
  $('#taskSetFocus').disabled=['done','closed'].includes(task.status);
  $('#taskSetFocus').onclick=()=>action(async()=>{await api('daily/focus',{work_item_id:id,revision:task.revision,focus_revision:details.focus.revision});toast(projectUi("Текущая задача сохранена"));await openTask(id);if(view==='daily'){dailySignature='';render();}});
  $('#taskPinRecall').onclick=()=>action(async()=>{await api('daily/recall',{work_item_id:id,revision:task.revision,daily_revision:details.recall.revision,enabled:!details.recall.recall_enabled});toast(projectUi("Настройка закрепления сохранена"));await openTask(id);if(view==='daily'){dailySignature='';render();}});
  bindTaskExtra($('#decisionRequestForm'),task);
  $('#decisionRequestForm')?.addEventListener('submit',e=>{e.preventDefault();const form=e.target,values=Object.fromEntries(new FormData(form));action(async()=>{await api('daily/request',{work_item_id:id,revision:task.revision,...values});clearTaskExtra(form,values);if(ticket===taskOpenEpoch)await openTask(id);if(view==='daily'){dailySignature='';render();}toast(projectUi("Вопрос добавлен в очередь внимания"));});});
  $('#decisionAnswerForm')?.addEventListener('submit',e=>{e.preventDefault();const form=e.target,values=Object.fromEntries(new FormData(form));action(async()=>{await api('daily/resolve',{work_item_id:id,revision:task.revision,id:open.id,decision_revision:open.revision,answer:values.answer});clearTaskExtra(form,values);if(ticket===taskOpenEpoch)await openTask(id);if(view==='daily'){dailySignature='';render();}toast(projectUi("Решение сохранено в истории карточки"));});});
};
$('#recallDialog').addEventListener('close',()=>{if(view==='daily'){dailySignature='';render();}});
setInterval(()=>{if(view==='daily'&&!document.hidden&&!document.querySelector('dialog[open]'))render();},60000);
document.addEventListener('visibilitychange',()=>{if(view==='daily'&&!document.hidden)render();});
