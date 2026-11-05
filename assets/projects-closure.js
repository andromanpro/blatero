'use strict';
// Closing retires a card without accepting its result. Reopening is explicit.
let closureTask = null;
let closureHistoryScope = null;
const closureBaseChangeStatus = changeStatus;
changeStatus = async function(task, to) {
  if (task.status === to) return;
  const readTask = selected?.task.id === task.id ? selected.task : task;
  if (to === 'closed') {
    closureTask = {...readTask};
    $('#closeForm').reset();
    $('#closeTaskTitle').textContent = readTask.title;
    $('#closeDialog').showModal();
    return;
  }
  if (readTask.status !== 'closed' || to === 'done') return closureBaseChangeStatus(readTask, to);
  await api('status', {work_item_id:readTask.id, revision:readTask.revision,
    from:'closed', to, reason:'Восстановление закрытой задачи пользователем'});
  await refresh(true);
  if (selected?.task.id === readTask.id) await openTask(readTask.id);
  toast(projectUi("Карточка восстановлена: {status}",{status:projectUi(labels[to])}));
};

function closedCard(task) {
  return `<article class="card closed-card"><div class="card-code"><span>${esc(task.id.slice(0,8).toUpperCase())}</span><span>${projectText("ЗАКРЫТО")}</span></div>
    <span class="tag">${projectNameText(task.project_id)}</span>
    <button data-open="${task.id}">${esc(task.title)}</button>
    <p class="closure-reason"><b>${projectText("Причина:")}</b> ${(task.closed_reason?esc(task.closed_reason):projectText("Смотрите историю карточки"))}</p>
    <p class="meta">${projectTime(task.closed_at)} ${projectText("· ранее:")} ${(labels[task.closed_from_status]?projectText(labels[task.closed_from_status]):esc('—'))}</p>
    <div class="actions"><button data-restore-task="${task.id}" data-to="inbox">${projectText("Во входящие")}</button><button data-restore-task="${task.id}" data-to="active">${projectText("В работу")}</button></div>
  </article>`;
}
const closureBaseRender = render;
render = function() {
  $('#historyFilter').disabled = view === 'closed';
  if (view !== 'closed') {
    if (closureHistoryScope !== null) {
      $('#historyFilter').value = closureHistoryScope;
      closureHistoryScope = null;
    }
    return closureBaseRender();
  }
  if (closureHistoryScope === null) closureHistoryScope = $('#historyFilter').value;
  $('#historyFilter').value = 'all';
  document.body.classList.remove('daily-view', 'library-view');
  const tasks = filtered();
  renderOverview(tasks);
  generation++;
  $('#content').innerHTML = `<p class="quiet">${projectText("Закрытие сохраняет историю и материалы. Оно не означает приёмку результата. Здесь показаны закрытые карточки за всё время; поиск и фильтр проекта работают.")}</p>`+
    (tasks.length ? `<div class="knowledge-grid closed-grid">${tasks.map(closedCard).join('')}</div>` :
      `<div class="welcome"><h2>${projectText("Закрытых карточек пока нет")}</h2><p class="quiet">${projectText("Их можно вернуть во входящие или в работу в любой момент.")}</p></div>`);
};

const closureBaseOpenTask = openTask;
openTask = async function(id) {
  const opening=closureBaseOpenTask(id),ticket=taskOpenEpoch;await opening;
  if (ticket!==taskOpenEpoch || selected?.task.id !== id || selected.task.merged_into) return;
  const task = selected.task;
  const closed = task.status === 'closed';
  $('#detail').insertAdjacentHTML('beforeend', `<section class="detail-section closure-tools">
    <h3>${closed ? projectText("Карточка закрыта") : projectText("Закрытие задачи")}</h3>
    ${task.closed_at ? `<p><b>${closed?projectText("Причина закрытия"):projectText("Последнее закрытие")}:</b> ${esc(task.closed_reason)}</p><p class="meta">${projectTime(task.closed_at)} ${projectText("· ранее:")} ${(labels[task.closed_from_status]?projectText(labels[task.closed_from_status]):esc('—'))}</p>` : ''}
    ${closed ? `<p class="quiet">${projectText("Чтобы изменить поля или план, восстановите карточку. Добавлять источники и предложения можно без восстановления.")}</p><div class="actions"><button class="primary" data-restore-task="${id}" data-to="inbox">${projectText("Восстановить во входящие")}</button><button data-restore-task="${id}" data-to="active">${projectText("Восстановить в работу")}</button></div>` :
      `<p class="quiet">${projectText("Если задача больше не актуальна, укажите причину закрытия. Результат не будет автоматически принят.")}</p><button data-retire-task="${id}">${projectText("Закрыть задачу")}</button>`}
    </section>`);
  if (closed) {
    $('#taskSaveTop').disabled=true;
    $('#detail').querySelectorAll('#editForm input,#editForm select,#editForm textarea,#editForm button,#taskPlanForm input,#taskPlanForm button,#taskPinRecall,[data-recall],#decisionRequestForm input,#decisionRequestForm textarea,#decisionRequestForm button').forEach(control=>control.disabled=true);
  }
};

document.addEventListener('click', event=>{
  const button = event.target.closest('[data-retire-task],[data-restore-task]');
  if (!button) return;
  const id = button.dataset.retireTask || button.dataset.restoreTask;
  const task = selected?.task.id === id ? selected.task : state.tasks.find(item=>item.id===id);
  if (task) action(()=>changeStatus(task, button.dataset.retireTask ? 'closed' : button.dataset.to));
});
$('#closeForm').onsubmit = event=>{
  event.preventDefault();
  action(async()=>{
    const task = closureTask;
    const reason = String(new FormData(event.target).get('reason') || '').trim();
    if (!reason) throw Error(projectUi("Укажите причину закрытия"));
    await api('status', {work_item_id:task.id, revision:task.revision,
      from:task.status, to:'closed', reason});
    $('#closeDialog').close();
    await refresh(true);
    if (selected?.task.id === task.id) await openTask(task.id);
    toast(projectUi("Карточка закрыта. Она доступна в разделе «Закрытые»."));
  });
};
$('#closeDialog').addEventListener('close', ()=>{
  // Cancelling the dialog must not leave a status selector showing an unsaved value.
  document.querySelectorAll('[data-status]').forEach(select=>{
    const task = state.tasks.find(item=>item.id===select.dataset.status);
    if (task) select.value = task.status;
  });
});
