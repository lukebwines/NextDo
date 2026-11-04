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
   const linkedIds=(p.responsibilities||[]).length?Array.from(new Set(p.responsibilities.map(a=>a.course_id))):(p.course_ids||[]);
    const courseNames=linkedIds.map(id=>S.courses.find(c=>c.id===id)?.code).filter(Boolean).join(', ');
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
   ...(current.can_edit?[
    opt('Esporta JSON per Lists',()=>{
     // Direct download of a single project; nothing is uploaded to SharePoint.
     const link=el('a',{href:'api/projects/'+current.id+'/sharepoint-export',download:''});
     document.body.append(link);link.click();link.remove();
    },'small'),
    opt('Modifica progetto',()=>projectForm(current),'small')
   ]:[]),
   opt('+ Attività',()=>taskForm(null,'task',null,{scope:'project',project_id:current.id}),'primary')
  ]);
  panel.append(heading);
  if(current.can_edit)panel.append(node('p','sub','Assegna i colleghi ai CdS nelle impostazioni del progetto. Esporta JSON per Lists genera automaticamente una riga per attività e per CdS, preservando gli avanzamenti già modificati in Microsoft Lists. Prima di caricare file con assegnazioni reali occorre adeguare le colonne e il flusso Power Automate.'));
  if(current.description)panel.append(node('p','sub',current.description));
  if((current.responsibilities||[]).length){
   const overview=el('div',{class:'card project-responsibilities-overview'},[node('h3','','Responsabili e CdS assegnati')]);
   const byUser=new Map();
   for(const r of current.responsibilities){
    if(!byUser.has(r.user_id))byUser.set(r.user_id,[]);
    const course=S.courses.find(c=>c.id===r.course_id);
    byUser.get(r.user_id).push(course?.code||String(r.course_id));
   }
   for(const [uid,courseCodes] of byUser){
    const colleague=S.users.find(u=>u.id===uid);
    overview.append(el('div',{class:'rowtask'},[
     node('strong','taskmain',colleague?.display_name||'Utente non disponibile'),
     node('span','muted',courseCodes.join(', '))
    ]));
   }
   panel.append(overview);
  }
  const viewbar=el('div',{class:'project-view-toolbar','aria-label':'Visualizzazione progetto'});
  for(const [mode,label] of [['kanban','Kanban'],['gantt','Gantt']]){
   const view=opt(label,()=>{
    S.projectMode=mode;localStorage.setItem('nextdo-project-view',mode);render();
   },'small'+(S.projectMode===mode?' active':''));
   view.setAttribute('aria-pressed',String(S.projectMode===mode));
   viewbar.append(view);
  }
  panel.append(viewbar);
  if(S.projectMode==='gantt'){
   panel.append(NextDoGantt.render(current));
   main.append(panel);
   return;
  }
  const kanban=el('div',{class:'kanban-board'});
  let draggingId=null;
  const updateTask=async(t,newStatus)=>{
   if(newStatus===t.status)return;
   try{
    await api('/tasks/'+t.id+'/status',{method:'PATCH',body:JSON.stringify({status:newStatus})});
    await refresh();render();
   }catch(error){msg('Impossibile aggiornare «'+t.title+'»: '+error.message,true);await refresh();render()}
  };
  for(const [status,label] of Object.entries(statuses)){
   const col=el('section',{class:'kanban-col','data-status':status});
   const cards=S.tasks.filter(t=>t.project_id===current.id&&t.status===status);
   col.append(el('h3',{},[label,tag(String(cards.length))]));
   if(!cards.length)col.append(node('p','kanban-empty','Nessuna attività'));
   for(const t of cards){
    const movable=t.can_move===true;
    const card=el('div',{class:'kanban-task'+(movable?' kanban-movable':' kanban-readonly'),draggable:String(movable),
     title:movable?'Trascina in un’altra colonna per aggiornare lo stato':'Sola lettura: attività assegnata a un altro collega',
     'aria-label':t.title+' — '+(statuses[t.status]||t.status)});
    if(movable)card.append(node('span','kanban-drag-handle','⠿'));
    card.append(
     node('strong','',t.title),
     node('span','muted',t.due_at?fmt(t.due_at):'Senza scadenza'),
     el('div',{class:'kanban-tags'},[tag(priority[t.priority]||'Normale',t.priority),...(t.labels||[]).slice(0,2).map(x=>tag(x))])
    );
    if(movable){
     const controls=el('div',{class:'kanban-card-tools'});
     const newStatus=select('task_status',Object.entries(statuses),t.status);
     newStatus.classList.add('kanban-status-select');
     newStatus.setAttribute('aria-label','Cambia stato: '+t.title);
     if(t.completion_mode==='per_course'&&(t.courses||[]).length){
      const doneOption=newStatus.querySelector('option[value="done"]');
      if(doneOption&&t.status!=='done')doneOption.disabled=true;
     }
     newStatus.addEventListener('click',e=>e.stopPropagation());
     newStatus.addEventListener('pointerdown',e=>e.stopPropagation());
     newStatus.addEventListener('change',e=>{e.stopPropagation();updateTask(t,newStatus.value)});
     controls.append(newStatus,opt('Aggiorna',e=>{e.stopPropagation();NextDoProgress.open(t)},'small'));
     card.append(controls);
     card.addEventListener('dragstart',e=>{
      if(e.target.closest?.('select,button')){e.preventDefault();return}
      draggingId=t.id;
      e.dataTransfer.setData('text/plain',String(t.id));
      e.dataTransfer.effectAllowed='move';
      card.classList.add('kanban-dragging');
     });
     card.addEventListener('dragend',()=>{
      draggingId=null;
      card.classList.remove('kanban-dragging');
      kanban.querySelectorAll('.kanban-over').forEach(x=>x.classList.remove('kanban-over'));
     });
    }else{
     card.append(node('span','kanban-permission-label','Visibile · non assegnata a te'));
    }
    card.addEventListener('click',e=>{
     if(e.target.closest?.('button,select'))return;
     taskForm(t);
    });
    col.append(card);
   }
   col.addEventListener('dragenter',e=>{
    if(draggingId!==null){e.preventDefault();col.classList.add('kanban-over')}
   });
   col.addEventListener('dragover',e=>{
    if(draggingId!==null){
     e.preventDefault();
     if(e.dataTransfer)e.dataTransfer.dropEffect='move';
     col.classList.add('kanban-over');
    }
   });
   col.addEventListener('dragleave',e=>{
    if(!col.contains(e.relatedTarget))col.classList.remove('kanban-over');
   });
   col.addEventListener('drop',e=>{
    e.preventDefault();col.classList.remove('kanban-over');
    const id=draggingId||Number(e.dataTransfer?.getData('text/plain'));
    draggingId=null;
    const t=S.tasks.find(x=>x.id===id&&x.project_id===current.id);
    if(!t||!t.can_move)return;
    updateTask(t,status);
   });
   kanban.append(col);
  }
  panel.append(kanban);
  const hint=node('p','sub','Trascina una scheda con il simbolo ⠿ oppure usa il menu Stato in basso alla scheda. Le attività assegnate ad altri colleghi sono in sola lettura; i completamenti per CdS richiedono la conferma del singolo corso.');
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
  const featured=el('input',{type:'checkbox',checked:p?p.featured!==0:true});
  const courseBox=checkboxes('CdS coinvolti',scopedCourses().map(c=>[c.id,c.code+' — '+c.name]),p?.course_ids||[]);
  const memberBox=checkboxes('Altri partecipanti con accesso al progetto',S.users.filter(u=>u.active&&u.id!==S.me.id).map(u=>[u.id,u.display_name]),p?.member_ids||[]);
  const responsibilities=el('div',{class:'full project-responsibilities'});
  responsibilities.append(
   node('h3','','Colleghi coinvolti'),
   node('p','sub','Seleziona sopra i CdS tramite spunte: NextDo propone automaticamente i colleghi associati in Corsi di Studio. Puoi modificare le proposte solo per questo progetto.')
  );
  const assignmentOverview=el('div',{class:'project-assignment-overview'});
  responsibilities.append(assignmentOverview);
  const responsibilityRows=el('div',{class:'project-responsibility-rows'});
  const activeCourses=scopedCourses().filter(c=>c.active);
  const colleagueOptions=[['','Seleziona collega'],...S.users.filter(u=>u.active).map(u=>[String(u.id),u.display_name])];
  const defaultCoursesFor=uid=>S.courseAssignees
   .filter(a=>a.user_id===Number(uid)).map(a=>a.course_id);
  const scopedDefaultsFor=uid=>defaultCoursesFor(uid)
   .filter(cid=>scope.value!=='cds'||courseBox.selected().includes(cid));
  function updateOverview(){
   assignmentOverview.replaceChildren();
   const selected=scope.value==='cds'?new Set(courseBox.selected()):null;
   if(selected&&!selected.size){
    assignmentOverview.append(node('p','sub','Seleziona almeno un CdS per vedere i colleghi proposti.'));
    return;
   }
   const byUser=new Map(),covered=new Set();
   for(const row of responsibilityRows.children){
    const uid=Number(row.querySelector('select[name="responsibility_user"]').value);
    if(!uid)continue;
    for(const check of row.querySelectorAll('input[name="responsibility_course"]:checked')){
     const cid=Number(check.value);
     if(selected&&!selected.has(cid))continue;
     if(!byUser.has(uid))byUser.set(uid,[]);
     if(!byUser.get(uid).includes(cid))byUser.get(uid).push(cid);
     covered.add(cid);
    }
   }
   if(!byUser.size)assignmentOverview.append(node('p','sub','Nessun collega ancora associato ai CdS selezionati.'));
   for(const [uid,cids] of byUser){
    const person=S.users.find(u=>u.id===uid);
    const names=cids.map(cid=>{
     const course=S.courses.find(c=>c.id===cid);
     return course?.code||String(cid);
    });
    assignmentOverview.append(el('div',{class:'project-assignment-summary-row'},[
     node('strong','',person?.display_name||'Utente non disponibile'),
     node('span','sub',names.join(', '))
    ]));
   }
   if(selected){
    const missing=[...selected].filter(cid=>!covered.has(cid));
    if(missing.length){
     const names=missing.map(cid=>S.courses.find(c=>c.id===cid)?.code||String(cid));
     assignmentOverview.append(node('p','project-assignment-warning',
      'Nessun collega predefinito per: '+names.join(', ')+'. Puoi indicarlo in “Modifica assegnazioni”.'));
    }
   }
  }
  function addResponsibilityGroup(userId='',savedCourses=null){
   const group=el('section',{class:'project-colleague-group'});
   const head=el('div',{class:'project-colleague-header'});
   const colleague=select('responsibility_user',colleagueOptions,String(userId||''));
   const checks=el('div',{class:'project-course-checklist'});
   const hint=node('p','sub','');
   const reset=opt('Ripristina predefiniti',()=>{drawChecks(scopedDefaultsFor(colleague.value));updateOverview()},'small');
   const remove=opt('Rimuovi collega',()=>{group.remove();updateOverview()},'small');
   head.append(field('Collega responsabile',colleague),reset,remove);
   group.append(head,checks,hint);
   function updateAllowed(){
    const allowed=new Set(courseBox.selected());
    for(const check of checks.querySelectorAll('input[name="responsibility_course"]')){
     const outOfScope=scope.value==='cds'&&!allowed.has(Number(check.value));
     check.disabled=outOfScope&&!check.checked;
    }
    const chosen=checks.querySelectorAll('input[name="responsibility_course"]:checked').length;
    hint.textContent=chosen+' CdS selezionati per questo progetto';
   }
   function drawChecks(selectedIds=[]){
    checks.replaceChildren();
    for(const c of activeCourses){
     const check=el('input',{type:'checkbox',name:'responsibility_course',
      value:String(c.id),checked:selectedIds.includes(c.id)});
     check.addEventListener('change',()=>{updateAllowed();updateOverview()});
     checks.append(el('label',{class:'project-course-option'},[check,
      node('span','',c.code+' — '+c.name)]));
    }
    updateAllowed();
   }
   colleague.addEventListener('change',()=>{drawChecks(scopedDefaultsFor(colleague.value));updateOverview()});
   drawChecks(savedCourses===null?scopedDefaultsFor(userId):savedCourses);
   responsibilityRows.append(group);
   return {group,updateAllowed};
  }
  const existingByUser=new Map();
  for(const a of p?.responsibilities||[]){
   if(!existingByUser.has(a.user_id))existingByUser.set(a.user_id,[]);
   existingByUser.get(a.user_id).push(a.course_id);
  }
  const responsibilityGroups=[];
  function appendColleague(uid='',ids=null){
   const group=addResponsibilityGroup(uid,ids);
   responsibilityGroups.push(group);
   return group;
  }
  for(const [uid,ids] of existingByUser)appendColleague(uid,ids);
  const advanced=el('details',{class:'project-responsibility-advanced'});
  advanced.append(
   node('summary','','Modifica assegnazioni per questo progetto (facoltativo)'),
   responsibilityRows,
   opt('+ Aggiungi collega',()=>{appendColleague();updateOverview()},'small'),
   node('p','sub','Le modifiche qui effettuate non cambiano le associazioni generali in Corsi di Studio. I progetti già salvati mantengono le proprie assegnazioni.')
  );
  responsibilities.append(advanced);
  // Apply defaults only to newly selected CdS. Keep saved project assignments unchanged.
  let previousSelected=new Set(courseBox.selected());
  function syncSelectedCourses(){
   if(scope.value!=='cds'){update();return}
   const selected=new Set(courseBox.selected());
   for(const cid of previousSelected){
    if(selected.has(cid))continue;
    for(const item of responsibilityGroups){
     if(item.group.parentNode!==responsibilityRows)continue;
     const check=[...item.group.querySelectorAll('input[name="responsibility_course"]')]
      .find(el=>Number(el.value)===cid);
     if(check)check.checked=false;
    }
   }
   for(const cid of selected){
    if(previousSelected.has(cid))continue;
    for(const a of S.courseAssignees.filter(a=>a.course_id===cid)){
     let item=responsibilityGroups.find(item=>item.group.parentNode===responsibilityRows&&
      Number(item.group.querySelector('select[name="responsibility_user"]').value)===a.user_id);
     if(!item)item=appendColleague(a.user_id,[]);
     const check=[...item.group.querySelectorAll('input[name="responsibility_course"]')]
      .find(el=>Number(el.value)===cid);
     if(check)check.checked=true;
    }
   }
   previousSelected=selected;
   update();
  }
  const courseWrap=el('div',{class:'full'},[courseBox.outer]);
  const update=()=>{
   courseWrap.style.display=scope.value==='cds'?'':'none';
   for(const item of responsibilityGroups)item.updateAllowed();
   updateOverview();
  };
  scope.addEventListener('change',syncSelectedCourses);
  courseBox.outer.addEventListener('change',syncSelectedCourses);
  f.append(field('Titolo',title),field('Ambito',scope),el('div',{class:'full'},[field('Descrizione',desc)]),field('Stato',status),field('Responsabile',manager),field('Scadenza facoltativa',due),courseWrap,responsibilities,memberBox.outer,
   el('label',{class:'full project-featured-option'},[featured,' Mostra Gantt nella Dashboard dei partecipanti']));
  update();
  const actions=el('div',{class:'actions full'},[opt('Annulla',()=>back.remove()),el('button',{type:'submit',class:'btn primary',text:p?'Salva progetto':'Crea progetto'})]);
  f.append(actions);
  f.addEventListener('submit',async e=>{
   e.preventDefault();
   const assignments=[],seenColleagues=new Set();
   for(const group of responsibilityRows.children){
    const chosen=[...group.querySelectorAll('input[name="responsibility_course"]:checked')];
    if(!chosen.length)continue;
    const userId=Number(group.querySelector('select[name="responsibility_user"]').value);
    if(!userId)return msg('Seleziona il collega per le spunte presenti.',true);
    if(seenColleagues.has(userId))return msg('Il collega è già presente: seleziona tutti i suoi CdS nello stesso riquadro.',true);
    seenColleagues.add(userId);
    for(const check of chosen)assignments.push({course_id:Number(check.value),user_id:userId});
   }
   if(scope.value==='cds'){
    const allowed=new Set(courseBox.selected());
    if(assignments.some(a=>!allowed.has(a.course_id)))
     return msg('Un CdS assegnato non è incluso tra i CdS del progetto: selezionalo sopra o togli la spunta.',true);
   }
   const data={title:title.value.trim(),description:desc.value,scope:scope.value,status:status.value,featured:featured.checked,
    manager_id:manager.value?Number(manager.value):null,due_at:due.value?new Date(due.value).toISOString():null,
    course_ids:scope.value==='cds'?courseBox.selected():[],member_ids:memberBox.selected(),responsibilities:assignments};
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
  const minimum=S.me.role==='admin'?12:8;
  const old=input('old','Password attuale','','password'),pw=input('new','Nuova password (almeno '+minimum+' caratteri)','','password'),again=input('again','Conferma nuova password','','password');
  f.append(field('Password attuale',old),field('Nuova password',pw),field('Conferma nuova password',again));
  f.append(el('button',{type:'submit',class:'btn primary',text:'Aggiorna password'}));
  f.addEventListener('submit',async e=>{
   e.preventDefault();if(pw.value!==again.value)return msg('Le password non coincidono',true);
   if(pw.value.length<minimum)return msg('Servono almeno '+minimum+' caratteri',true);
   try{await api('/profile/password',{method:'POST',body:JSON.stringify({current_password:old.value,new_password:pw.value})});back.remove();alert('Password aggiornata. Accedi nuovamente.');location.reload()}catch(error){msg(error.message,true)}
  });box.append(f);
 }
 function resetPassword(u){
  const {box,back}=modal('Reimposta password — '+u.display_name);
  box.append(node('p','sub','La password attuale non è visibile. Dopo la modifica tutte le sessioni di questo utente saranno revocate.'));
  const minimum=u.role==='admin'?12:8;
  const pw=input('pw','Nuova password (almeno '+minimum+' caratteri)','','password');
  box.append(field('Nuova password',pw),opt('Reimposta password',async()=>{
   if(pw.value.length<minimum)return msg('Servono almeno '+minimum+' caratteri',true);
   if(!confirm('Reimpostare la password per '+u.display_name+'?'))return;
   try{await api('/admin/users/'+u.id+'/password',{method:'POST',body:JSON.stringify({new_password:pw.value})});back.remove();msg('Password reimpostata')}catch(e){msg(e.message,true)}
  },'primary'));
 }
 function editAccount(u){
  const {box,back}=modal('Gestisci account — '+u.display_name);
  const role=select('role',[['user','Utente'],['admin','Amministratore']],u.role);
  const active=el('input',{type:'checkbox',checked:!!u.active});
  const promotion=el('input',{class:'field',type:'password',placeholder:'Nuova password amministratore (almeno 12 caratteri)',autocomplete:'new-password'});
  const promotionField=field('Nuova password obbligatoria se promuovi un utente ad amministratore',promotion);
  const update=()=>{promotionField.hidden=!(u.role!=='admin'&&role.value==='admin')};
  role.addEventListener('change',update);update();
  box.append(field('Ruolo',role),el('label',{},[active,' Account attivo']),promotionField,opt('Salva',async()=>{
   const promoting=u.role!=='admin'&&role.value==='admin';
   if(promoting&&promotion.value.length<12)return msg('Per promuovere un utente servono almeno 12 caratteri',true);
   const data={role:role.value,active:active.checked};
   if(promoting)data.promotion_password=promotion.value;
   try{await api('/admin/users/'+u.id,{method:'PUT',body:JSON.stringify(data)});back.remove();await refresh();render();msg('Account aggiornato')}catch(e){msg(e.message,true)}
  },'primary'));
 }
 return {projectView,projectForm,courseAssignmentForm,courseAdminButton,settings,taskScopeOptions,scopedCourses};
})();
