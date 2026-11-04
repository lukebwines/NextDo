'use strict';
/* NextDo project Gantt. Local rendering only; no external JS dependency.
   Dates are shown in the application's Europe/Rome timezone and all DOM is created
   with safe text nodes instead of string HTML. */
const NextDoGantt=(()=>{
 const DAY=86400000;
 const localDate=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'});
 const monthName=new Intl.DateTimeFormat('it-IT',{timeZone:'UTC',month:'long',year:'numeric'});
 function utcDay(raw){
  if(!raw)return null;
  const dt=new Date(raw);if(!Number.isFinite(dt.getTime()))return null;
  const parts=Object.fromEntries(localDate.formatToParts(dt).filter(x=>x.type!=='literal').map(x=>[x.type,Number(x.value)]));
  return Math.floor(Date.UTC(parts.year,parts.month-1,parts.day)/DAY);
 }
 function printable(day){
  const d=new Date(day*DAY);
  return String(d.getUTCDate()).padStart(2,'0')+'/'+String(d.getUTCMonth()+1).padStart(2,'0');
 }
 function monday(day){
  const w=new Date(day*DAY).getUTCDay();
  return day-((w+6)%7);
 }
 function beginningOfMonth(day){
  const d=new Date(day*DAY);
  return Math.floor(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),1)/DAY);
 }
 function nextMonth(day){
  const d=new Date(day*DAY);
  return Math.floor(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,1)/DAY);
 }
 function labelForDate(day){return monthName.format(new Date(day*DAY));}
 function addTick(track,left,kind,caption){
  return el('span',{class:'gantt-marker-line '+kind,style:'left:'+left+'px',title:caption,'aria-hidden':'true'});
 }
 function legend(){
  return el('div',{class:'gantt-legend'},[
   el('span',{},[el('i',{class:'gantt-key gantt-key--doing'}),' In corso']),
   el('span',{},[el('i',{class:'gantt-key gantt-key--waiting'}),' In attesa']),
   el('span',{},[el('i',{class:'gantt-key gantt-key--done'}),' Completata']),
   el('span',{},[el('i',{class:'gantt-key gantt-key--milestone'}),' Scadenza puntuale']),
   el('span',{},[el('i',{class:'gantt-key gantt-key--today'}),' Oggi']),
   el('span',{},[el('i',{class:'gantt-key gantt-key--deadline'}),' Termine progetto'])
  ]);
 }
 function draw(project){
  const section=el('div',{class:'gantt-section'});
  const tasks=S.tasks.filter(t=>t.project_id===project.id&&t.kind==='task');
  const planned=tasks.map(t=>({task:t,start:utcDay(t.start_at),end:utcDay(t.due_at)})).filter(t=>t.start!==null||t.end!==null);
  const unplanned=tasks.filter(t=>!t.start_at&&!t.due_at);
  const toolbar=el('div',{class:'gantt-controls'});
  toolbar.append(node('strong','','Cronoprogramma'),node('span','muted',planned.length+' pianificate · '+unplanned.length+' da pianificare'));
  const scale=select('gantt-zoom',[['overview','Panoramica'],['normal','Settimane'],['detail','Dettaglio']],S.ganttZoom||'normal');
  scale.setAttribute('aria-label','Scala temporale Gantt');
  scale.addEventListener('change',()=>{S.ganttZoom=scale.value;localStorage.setItem('nextdo-gantt-zoom',scale.value);renderProjectAgain()});
  toolbar.append(field('Scala',scale));section.append(toolbar);
  section.append(legend());
  if(!planned.length&&!project.due_at){
   section.append(node('p','empty','Nessuna attività con date. Apri una scheda e inserisci la data di inizio e/o la scadenza.'));
   if(unplanned.length)addUnplanned();
   return section;
  }
  const dates=planned.flatMap(t=>[t.start,t.end].filter(v=>v!==null));
  const projectDue=utcDay(project.due_at);if(projectDue!==null)dates.push(projectDue);
  const min=Math.min(...dates),max=Math.max(...dates);
  const leftBound=monday(min-7),rightBound=Math.max(leftBound+35,max+10);
  const days=rightBound-leftBound+1;
  if(days>3653){
   section.append(node('p','empty','Il progetto contiene date distanti più di 10 anni: verifica le schede o utilizza la vista Kanban per correggerle. Non sono state modificate le attività.'));
   for(const {task:t} of planned)section.append(el('button',{type:'button',class:'gantt-open-task',onclick:()=>taskForm(t)},[t.title+' — '+(t.due_at?fmt(t.due_at):'Fine da definire')]));
   if(unplanned.length)addUnplanned();
   return section;
  }
  const widthPerDay={overview:8,normal:14,detail:24}[S.ganttZoom]||14;
  const width=days*widthPerDay;
  const today=utcDay(new Date().toISOString());
  const scroller=el('div',{class:'gantt-scroll',role:'region','aria-label':'Cronoprogramma del progetto: scorrimento orizzontale',tabindex:'0'});
  const grid=el('div',{class:'gantt-grid',style:'--gantt-days-width:'+width+'px;--gantt-week-width:'+(widthPerDay*7)+'px'});
  const header=el('div',{class:'gantt-row gantt-heading'});
  header.append(el('div',{class:'gantt-name'},[node('strong','','Attività / referente')]));
  const htrack=el('div',{class:'gantt-track gantt-head-track'});
  const months=el('div',{class:'gantt-months'});
  for(let c=beginningOfMonth(leftBound);c<=rightBound;c=nextMonth(c)){
   const first=Math.max(c,leftBound),last=Math.min(nextMonth(c),rightBound+1);
   if(last<=first)continue;
   months.append(el('div',{class:'gantt-month',style:'left:'+((first-leftBound)*widthPerDay)+'px;width:'+((last-first)*widthPerDay)+'px'},[labelForDate(c)]));
  }
  const weeks=el('div',{class:'gantt-weeks'});
  for(let c=monday(leftBound);c<=rightBound;c+=7){
   if(c<leftBound)continue;
   weeks.append(el('span',{class:'gantt-week-label',style:'left:'+((c-leftBound)*widthPerDay)+'px'},[printable(c)]));
  }
  htrack.append(months,weeks);
  if(today!==null&&today>=leftBound&&today<=rightBound)htrack.append(addTick(htrack,(today-leftBound)*widthPerDay,'gantt-today','Oggi'));
  if(projectDue!==null&&projectDue>=leftBound&&projectDue<=rightBound)htrack.append(addTick(htrack,(projectDue-leftBound)*widthPerDay,'gantt-project-deadline','Scadenza del progetto: '+fmt(project.due_at)));
  header.append(htrack);grid.append(header);
  planned.sort((a,b)=>(a.start??a.end)-(b.start??b.end)||(a.end??a.start)-(b.end??b.start));
  for(const {task:t,start,end} of planned){
   const row=el('div',{class:'gantt-row'});
   const person=S.users.find(u=>u.id===t.assigned_to);
   const subtitle=person?.display_name||'Senza assegnatario';
   const label=el('button',{type:'button',class:'gantt-name gantt-task-label',onclick:()=>taskForm(t),title:'Apri scheda: '+t.title},[
    node('strong','',t.title),
    node('span','gantt-subtitle',subtitle+' · '+(statuses[t.status]||t.status))
   ]);
   const track=el('div',{class:'gantt-track gantt-body-track'});
   if(today!==null&&today>=leftBound&&today<=rightBound)track.append(addTick(track,(today-leftBound)*widthPerDay,'gantt-today','Oggi'));
   if(projectDue!==null&&projectDue>=leftBound&&projectDue<=rightBound)track.append(addTick(track,(projectDue-leftBound)*widthPerDay,'gantt-project-deadline','Scadenza del progetto'));
   const first=start??end,last=end??start;
   const milestone=start===null||end===null||first===last;
   const dateInfo=(start===null?'Inizio da definire':'Inizio: '+fmt(t.start_at))+' · '+(end===null?'Fine da definire':'Scadenza: '+fmt(t.due_at));
   const tooltip=t.title+' · '+(statuses[t.status]||t.status)+' · '+subtitle+' · '+dateInfo;
   const bar=el('button',{
    type:'button',class:'gantt-bar gantt-bar--'+t.status+(milestone?' gantt-milestone':''),
    style:'left:'+((first-leftBound)*widthPerDay+(milestone?-4:2))+'px;width:'+(milestone?12:Math.max(12,(last-first+1)*widthPerDay-4))+'px',
    title:tooltip,'aria-label':tooltip,onclick:()=>taskForm(t)
   });
   if(!milestone&&last-first>5)bar.append(node('span','',statuses[t.status]||t.status));
   track.append(bar);row.append(label,track);grid.append(row);
  }
  scroller.append(grid);section.append(scroller);
  section.append(node('p','sub','Le barre mostrano il periodo pianificato; i rombi indicano una sola data. I colori rappresentano lo stato, non una percentuale di avanzamento. Seleziona una barra per modificare le date o aprire la scheda.'));
  if(unplanned.length)addUnplanned();
  return section;
  function addUnplanned(){
   const summary=el('details',{class:'gantt-unplanned',open:!planned.length});
   summary.append(el('summary',{},['Da pianificare ('+unplanned.length+')']));
   for(const t of unplanned)summary.append(el('div',{class:'gantt-unplanned-row'},[
    el('button',{type:'button',class:'gantt-open-task',onclick:()=>taskForm(t)},[t.title]),
    node('span','muted',statuses[t.status]||t.status),
    el('button',{type:'button',class:'btn small',onclick:()=>taskForm(t)},['Inserisci date'])
   ]));
   section.append(summary);
  }
 }
 function renderProjectAgain(){if(S.view==='projects'||S.view==='dashboard')render()}
 return {render:draw};
})();
