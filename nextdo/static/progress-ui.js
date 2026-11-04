'use strict';
/* Dashboard views of featured project timelines and personal work updates. */
const NextDoProgress=(()=>{
 function activeTasks(){
  const ids=new Set(S.projects.map(p=>p.id));
  return S.tasks.filter(t=>t.kind==='task'&&t.scope==='project'&&ids.has(t.project_id)&&(
   t.assigned_to===S.me.id||(t.assigned_to==null&&t.owner_id===S.me.id)
  ));
 }
 function dashboard(main){
  const featured=S.projects.filter(p=>p.featured!==0);
  const mine=activeTasks().sort((a,b)=>(a.status==='done')-(b.status==='done')||(a.due_at||'9999').localeCompare(b.due_at||'9999'));
  if(!featured.length&&!mine.length)return;
  const section=el('section',{class:'card dashboard-work'});
  const head=el('div',{class:'card-head dashboard-work-title'},[
   node('h2','','I miei progetti e avanzamenti'),
   btn('Apri Progetti',()=>changeView('projects'),'small')
  ]);
  section.append(head);
  if(mine.length){
   const tracker=el('div',{class:'dashboard-assigned'});
   tracker.append(node('h3','','Le mie attività di progetto'));
   for(const t of mine){
    const p=S.projects.find(x=>x.id===t.project_id);
    const row=el('div',{class:'dashboard-assigned-row'});
    const name=el('button',{type:'button',class:'dashboard-assigned-name',onclick:()=>taskForm(t)},[
     node('strong','',t.title),
     node('span','muted',(p?.title||'Progetto')+' · '+(t.due_at?fmt(t.due_at):'Senza scadenza'))
    ]);
    const status=tag(statuses[t.status]||t.status,t.status);
    row.append(name,status);
    if(t.can_edit!==false||t.can_complete)row.append(btn('Aggiorna',()=>open(t),'small'));
    else row.append(btn('Dettagli',()=>taskForm(t),'small'));
    tracker.append(row);
   }
   section.append(tracker);
  }
  if(featured.length){
   const intro=el('div',{class:'dashboard-gantt-heading'},[
    node('h3','','Gantt dei progetti in evidenza'),
    node('p','sub','I cronoprogrammi mostrano i progetti accessibili al tuo account. Seleziona un’attività per aggiornare la scheda.')
   ]);
   section.append(intro);
   for(const p of featured){
    const wrap=el('section',{class:'dashboard-project-gantt'});
    const count=Object.values(p.counts||{}).reduce((a,b)=>a+b,0);
    const done=p.counts?.done||0;
    const h=el('div',{class:'dashboard-project-header'},[
     node('h4','',p.title),
     node('span','muted',count?done+' / '+count+' completate':'Nessuna attività'),
     btn('Apri Kanban',()=>{S.selectedProject=p.id;S.projectMode='kanban';changeView('projects')},'small')
    ]);
    wrap.append(h);
    wrap.append(NextDoGantt.render(p));
    section.append(wrap);
   }
  }
  main.append(section);
 }
 function open(task){
  const {box,back}=modal('Aggiorna attività — '+task.title);
  box.classList.add('progress-dialog');
  const project=S.projects.find(p=>p.id===task.project_id);
  if(project)box.append(node('p','sub','Progetto: '+project.title));
  const form=el('form',{class:'formgrid'});
  const st=select('progress-status',Object.entries(statuses),task.status);
  const note=el('textarea',{class:'field',rows:'3',maxlength:'1500',placeholder:'Aggiornamento del lavoro svolto, eventuali impedimenti, documenti predisposti…','aria-label':'Nota di avanzamento'});
  const scopedCourse=task.completion_mode==='per_course'&&task.courses?.length;
  if(scopedCourse){
   const alert=node('p','sub','Per completare una scadenza comune, conferma il completamento del singolo CdS nella scheda dell’attività.');
   form.append(alert);
  }
  form.append(field('Stato dell’attività',st),el('div',{class:'full'},[field('Breve aggiornamento (facoltativo se cambi stato)',note)]));
  const history=el('div',{class:'progress-history full'});
  history.append(node('h3','','Storico degli aggiornamenti'));
  const list=el('div',{class:'progress-history-list'},[node('p','muted','Caricamento…')]);
  history.append(list);
  api('/tasks/'+task.id+'/progress').then(items=>{
   list.replaceChildren();
   if(!items.length){list.append(node('p','muted','Nessun aggiornamento registrato.'));return}
   for(const item of items){
    const event=el('div',{class:'progress-history-event'},[
     node('strong','',item.actor),
     node('span','muted',fmt(item.created_at.endsWith('Z')?item.created_at:item.created_at.replace(' ','T')+'Z')),
     node('span','',item.old_status===item.new_status?(statuses[item.new_status]||item.new_status):(statuses[item.old_status]||item.old_status)+' → '+(statuses[item.new_status]||item.new_status))
    ]);
    if(item.note)event.append(node('p','',item.note));
    list.append(event);
   }
  }).catch(err=>{list.replaceChildren(node('p','muted',err.message))});
  const actions=el('div',{class:'actions full'},[
   btn('Apri scheda',()=>{back.remove();taskForm(task)},'small'),
   el('button',{class:'btn primary',type:'submit',text:'Salva aggiornamento'})
  ]);
  if(task.can_edit===false){
   st.disabled=true;note.disabled=true;actions.lastChild.disabled=true;
   form.append(node('p','sub','Non hai i permessi per aggiornare questa attività.'));
  }
  form.append(history,actions);
  form.addEventListener('submit',async e=>{
   e.preventDefault();
   const save=actions.lastChild;save.disabled=true;
   try{
    await api('/tasks/'+task.id+'/progress',{method:'POST',body:JSON.stringify({status:st.value,note:note.value})});
    back.remove();await refresh();render();msg('Avanzamento aggiornato');
   }catch(err){save.disabled=false;msg(err.message,true)}
  });
  box.append(form);
 }
 return {dashboard,open};
})();
