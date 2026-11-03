'use strict';
/* Additional NextDo views: CdS ownership, independent projects and account management. */
const NextDoWorkspace=(()=>{
 const scopes={personal:'Il mio spazio',cds:'Corsi di Studio',common:'Comune a tutti i CdS',project:'Progetto',group:'Gruppo'};
 const projectScopes={independent:'Indipendente dai CdS',cds:'Uno o più CdS',common:'Tutti i CdS'};
 const set=(...nodes)=>el('div',{},nodes);
 const opt=(label,fn,kind='')=>btn(label,fn,kind);
 function taskScopeOptions(){return Object.entries(scopes).map(([k,v])=>[k,k==='common'&&S.me.role!=='admin'?v+' (sola lettura)':v])}
 function scopedCourses(){return S.me.role==='admin'?S.courses:S.courses.filter(x=>S.myCourseIds.includes(x.id))}
 function projectLabel(p){return projectScopes[p.scope]||p.scope}
 function projectView(main){
  const tools=el('div',{class:'workspace-tools'},[
   node('p','sub','Gestisci progetti dei CdS, progetti comuni e progetti indipendenti.'),
   opt('+ Nuovo progetto',()=>projectForm(),'primary')
  ]);
  main.append(tools);
  const projects=el('div',{class:'project-grid'});
  for(const p of S.projects){
   const n=Object.values(p.counts||{}).reduce((a,b)=>a+b,0);
   const done=p.counts?.done||0;
   const courseNames=(p.course_ids||[]).map(id=>S.courses.find(c=>c.id===id)?.code).filter(Boolean).join(', ');
   projects.append(el('button',{type:'button',class:'project-tile '+(S.selectedProject===p.id?'selected':''),onclick:()=>{S.selectedProject=p.id;render()}},[
    node('strong','',p.title),tag(projectLabel(p.scope)),node('span','muted',courseNames||'Nessun CdS associato'),
    node('span','project-progress',n?done+' / '+n+' attività completate':'Nessuna attività'),
    el('span',{class:'project-bar'},[el('i',{style:'width:'+(n?done/n*100:0)+'%'})])
   ]));
  }
  if(!S.projects.length)projects.append(node('div','empty','Nessun progetto. Crea il primo progetto in pochi passaggi.'));
  main.append(projects);
  const current=S.projects.find(p=>p.id===S.selectedProject)||S.projects[0];
  if(!current)return;
  S.selectedProject=current.id;
  const panel=el('section',{class:'card project-board'});
  const heading=el('div',{class:'card-head'},[
   node('h2','',current.title),
   opt('Modifica progetto',()=>projectForm(current),'small'),
   opt('+ Attività',()=>taskForm(null,'task',null,{scope:'project',project_id:current.id}),'primary')
  ]);
  panel.append(heading);
  if(current.description)panel.append(node('p','sub',current.description));
  const kanban=el('div',{class:'kanban-board'});
  for(const [status,label] of Object.entries(statuses)){
   const col=el('section',{class:'kanban-col','data-status':status});
   const cards=S.tasks.filter(t=>t.project_id===current.id&&t.status===status);
   col.append(el('h3',{},[label,tag(String(cards.length))]));
   if(!cards.length)col.append(node('p','kanban-empty','Nessuna attività'));
   for(const t of cards){
    const card=el('div',{class:'kanban-task',draggable:t.can_edit===false?'false':'true'},[
     node('strong','',t.title),
     node('span','muted',t.due_at?fmt(t.due_at):'Senza scadenza'),
     el('div',{class:'kanban-tags'},[tag(priority[t.priority]||'Normale',t.priority),...(t.labels||[]).slice(0,2).map(x=>tag(x))])
    ]);
    card.addEventListener('click',()=>taskForm(t));
    card.addEventListener('dragstart',e=>{e.dataTransfer.setData('text/plain',String(t.id));e.dataTransfer.effectAllowed='move'});
    col.append(card);
   }
   col.addEventListener('dragover',e=>{if([...e.dataTransfer.types].includes('text/plain')){e.preventDefault();col.classList.add('kanban-over')}});
   col.addEventListener('dragleave',()=>col.classList.remove('kanban-over'));
   col.addEventListener('drop',async e=>{
    e.preventDefault();col.classList.remove('kanban-over');
    const id=Number(e.dataTransfer.getData('text/plain'));
    if(!S.tasks.some(t=>t.id===id&&t.project_id===current.id))return;
    try{await api('/tasks/'+id+'/status',{method:'PATCH',body:JSON.stringify({status})});await refresh();render()}
    catch(err){msg(err.message,true)}
   });
   kanban.append(col);
  }
  panel.append(kanban);
  const hint=node('p','sub','Trascina una scheda tra le colonne oppure aprila e cambia lo stato. Le attività con completamento per CdS richiedono la conferma del singolo corso.');
  panel.append(hint);main.append(panel);
 }
 function projectForm(p=null){
  const {box,back}=modal(p?'Modifica progetto':'Nuovo progetto');
  const f=el('form',{class:'formgrid'});
  const title=input('title','Titolo del progetto',p?.title||'');
  const desc=el('textarea',{class:'field',rows:'4'});desc.value=p?.description||'';
  const scope=select('scope',Object.entries(projectScopes),p?.scope||'independent');
  const status=select('status',Object.entries(statuses),p?.status||'doing');
  const manager=select('manager_id',[['','Me stesso'],...S.users.map(u=>[String(u.id),u.display_name])],String(p?.manager_id||''));
  const due=input('due','',dtLocal(p?.due_at),'datetime-local');
  const courseBox=checkboxes('CdS coinvolti',scopedCourses().map(c=>[c.id,c.code+' — '+c.name]),p?.course_ids||[]);
  const memberBox=checkboxes('Colleghi partecipanti',S.users.filter(u=>u.active&&u.id!==S.me.id).map(u=>[u.id,u.display_name]),p?.member_ids||[]);
  const courseWrap=el('div',{class:'full'},[courseBox.outer]);
  const update=()=>{courseWrap.style.display=scope.value==='cds'?'':'none'};
  scope.addEventListener('change',update);
  f.append(field('Titolo',title),field('Ambito',scope),el('div',{class:'full'},[field('Descrizione',desc)]),field('Stato',status),field('Responsabile',manager),field('Scadenza facoltativa',due),courseWrap,memberBox.outer);
  update();
  const actions=el('div',{class:'actions full'},[opt('Annulla',()=>back.remove()),el('button',{type:'submit',class:'btn primary',text:p?'Salva progetto':'Crea progetto'})]);
  f.append(actions);
  f.addEventListener('submit',async e=>{
   e.preventDefault();
   const data={title:title.value.trim(),description:desc.value,scope:scope.value,status:status.value,
    manager_id:manager.value?Number(manager.value):null,due_at:due.value?new Date(due.value).toISOString():null,
    course_ids:scope.value==='cds'?courseBox.selected():[],member_ids:memberBox.selected()};
   if(!data.title)return msg('Titolo obbligatorio',true);
   try{
    const r=await api('/projects'+(p?'/'+p.id:''),{method:p?'PUT':'POST',body:JSON.stringify(data)});
    if(!p)S.selectedProject=r.id;
    back.remove();await refresh();render();
   }catch(error){msg(error.message,true)}
  });
  box.append(f);
 }
 function courseAssignmentForm(c){
  const {box,back}=modal('Colleghi assegnati — '+c.code);
  const selected=S.courseAssignees.filter(x=>x.course_id===c.id).map(x=>x.user_id);
  const checklist=checkboxes('Seleziona uno o più colleghi',S.users.filter(x=>x.active).map(x=>[x.id,x.display_name]),selected);
  box.append(node('p','sub','I colleghi selezionati potranno vedere e gestire le attività di questo Corso di Studio.'),checklist.outer,
   el('div',{class:'actions'},[opt('Annulla',()=>back.remove()),opt('Salva assegnazioni',async()=>{
    try{
     await api('/courses/'+c.id+'/assignees',{method:'PUT',body:JSON.stringify({user_ids:checklist.selected()})});
     const result=await api('/course-assignees');S.courseAssignees=result;back.remove();render();msg('Assegnazioni aggiornate');
    }catch(error){msg(error.message,true)}
   },'primary')]));
 }
 function courseAdminButton(c){
  if(S.me.role!=='admin')return null;
  const assigned=S.courseAssignees.filter(a=>a.course_id===c.id);
  return opt('Assegna colleghi ('+assigned.length+')',()=>courseAssignmentForm(c),'small');
 }
 function settings(main){
  const section=el('section',{class:'card workspace-settings',style:'margin-top:16px'});
  section.append(node('h2','','Il mio profilo'),node('p','sub','Modifica la tua password senza coinvolgere l’amministratore.'));
  section.append(opt('Cambia password',changePasswordForm,'primary'));
  main.append(section);
  if(S.me.role!=='admin')return;
  const section2=el('section',{class:'card workspace-settings',style:'margin-top:16px'});
  section2.append(node('h2','','Gestione utenti'),node('p','sub','Crea i colleghi con + Utente, poi assegna loro i CdS. Qui puoi cambiare ruolo, reimpostare password e attivare/disattivare account.'));
  for(const u of S.users){
   const line=el('div',{class:'rowtask'},[
    node('span','taskmain',u.display_name+' · '+u.username+(u.active?'':' · Disattivato')),
    opt('Ruolo / Stato',()=>editAccount(u),'small'),
    opt('Reimposta password',()=>resetPassword(u),'small')
   ]);
   section2.append(line);
  }
  main.append(section2);
 }
 function changePasswordForm(){
  const {box,back}=modal('Cambia la tua password');
  const f=el('form',{class:'formgrid'});
  const old=input('old','Password attuale','','password'),pw=input('new','Nuova password (almeno 12 caratteri)','','password'),again=input('again','Conferma nuova password','','password');
  f.append(field('Password attuale',old),field('Nuova password',pw),field('Conferma nuova password',again));
  f.append(el('button',{type:'submit',class:'btn primary',text:'Aggiorna password'}));
  f.addEventListener('submit',async e=>{
   e.preventDefault();if(pw.value!==again.value)return msg('Le password non coincidono',true);
   try{await api('/profile/password',{method:'POST',body:JSON.stringify({current_password:old.value,new_password:pw.value})});back.remove();alert('Password aggiornata. Accedi nuovamente.');location.reload()}catch(error){msg(error.message,true)}
  });box.append(f);
 }
 function resetPassword(u){
  const {box,back}=modal('Reimposta password — '+u.display_name);
  box.append(node('p','sub','La password attuale non è visibile. Dopo la modifica tutte le sessioni di questo utente saranno revocate.'));
  const pw=input('pw','Nuova password (almeno 12 caratteri)','','password');
  box.append(field('Nuova password',pw),opt('Reimposta password',async()=>{
   if(pw.value.length<12)return msg('Servono almeno 12 caratteri',true);
   if(!confirm('Reimpostare la password per '+u.display_name+'?'))return;
   try{await api('/admin/users/'+u.id+'/password',{method:'POST',body:JSON.stringify({new_password:pw.value})});back.remove();msg('Password reimpostata')}catch(e){msg(e.message,true)}
  },'primary'));
 }
 function editAccount(u){
  const {box,back}=modal('Gestisci account — '+u.display_name);
  const role=select('role',[['user','Utente'],['admin','Amministratore']],u.role);
  const active=el('input',{type:'checkbox',checked:!!u.active});
  box.append(field('Ruolo',role),el('label',{},[active,' Account attivo']),opt('Salva',async()=>{
   try{await api('/admin/users/'+u.id,{method:'PUT',body:JSON.stringify({role:role.value,active:active.checked})});back.remove();await refresh();render();msg('Account aggiornato')}catch(e){msg(e.message,true)}
  },'primary'));
 }
 return {projectView,projectForm,courseAssignmentForm,courseAdminButton,settings,taskScopeOptions,scopedCourses};
})();
