'use strict';
// Project closure only changes the project rail; its tasks retain their states.
let lifecycleProject=null;
const lifecycleNav=renderProjectNav;
renderProjectNav=function(){
  lifecycleNav();
  const nav=$('#projectNav'),selected=$('#projectFilter').value;
  const group=document.createElement('details');group.className='closed-projects';group.id='closedProjects';
  const closed=state.projects.filter(p=>p.lifecycle?.closed);
  group.innerHTML=`<summary>${projectText("Закрытые проекты")} <span>${closed.length}</span></summary><div class="closed-project-list"></div>`;
  group.open=localStorage.getItem('blatero.closedProjectsOpen')==='true'||closed.some(p=>p.id===selected);
  let matching=0;
  for(const p of state.projects){
    const button=nav.querySelector(`[data-project="${p.id}"]`);if(!button)continue;
    const row=document.createElement('div');row.className='project-row';row.dataset.projectRow=p.id;
    button.replaceWith(row);row.append(button);
    const isClosed=!!p.lifecycle?.closed;
    row.insertAdjacentHTML('beforeend',`<button class="project-lifecycle-action" ${isClosed?'data-project-reopen':'data-project-close'}="${p.id}" ${projectAttrs("title",isClosed?"Восстановить проект":"Закрыть проект")} ${projectAttrs("aria-label",isClosed?"Восстановить проект {name}":"Закрыть проект {name}",{name:p.name})}>${isClosed?'↶':'×'}</button>`);
    if(isClosed){group.querySelector('.closed-project-list').append(row);matching++;}
  }
  if(closed.length){
    if(matching&&$('#projectSearch').value.trim())group.open=true;
    if(!matching)group.querySelector('.closed-project-list').innerHTML=`<p class="quiet">${projectText("Нет совпадений с поиском.")}</p>`;
    nav.append(group);group.addEventListener('toggle',()=>localStorage.setItem('blatero.closedProjectsOpen',String(group.open)));
  }
  projectValue($('#projectTotal'),state.projects.length-closed.length);
};

document.body.insertAdjacentHTML('beforeend',`<dialog id="projectCloseDialog"><form id="projectCloseForm"><div class="dialog-heading"><h2>${projectText("Закрыть проект")}</h2><button type="button" data-close ${projectAttrs("aria-label","Закрыть")}>×</button></div><p id="projectCloseName"></p><p class="quiet">${projectText("Проект уйдёт из основного списка в группу «Закрытые проекты». Задачи, материалы и знания сохранятся. Проект можно восстановить.")}</p><p id="projectCloseTasks" class="quiet"></p><label>${projectText("Причина")} <span class="quiet">${projectText("(необязательно)")}</span><textarea name="reason" maxlength="2000" ${projectAttrs("placeholder","Например, работа завершена или проект отложен")}></textarea></label><div class="actions"><button type="submit" class="primary">${projectText("Закрыть проект")}</button><button type="button" data-close>${projectText("Отмена")}</button></div></form></dialog>`);
document.addEventListener('click',event=>{
  const close=event.target.closest('[data-project-close]'),reopen=event.target.closest('[data-project-reopen]');
  if(!close&&!reopen)return;
  const p=state.projects.find(p=>p.id===(close?.dataset.projectClose||reopen?.dataset.projectReopen));if(!p)return;
  if(close){
    lifecycleProject=p;$('#projectCloseForm').reset();projectValue($('#projectCloseName'),p.name);
    const n=state.tasks.filter(t=>t.project_id===p.id&&!['closed','done'].includes(t.status)).length;
    projectLabel($('#projectCloseTasks'),()=>(n?{source:"В проекте {p0} незавершённых задач. Их статусы не изменятся.",values:{p0:n}}:{source:"Все текущие статусы задач сохранятся.",values:{}}));
    $('#projectCloseDialog').showModal();
  }else action(async()=>{reopen.disabled=true;try{await api('project-lifecycle',{project_id:p.id,revision:p.lifecycle?.revision||0,closed:false});await refresh(true);toast(projectUi("Проект восстановлен"));}finally{if(reopen.isConnected)reopen.disabled=false;}});
});
$('#projectCloseForm').onsubmit=event=>{
  event.preventDefault();const p=lifecycleProject;if(!p)return;
  const button=event.submitter||$('#projectCloseForm [type=submit]');button.disabled=true;
  action(async()=>{try{
    await api('project-lifecycle',{project_id:p.id,revision:p.lifecycle?.revision||0,closed:true,reason:$('#projectCloseForm [name=reason]').value});
    $('#projectCloseDialog').close();lifecycleProject=null;
    if($('#projectFilter').value===p.id){$('#projectFilter').value='';$('#projectInfo').hidden=true;$('#projectFilter').dispatchEvent(new Event('change'));}
    await refresh(true);toast(projectUi("Проект перемещён в «Закрытые проекты»"));
  }finally{button.disabled=false;}});
};
