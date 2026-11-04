'use strict';
const S={me:null,csrf:'',tasks:[],courses:[],groups:[],users:[],view:'dashboard',editing:null,month:new Date(),light:localStorage.getItem('nextdo-light')==='1',listPreset:'all',labelFilter:'',searchTerm:'',projects:[],courseAssignees:[],collaborators:[],courseCollaborators:[],myCourseIds:[],selectedProject:null,projectMode:localStorage.getItem('nextdo-project-view')==='gantt'?'gantt':'kanban',ganttZoom:localStorage.getItem('nextdo-gantt-zoom')||'normal'};
const $=id=>document.getElementById(id), priority={low:'Bassa',normal:'Normale',high:'Alta',critical:'Critica'}, statuses={todo:'Da fare',doing:'In corso',waiting:'In attesa',done:'Completata'};
function el(tag,attrs={},children=[]){const n=document.createElement(tag);for(const [k,v] of Object.entries(attrs)){if(k==='class')n.className=v;else if(k==='text')n.textContent=v;else if(k==='html')throw Error('Unsafe HTML');else if(k.startsWith('on'))n.addEventListener(k.slice(2),v);else if(k==='value')n.value=v;else if(k==='checked')n.checked=!!v;else if(k==='style')n.setAttribute('style',v);else n.setAttribute(k,v)}for(const c of (Array.isArray(children)?children:[children]))if(c!=null)n.append(typeof c==='string'?document.createTextNode(c):c);return n}
function node(tag,cls,txt){return el(tag,{class:cls,text:txt})}
function msg(t,error=false){const d=el('div',{class:'notice'+(error?' error':'')},[t]);document.body.append(d);setTimeout(()=>d.remove(),5000)}
async function api(path,opts={}){let headers={'X-NextDo-CSRF':S.csrf,...(opts.headers||{})};if(opts.body&&!(opts.body instanceof FormData))headers['Content-Type']='application/json';const res=await fetch('api'+path,{credentials:'same-origin',...opts,headers});if(!res.ok){let d;try{d=await res.json()}catch{}throw Error(typeof d?.detail==='string'?d.detail:`Errore HTTP ${res.status}`)}return res.headers.get('content-type')?.includes('application/json')?res.json():res}
const opt=(v,t)=>el('option',{value:v,text:t});const input=(name,placeholder='',value='',type='text')=>el('input',{class:'field',name,placeholder,value,type});
const field=(title,control)=>el('div',{},[node('label','label',title),control]);
const select=(name,options,value='')=>{const s=el('select',{class:'field',name});for(const [v,t] of options)s.append(opt(v,t));s.value=value??'';return s};
const wrap=(...x)=>el('div',{},x);const btn=(text,fn,cls='')=>el('button',{type:'button',class:'btn '+cls,onclick:fn,text});
function fmt(d){if(!d)return 'Senza data';const dt=new Date(d);return isNaN(dt)?d:dt.toLocaleString('it-IT',{dateStyle:'medium',timeStyle:'short'})}
function tag(text,cls=''){return node('span','pill '+cls,text)}
function today(){return new Date().toISOString().slice(0,10)}
function dtLocal(raw){if(!raw)return '';const d=new Date(raw);if(isNaN(d))return raw.slice(0,16);const z=new Date(d.getTime()-d.getTimezoneOffset()*60000);return z.toISOString().slice(0,16)}
async function init(){document.body.classList.toggle('light',S.light);const csrf=await api('/csrf');S.csrf=csrf.csrf;const setup=await api('/setup');if(setup.needs_setup)return loginView(true);try{S.me=await api('/me');await refresh();render()}catch{loginView(false)}}
function loginView(setup){const box=el('form',{class:'authbox'});box.append(node('div','logo','✓ NextDo'),node('h1','',setup?'Prima configurazione':'Accedi'),node('p','sub',setup?'Crea il primo account amministratore. La password deve avere almeno 12 caratteri.':'Usa le credenziali personali NextDo.'));const u=input('username','Nome utente');const p=input('password','Password','','password');box.append(field('Nome utente',u));if(setup)box.append(field('Nome visualizzato',input('display_name','Nome visualizzato')));box.append(field('Password',p));if(setup)box.append(field('Codice installazione (visibile nei log NextDo)',input('setup_token','Codice locale di prima attivazione')));const submit=el('button',{class:'btn primary',type:'submit',style:'width:100%;margin-top:20px',text:setup?'Crea amministratore':'Accedi'});box.append(submit);box.addEventListener('submit',async e=>{e.preventDefault();try{const data=Object.fromEntries(new FormData(box));if(setup){await api('/setup',{method:'POST',body:JSON.stringify(data)});msg('Amministratore creato: effettua l’accesso');loginView(false)}else{await api('/login',{method:'POST',body:JSON.stringify({...data,display_name:''})});S.me=await api('/me');await refresh();render()}}catch(e){msg(e.message,true)}});$('app').replaceChildren(box)}
async function refresh(){
 const out=await Promise.all([api('/tasks'),api('/courses'),api('/groups'),api('/users'),api('/projects'),api('/my-courses')]);
 [S.tasks,S.courses,S.groups,S.users,S.projects,S.myCourseIds]=out;
 S.courseAssignees=await api('/course-assignee-defaults');
 [S.collaborators,S.courseCollaborators]=await Promise.all([api('/collaborators'),api('/course-collaborators')]);
}
const iconDefs={paperclip:['M21.44 11.05l-8.49 8.49a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.41 17.4a2 2 0 0 1-2.83-2.83l8.49-8.49'],check:['M9 11l3 3L22 4','M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11'],home:['M3 10l9-7 9 7','M5 9v12h14V9','M9 21v-8h6v8'],list:['M8 6h13','M8 12h13','M8 18h13','M3 6h.01','M3 12h.01','M3 18h.01'],calendar:['M8 2v4','M16 2v4','M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2z'],note:['M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8l-5-5H8z','M16 3v5h5','M8 13h8','M8 17h5'],archive:['M3 4h18v5H3z','M5 9v12h14V9','M10 13h4'],settings:['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8','M4 12a8 8 0 0 1 16 0 8 8 0 0 1-16 0'],bell:['M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9','M10 21h4'],search:['M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16','M21 21l-4.35-4.35'],user:['M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2','M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8'],clock:['M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20','M12 6v6l4 2'],alert:['M12 3L2 21h20L12 3z','M12 9v4','M12 17h.01'],tag:['M3 3h8l10 10-8 8L3 11V3z','M7 7h.01'],plus:['M12 5v14','M5 12h14'],chevron:['M9 18l6-6-6-6']};
function ico(name,cls=''){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','2');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');svg.setAttribute('class','ico '+cls);svg.setAttribute('aria-hidden','true');for(const d of iconDefs[name]||iconDefs.check){const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',d);svg.append(p)}return svg}
function changeView(view,preset='all',label='',projectId=null){if(view==='projects')S.selectedProject=projectId;S.view=view;S.listPreset=preset;S.labelFilter=label;render()}
function render(){
 const app=$('app');app.replaceChildren();
 const layout=el('div',{class:'app'}),sidebar=el('aside',{class:'sidebar'}),main=el('main',{class:'main'});
 const logo=el('div',{class:'logo'},[el('span',{class:'brandmark'},[ico('check')]),el('span',{},[node('span','name','NextDo'),node('small','brand-sub','Tasks, Notes & Deadlines')])]);
 sidebar.append(logo);
 const navs=[['dashboard','home','Dashboard'],['mine','note','Il mio spazio'],['tasks','list','Scadenze'],['projects','archive','Progetti'],['calendar','calendar','Calendario'],['notes','note','Note'],['courses','calendar','Corsi di Studio'],['archive','archive','Archivio'],['settings','settings','Impostazioni']];
 for(const [id,icon,title] of navs)sidebar.append(el('button',{class:'nav '+(S.view===id?'active':''),onclick:()=>changeView(id)},[ico(icon),node('span','navtext',title)]));
 const labels=[...new Set(S.tasks.flatMap(t=>t.labels||[]))].sort((a,b)=>a.localeCompare(b,'it')).slice(0,12);
 const labelBox=el('div',{class:'sidebar-labels'},[node('div','sidebar-labels-heading','Etichette')]);
 if(!labels.length)labelBox.append(node('p','sidebar-empty','Nessuna etichetta'));
 labels.forEach((label,i)=>labelBox.append(el('button',{class:'label-link',onclick:()=>changeView('tasks','all',label)},[el('span',{class:'label-dot',style:'--dot-color:'+['#8c83ff','#f87283','#58cdbb','#ffad55','#48c4ff'][i%5]}),node('span','',label)])));
 sidebar.append(labelBox);
 sidebar.append(el('div',{class:'bottom'},[node('div','muted labeltext',S.me.display_name),btn('Esci',async()=>{await api('/logout',{method:'POST'});S.me=null;loginView(false)},'small')]));
 layout.append(sidebar,main);app.append(layout);
 const toolbar=el('div',{class:'appbar'});
 const search=el('form',{class:'global-search'},[ico('search'),input('global-search','Cerca attività e note...',S.searchTerm)]);
 search.addEventListener('submit',e=>{e.preventDefault();S.searchTerm=search.querySelector('input').value;changeView('tasks')});
 toolbar.append(search,el('button',{type:'button',class:'iconbutton',title:'Notifiche',onclick:()=>changeView('settings')},[ico('bell')]),el('button',{type:'button',class:'iconbutton',title:'Profilo e impostazioni',onclick:()=>changeView('settings')},[ico('user')]));
 main.append(toolbar);
 const titles={dashboard:'Dashboard',mine:'Il mio spazio',tasks:'Scadenze',projects:'Progetti',notes:'Note',calendar:'Calendario',courses:'Corsi di Studio',groups:'Gruppi',archive:'Archivio',settings:'Impostazioni'};
 const header=el('div',{class:'top'},[el('div',{},[node('h1','',titles[S.view]),node('div','sub',S.view==='dashboard'?'Panoramica delle tue attività':'Organizza le attività, rispetta le scadenze.')]),el('div',{class:'top-actions'},[btn(S.light?'☀ Tema':'☾ Tema',()=>{S.light=!S.light;localStorage.setItem('nextdo-light',S.light?'1':'0');document.body.classList.toggle('light',S.light)},'small'),btn('+ Nuova',()=>taskForm(),'primary')])]);
 main.append(header);
 if(S.view==='dashboard')dashboard(main);else if(['tasks','notes','archive','mine'].includes(S.view))taskList(main,S.view);else if(S.view==='projects')NextDoWorkspace.projectView(main);else if(S.view==='calendar')calendar(main);else if(S.view==='courses')coursesView(main);else if(S.view==='groups')groupsView(main);else settings(main);
}
function taskrow(t){const row=el('div',{class:'rowtask'});const cb=el('input',{type:'checkbox',checked:t.status==='done',title:'Completa attività'});if(t.can_complete===false)cb.disabled=true;cb.addEventListener('change',async()=>{try{if(t.completion_mode==='per_course'&&t.courses.length){taskForm(t);cb.checked=t.status==='done';return}await api(`/tasks/${t.id}/toggle`,{method:'POST'});await refresh();render()}catch(e){msg(e.message,true)}});const main=el('div',{class:'taskmain'},[node('div','tasktitle',t.title),el('div',{},[node('span','muted',fmt(t.due_at)+' · '),tag(priority[t.priority],t.priority),...t.courses.slice(0,3).map(c=>tag(c.code)),...(t.labels||[]).slice(0,2).map(x=>tag(x))])]);const edit=btn('Apri',()=>taskForm(t),'small');row.append(cb,main,edit);return row}
function dashboard(main){
 main.classList.add('dashboard-page');
 const pending=S.tasks.filter(t=>t.kind==='task'&&t.status!=='done');
 const urgent=pending.filter(t=>['high','critical'].includes(t.priority));
 const late=pending.filter(t=>t.due_at&&new Date(t.due_at)<new Date());
 const done=S.tasks.filter(t=>t.kind==='task'&&t.status==='done');
 const metrics=[['Da gestire',pending.length,'calendar','all'],['Urgenti',urgent.length,'alert','urgent'],['Scadute',late.length,'clock','overdue'],['Completate',done.length,'check','done']];
 const summary=el('div',{class:'dash-metrics'});
 metrics.forEach(([name,n,icon,preset],index)=>summary.append(el('button',{type:'button',class:'metric metric-'+index,onclick:()=>changeView(preset==='done'?'archive':'tasks',preset),'aria-label':name+': '+n+' attività, apri elenco filtrato'},[el('span',{class:'metric-icon'},[ico(icon)]),node('span','metric-label',name),node('strong','metric-value',String(n))])));
 main.append(summary);
 const board=el('div',{class:'dash-layout'});const left=el('section',{class:'card dash-upcoming'});
 left.append(el('div',{class:'card-head'},[node('h2','','Prossime scadenze'),btn('Vedi tutte ›',()=>changeView('tasks'),'textlink')]));
 for(const t of [...pending].sort((a,b)=>(a.due_at||'9999').localeCompare(b.due_at||'9999')).slice(0,6)){
  const row=el('div',{class:'dash-task-row '+(t.priority||'normal')});
  const checkbox=el('input',{type:'checkbox',title:'Completa attività'});
  checkbox.addEventListener('change',async()=>{if(t.completion_mode==='per_course'&&t.courses.length){taskForm(t);checkbox.checked=false;return}try{await api('/tasks/'+t.id+'/toggle',{method:'POST'});await refresh();render()}catch(e){checkbox.checked=false;msg(e.message,true)}});
  const details=el('button',{type:'button',class:'dash-task-title',onclick:()=>taskForm(t)},[node('span','dash-task-name',t.title),el('span',{class:'dash-task-meta'},[...(t.labels||[]).slice(0,1).map(v=>tag(v,'label-tag')),tag(priority[t.priority]||'Normale',t.priority),node('span','dash-due',fmt(t.due_at))])]);
  row.append(checkbox,details);left.append(row);
 }
 if(!pending.length)left.append(node('div','empty','Nessuna attività in sospeso'));
 const quick=el('section',{class:'card dash-quick'});quick.append(el('div',{class:'card-head'},[ico('plus'),node('h2','','Aggiunta rapida')]));
 const compose=el('textarea',{class:'field dash-compose',rows:'3',placeholder:'Incolla una nota, un’email o scrivi un’attività...','aria-label':'Testo per aggiunta rapida'});
 const pr=select('quick-priority',Object.entries(priority),'normal');pr.setAttribute('aria-label','Priorità');
 const makeQuick=()=>{
  const text=compose.value.trim();
  return {title:text.split('\n')[0].slice(0,250),description:text,priority:pr.value};
 };
 const tool=(name,label,fn)=>el('button',{type:'button',class:'btn icon-small quick-tool',title:label,'aria-label':label,onclick:fn},[ico(name)]);
 const quickFileInput=el('input',{type:'file',accept:NextDoFileUI.accept,multiple:true,hidden:true});
 quickFileInput.addEventListener('change',()=>{
  const result=NextDoFileUI.validate(quickFileInput.files);
  if(result.errors.length)msg(result.errors.join('; '),true);
  if(result.files.length)taskForm(null,'task',makeQuick(),{files:result.files,focus:'attachments'});
  quickFileInput.value='';
 });
 const actions=el('div',{class:'quick-actions'},[
  tool('paperclip','Allega documenti alla nuova attività',()=>quickFileInput.click()),
  tool('calendar','Imposta la data della nuova scadenza',()=>taskForm(null,'task',makeQuick(),{focus:'due'})),
  tool('tag','Assegna etichette alla nuova attività',()=>taskForm(null,'task',makeQuick(),{focus:'labels'})),
  pr,
  btn('Aggiungi',async()=>{
   const text=compose.value.trim();if(!text){compose.focus();return}
   try{
    await api('/tasks',{method:'POST',body:JSON.stringify({title:text.split('\n')[0].slice(0,250),description:text,kind:'task',priority:pr.value})});
    await refresh();render();msg('Attività aggiunta');
   }catch(e){msg(e.message,true)}
  },'primary')
 ]);
 quick.append(compose,actions,quickFileInput);
 NextDoFileUI.quickDrop(quick,files=>taskForm(null,'task',makeQuick(),{files,focus:'attachments'}),message=>msg(message,true));
 const extract=el('button',{type:'button',class:'extract-action',onclick:pasteForm},[ico('note'),el('span',{},[node('strong','','Incolla e crea scadenze'),node('small','','NextDo riconosce date e priorità; conferma prima di salvare')]),ico('chevron')]);
 const right=el('div',{class:'dash-right'},[quick,extract]);board.append(left,right);main.append(board);
 const lower=el('div',{class:'dash-bottom'});const week=el('section',{class:'card dash-week'});week.append(node('h2','','In arrivo questa settimana'));
 const weekRow=el('div',{class:'week-row'});const base=new Date();base.setHours(0,0,0,0);
 for(let i=0;i<7;i++){const date=new Date(base);date.setDate(base.getDate()+i);const dayString=[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');const daily=pending.filter(t=>t.due_at&&dtLocal(t.due_at).slice(0,10)===dayString);const tile=el('button',{type:'button',class:'week-day '+(i===0?'today':''),onclick:()=>changeView('tasks')},[node('span','',date.toLocaleDateString('it-IT',{weekday:'short'})),node('strong','',String(date.getDate())),node('span','week-dots',daily.length?'● '.repeat(Math.min(daily.length,3)):'·')]);weekRow.append(tile)}week.append(weekRow);
 const groups=new Map();for(const t of pending)for(const label of t.labels||[])groups.set(label,(groups.get(label)||0)+1);
 const count=[...groups.entries()].sort((a,b)=>b[1]-a[1]).slice(0,5);const breakdown=el('section',{class:'card dash-breakdown'});breakdown.append(node('h2','','Distribuzione per etichetta'));
 const chart=el('div',{class:'breakdown-inner'});const colors=['#8e80ff','#409bff','#51d8a2','#ffad43','#5dc6ea'];const all=count.reduce((n,v)=>n+v[1],0);let pct=0;const segments=count.map(([name,n],i)=>{const first=pct;pct+=n/all*100;return colors[i]+' '+first+'% '+pct+'%'});
 const ring=el('div',{class:'donut',style:'background:'+(all?'conic-gradient('+segments.join(',')+')':'conic-gradient(#31465e 0 100%)')},[node('span','donut-count',String(pending.length)),node('span','donut-label','attività')]);
 const legend=el('div',{class:'chart-legend'});count.forEach(([name,num],i)=>legend.append(el('div',{class:'legend-row'},[el('span',{class:'legend-dot',style:'background:'+colors[i]}),node('span','',name),node('strong','',String(num))])));if(!count.length)legend.append(node('span','muted','Nessuna etichetta assegnata'));chart.append(ring,legend);breakdown.append(chart);lower.append(week,breakdown);main.append(lower);
 NextDoProgress.dashboard(main);
}
function taskList(main,view){const tools=el('div',{class:'toolbar'});const search=input('q','Cerca testo, attività o note…');const csel=select('course',[['','Tutti i CdS'],...S.courses.map(c=>[String(c.id),c.code+' — '+c.name])]);const gsel=select('group',[['','Tutti i gruppi'],...S.groups.map(g=>[String(g.id),g.name])]);const status=select('status',[['','Tutti gli stati'],...Object.entries(statuses)]);const preset=select('preset',[['all','Tutte'],['urgent','Urgenti'],['overdue','Scadute'],['done','Completate']],S.listPreset);search.value=S.searchTerm||'';tools.append(search,csel,gsel,status,preset);if(view==='notes')tools.append(btn('+ Nota',()=>taskForm(null,'note'),'primary'));if(view==='tasks'&&S.me.role==='admin')tools.append(btn('Importa calendario Excel',calendarImportForm,'small'));main.append(tools);const panel=el('section',{class:'card'});main.append(panel);function draw(){panel.replaceChildren();let tasks=S.tasks.filter(t=>view==='mine'?t.scope==='personal':view==='notes'?t.kind==='note':view==='archive'?t.status==='done':t.kind==='task'&&(t.status!=='done'||preset.value==='done'));tasks=tasks.filter(t=>(!search.value||(t.title+' '+t.description).toLowerCase().includes(search.value.toLowerCase()))&&(!csel.value||t.courses.some(c=>c.id==csel.value))&&(!gsel.value||t.group_id==gsel.value)&&(!status.value||t.status===status.value)&&(!S.labelFilter||(t.labels||[]).includes(S.labelFilter))&&(preset.value==='all'||(preset.value==='urgent'&&['high','critical'].includes(t.priority)&&t.status!=='done')||(preset.value==='overdue'&&t.due_at&&new Date(t.due_at)<new Date()&&t.status!=='done')||(preset.value==='done'&&t.status==='done')));panel.append(node('h2','',`${tasks.length} elementi`));if(!tasks.length)panel.append(node('p','empty','Nessun elemento trovato'));tasks.forEach(t=>panel.append(taskrow(t)))}for(const x of [search,csel,gsel,status,preset])x.addEventListener('input',draw);draw()}
function modal(title){const back=el('div',{class:'modalback'}),box=el('div',{class:'modal'});box.append(node('h2','',title));back.append(box);back.addEventListener('click',e=>{if(e.target===back)back.remove()});document.body.append(back);return {back,box}}
function checkboxes(title,values,selected=[]){const outer=el('div',{class:'full'}),region=el('div',{class:'checkboxes'});outer.append(node('label','label',title),region);for(const [v,l] of values){const cb=el('input',{type:'checkbox',value:String(v),checked:selected.includes(Number(v))});region.append(el('label',{},[cb,' '+l]))}return {outer,selected:()=>[...region.querySelectorAll('input:checked')].map(e=>Number(e.value))}}
function taskForm(t=null,kind='task',suggestion=null,preferences={}){
 const editing=!!t;
 let currentId=t?.id||null;
 const {box,back}=modal(editing?'Modifica attività o nota':'Nuova attività o nota');
 const form=el('form',{class:'formgrid'});
 const title=input('title','Titolo',t?.title||suggestion?.title||'');
 const desc=el('textarea',{class:'field',name:'description',rows:'5'});
 desc.value=t?.description||suggestion?.description||'';
 const type=select('kind',[['task','Scadenza / attività'],['note','Nota libera']],t?.kind||kind);
 const pr=select('priority',Object.entries(priority),t?.priority||suggestion?.priority||'normal');
 const st=select('status',Object.entries(statuses),t?.status||'todo');
 const due=input('due_at','',dtLocal(t?.due_at||suggestion?.due_at),'datetime-local');
 const start=input('start_at','',dtLocal(t?.start_at||suggestion?.start_at),'datetime-local');
 const rec=select('recurrence',[['none','Nessuna'],['daily','Giornaliera'],['weekly','Settimanale'],['monthly','Mensile'],['yearly','Annuale']],t?.recurrence||suggestion?.recurrence||'none');
 const grp=select('group_id',[['','Privata (nessun gruppo)'],...S.groups.map(g=>[String(g.id),g.name])],t?.group_id||'');
 const assigned=select('assigned_to',[['','Non assegnata'],...S.users.map(u=>[String(u.id),u.display_name])],t?.assigned_to||'');
 const mode=select('completion_mode',[['global','Completamento globale'],['per_course','Completamento separato per CdS']],t?.completion_mode||'global');
 const labels=input('labels','Es: AQ, delibere, urgente',(t?.labels||suggestion?.labels||[]).join(', '));
 const reminders=input('reminders','Es: 1440, 60 (minuti)',(t?.reminders||[]).join(', '));
 const display=el('input',{type:'checkbox',checked:t?.display_enabled});
 const scope=select('scope',NextDoWorkspace.taskScopeOptions(),t?.scope||preferences.scope||'personal');
 const project=select('project_id',[['','Seleziona un progetto'],...S.projects.map(p=>[String(p.id),p.title])],String(t?.project_id||preferences.project_id||''));
 const courses=checkboxes('Corsi di Studio interessati (selezione multipla)',NextDoWorkspace.scopedCourses().filter(c=>c.active).map(c=>[c.id,c.code+' — '+c.name]),(t?.courses||[]).map(c=>c.id));
 const courseWrap=el('div',{class:'full'},[courses.outer]);
 const projectWrap=el('div',{class:'full'},[field('Progetto',project),node('p','sub','I CdS destinatari e i colleghi responsabili si assegnano nella scheda del progetto: tutte le attività ne erediteranno le associazioni.')]);
 const groupWrap=el('div',{class:'full'},[field('Gruppo di condivisione',grp)]);
 const displayWrap=el('label',{class:'full'},[display,' Pubblica esplicitamente su NextDo Display (solo attività di gruppo)']);
 const modeWrap=el('div',{class:'full'},[field('Modalità di completamento',mode)]);
 function updateScope(){
  courseWrap.hidden=scope.value!=='cds';
  projectWrap.hidden=scope.value!=='project';
  groupWrap.hidden=scope.value!=='group';
  displayWrap.hidden=scope.value!=='group';
  modeWrap.hidden=!['cds','common','group'].includes(scope.value);
 }
 scope.addEventListener('change',updateScope);
 form.append(field('Titolo *',title),field('Tipologia',type),el('div',{class:'full'},[field('Descrizione / nota',desc)]),field('Priorità',pr),field('Stato',st),field('Inizio previsto (facoltativo)',start),field('Data e ora scadenza',due),field('Ricorrenza',rec),field('Ambito / visibilità',scope),courseWrap,projectWrap,groupWrap,field('Responsabile',assigned),modeWrap,field('Etichette (separate da virgola)',labels),field('Promemoria in minuti prima della scadenza',reminders),displayWrap);
 updateScope();
 if(t?.completion_mode==='per_course'&&t.courses.length){
  const section=el('div',{class:'full card'},[node('h2','','Completamento per CdS')]);
  for(const c of t.courses)if(S.me.role==='admin'||S.myCourseIds.includes(c.id))section.append(el('div',{class:'rowtask'},[
   node('div','taskmain',c.code+' — '+c.name),tag(c.done?'Completato':'Da completare',c.done?'low':'high'),
   btn(c.done?'Riapri':'Completa',async()=>{try{await api('/tasks/'+t.id+'/complete/'+c.id,{method:'POST'});back.remove();await refresh();taskForm(S.tasks.find(x=>x.id===t.id))}catch(e){msg(e.message,true)}},'small')
  ]));
  form.append(section);
 }
 const attachments=el('div',{class:'full card attachment-card'});
 const existing=el('div',{class:'attachment-existing'});
 if(t?.attachments?.length){
  existing.append(node('p','sub','Allegati già salvati'));
  for(const a of t.attachments){
   const row=el('div',{class:'rowtask'});
   const anchor=el('a',{href:'api/attachments/'+a.id,download:a.filename,text:'Scarica'});
   const remove=btn('Rimuovi',async()=>{
    if(!confirm('Eliminare l\'allegato '+a.filename+'?'))return;
    try{await api('/attachments/'+a.id,{method:'DELETE'});row.remove();await refresh();msg('Allegato eliminato')}catch(e){msg(e.message,true)}
   },'small');
   row.append(node('span','taskmain',a.filename),anchor);if(t?.can_edit!==false)row.append(remove);
   existing.append(row);
  }
 }
 const picker=NextDoFileUI.picker(box,preferences.files||[],message=>msg(message,true));
 attachments.append(existing);if(!t||t.can_edit!==false)attachments.append(picker.element,node('p','sub','I nuovi file vengono caricati quando premi Salva. Puoi trascinarli in qualsiasi punto della scheda.'));
 form.append(attachments);
 const actions=el('div',{class:'actions full'});
 actions.append(btn('Annulla',()=>back.remove()));
 if(t&&t.kind==='task'&&t.scope!=='project'&&['personal','cds','common'].includes(t.scope)&&t.can_edit!==false){
  actions.append(btn('Trasforma in progetto',async()=>{
   if(!confirm('Trasformare questa scadenza in un progetto? Il numero dell’attività, gli allegati e lo storico saranno conservati.'))return;
   try{const result=await api('/tasks/'+t.id+'/promote-to-project',{method:'POST'});back.remove();await refresh();S.selectedProject=result.project_id;S.projectMode='kanban';changeView('projects','all','',result.project_id);msg('Scadenza trasformata in progetto')}
   catch(e){msg(e.message,true)}
  },'small'));
 }
 if(t&&t.can_edit!==false)actions.append(btn('Elimina',async()=>{
  if(!confirm('Eliminare definitivamente questa attività?'))return;
  try{await api('/tasks/'+t.id,{method:'DELETE'});back.remove();await refresh();render()}catch(e){msg(e.message,true)}
 },'danger'));
 const save=el('button',{class:'btn primary',type:'submit',text:editing?'Salva modifiche':'Crea attività'});
 if(t&&t.can_edit===false)save.hidden=true;
 actions.append(save);form.append(actions);
 if(t&&t.can_edit===false)form.append(node('p','sub','Questa attività è condivisa in sola lettura. Puoi eventualmente completare gli adempimenti dei CdS che ti sono assegnati.'));
 let busy=false;
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;
  busy=true;save.disabled=true;
  if(start.value&&due.value&&new Date(start.value)>new Date(due.value)){busy=false;save.disabled=false;msg('La data di inizio non può essere successiva alla scadenza',true);return}
   const mins=reminders.value.split(',').map(x=>x.trim()).filter(Boolean).map(Number);
  const data={
   title:title.value,description:desc.value,kind:type.value,priority:pr.value,status:st.value,
   start_at:start.value?new Date(start.value).toISOString():null,
    due_at:due.value?new Date(due.value).toISOString():null,recurrence:rec.value,
   group_id:scope.value==='group'&&grp.value?Number(grp.value):null,assigned_to:scope.value==='personal'?null:assigned.value?Number(assigned.value):null,
   completion_mode:modeWrap.hidden?'global':mode.value,display_enabled:scope.value==='group'&&display.checked,scope:scope.value,project_id:scope.value==='project'&&project.value?Number(project.value):null,
   labels:labels.value.split(',').map(x=>x.trim()).filter(Boolean),
   course_ids:scope.value==='cds'?courses.selected():[],reminders:mins
  };
  try{
   if(currentId){await api('/tasks/'+currentId,{method:'PUT',body:JSON.stringify(data)})}
   else{
    const created=await api('/tasks',{method:'POST',body:JSON.stringify(data)});
    currentId=created.id;
    save.textContent='Salva modifiche';
   }
   const failed=[];
   for(const file of picker.pending()){
    const body=new FormData();body.append('file',file,file.name);
    try{await api('/tasks/'+currentId+'/attachments',{method:'POST',body});picker.uploaded(file)}
    catch(error){failed.push(file.name+': '+error.message)}
   }
   await refresh();
   if(failed.length){
    msg('Attività salvata, ma alcuni allegati non sono stati caricati: '+failed.join('; ')+' — riprova premendo Salva.',true);
   }else{
    back.remove();render();msg('Salvato');
   }
  }catch(error){msg(error.message,true)}
  finally{busy=false;save.disabled=false}
 });
 box.append(form);
 if(preferences.focus==='due'){
  due.focus();
  try{if(typeof due.showPicker==='function')due.showPicker()}catch{}
 }else if(preferences.focus==='labels')labels.focus();
 else if(preferences.focus==='attachments')picker.focus();
}

function calendarImportForm(){
 const {box,back}=modal('Importa calendario annuale — UO SEGR CDS');
 const notice=node('p','sub','Carica il file ufficiale .xlsx, verifica l’anteprima e seleziona soltanto le attività pertinenti. Le date sono indicative. Nessun dato viene importato prima della conferma.');
 const picker=el('input',{type:'file',class:'field',accept:'.xlsx'});
 const preview=el('div',{class:'calendar-import-preview',style:'max-height:52vh;overflow:auto'});
 const counters=node('p','sub','');
 const previewButton=btn('Analizza Excel',async()=>{
  if(!picker.files?.length)return msg('Selezionare un file Excel',true);
  const data=new FormData();data.append('file',picker.files[0]);
  previewButton.disabled=true;
  try{
   const result=await api('/calendar-import/preview',{method:'POST',body:data});
   showPreview(result);
  }catch(e){msg(e.message,true)}
  finally{previewButton.disabled=false}
 },'small');
 const applyButton=btn('Importa le righe selezionate',async()=>{
  const selected=[...preview.querySelectorAll('input[data-calendar-id]:checked')].map(x=>x.dataset.calendarId);
  if(!selected.length)return msg('Seleziona almeno una attività da importare',true);
  if(!confirm('Confermi l’importazione di '+selected.length+' attività? Saranno inizialmente private dell’amministratore, da verificare e assegnare in seguito.'))return;
  const data=new FormData();data.append('file',picker.files[0]);data.append('selected',JSON.stringify(selected));
  applyButton.disabled=true;
  try{
   const result=await api('/calendar-import/apply',{method:'POST',body:data});
   back.remove();await refresh();render();
   msg('Importate '+result.created+' attività. Già presenti: '+result.skipped+'. Verificare incarichi, CdS e termini.');
  }catch(e){msg(e.message,true)}
  finally{applyButton.disabled=false}
 },'primary');
 applyButton.disabled=true;
 box.append(notice,field('Calendario dell’offerta formativa (.xlsx)',picker),previewButton,counters,preview,applyButton);
 picker.addEventListener('change',()=>{preview.replaceChildren();counters.textContent='';applyButton.disabled=true});
 function showPreview(data){
  preview.replaceChildren();
  const rows=data.rows||[];
  counters.textContent=rows.length+' attività UO SEGR CDS individuate · '+rows.filter(r=>r.already_imported).length+' già importate';
  if(!rows.length){preview.append(node('p','empty','Nessuna attività UO SEGR CDS individuata.'));applyButton.disabled=true;return}
  const selectAll=btn('Seleziona nuove future',()=>{
   preview.querySelectorAll('input[data-calendar-id]').forEach(cb=>{cb.checked=cb.dataset.default==='yes'});
  },'small');
  preview.append(selectAll);
  for(const r of rows){
   const bad=r.invalid_dates?' · DATE INCOERENTI':r.requires_verification?' · [DA VERIFICARE]':'';
   const old=r.already_imported?' · GIÀ IMPORTATA'+(r.changed_in_source?' — DATE VARIATE':''):'';
   const check=el('input',{type:'checkbox',checked:r.select_by_default});
   check.dataset.calendarId=r.key;
   check.dataset.default=r.select_by_default?'yes':'no';
   if(r.already_imported||r.invalid_dates)check.disabled=true;
   const role=r.roles.join(', ');
   const text=el('div',{},[
    node('strong','',r.title),
    node('div','sub','Scadenza: '+(r.due||'[DA VERIFICARE]')+' · A.A. '+(r.year||'[DA VERIFICARE]')+' · '+(r.process||'')+old+bad),
    node('div','sub','UO SEGR CDS: '+role+' · Responsabile: '+(r.responsible||'[DA VERIFICARE]'))
   ]);
   preview.append(el('label',{class:'rowtask'},[check,text]));
  }
  applyButton.disabled=false;
 }
}

function pasteForm(){const {box,back}=modal('Incolla nota e rileva scadenze');const txt=el('textarea',{class:'field',rows:'10',placeholder:'Incolla una comunicazione o una nota…'});box.append(field('Testo originale',txt));box.append(el('p',{class:'sub',text:'Il rilevamento è locale e non utilizza servizi di AI esterni. Le date e le priorità devono sempre essere confermate.'}),el('div',{class:'actions'},[btn('Annulla',()=>back.remove()),btn('Analizza testo',async()=>{try{const suggestion=await api('/extract',{method:'POST',body:JSON.stringify({text:txt.value})});if(suggestion.detected_dates.length>1)msg('Rilevate più date: verificare quelle aggiuntive nella descrizione.');suggestion.due_at=suggestion.detected_dates[0]?suggestion.detected_dates[0]+'T12:00:00':'';back.remove();taskForm(null,'task',suggestion)}catch(e){msg(e.message,true)}},'primary')]))}
function calendar(main){const bar=el('div',{class:'toolbar'});bar.append(btn('←',()=>{S.month.setMonth(S.month.getMonth()-1);render()}),node('h2','',S.month.toLocaleDateString('it-IT',{month:'long',year:'numeric'})),btn('→',()=>{S.month.setMonth(S.month.getMonth()+1);render()}));main.append(bar);const grid=el('div',{class:'monthgrid'});for(const name of ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'])grid.append(node('div','day head',name));const y=S.month.getFullYear(),m=S.month.getMonth(),start=(new Date(y,m,1).getDay()+6)%7,num=new Date(y,m+1,0).getDate();for(let i=0;i<start;i++)grid.append(node('div','day',''));for(let d=1;d<=num;d++){const cell=el('div',{class:'day'},[node('strong','',String(d))]);for(const t of S.tasks.filter(t=>t.due_at&&new Date(t.due_at).getDate()===d&&new Date(t.due_at).getMonth()===m&&new Date(t.due_at).getFullYear()===y))cell.append(el('button',{class:'item',onclick:()=>taskForm(t),text:t.title}));grid.append(cell)}main.append(grid)}
function coursesView(main){const card=el('section',{class:'card'});card.append(node('h2','','Anagrafica CdS'));if(S.me.role==='admin'){card.append(btn('+ Aggiungi CdS',()=>courseForm(),'primary'),node('p','muted','Import CSV UTF-8 con intestazioni code,name. I codici devono rispettare il formato M seguito da 2–3 caratteri alfanumerici.'));const upload=el('input',{type:'file',accept:'.csv',class:'field'});card.append(upload,btn('Importa CSV',async()=>{if(!upload.files[0])return;const form=new FormData();form.append('file',upload.files[0]);try{const r=await api('/courses/import',{method:'POST',body:form});msg(`Importate ${r.imported} righe; righe scartate: ${r.rejected_lines.join(', ')||'nessuna'}`);await refresh();render()}catch(e){msg(e.message,true)}},'small'))}card.append(node('p','sub','L’elenco ufficiale non è precaricato: inserire o importare solo codici e denominazioni verificati.'));for(const c of S.courses){card.append(el('div',{class:'rowtask'},[node('div','taskmain',c.code+' — '+c.name+(c.active?'':' (non attivo)')),tag(S.tasks.filter(t=>t.courses.some(x=>x.id===c.id)&&t.status!=='done').length+' attività'),...(S.me.role==='admin'?[btn('Modifica',()=>courseForm(c),'small'),NextDoWorkspace.courseAdminButton(c)]:[])]))}main.append(card)}
function courseForm(c){const {box,back}=modal(c?'Modifica CdS':'Nuovo CdS');const form=el('form',{class:'formgrid'}),code=input('code','Es. M...',c?.code||''),name=input('name','Denominazione ufficiale',c?.name||''),active=el('input',{type:'checkbox',checked:c?.active??true});form.append(field('Codice CdS',code),field('Denominazione',name),el('label',{class:'full'},[active,' Attivo']));form.append(el('div',{class:'actions full'},[btn('Annulla',()=>back.remove()),el('button',{type:'submit',class:'btn primary',text:'Salva'})]));form.addEventListener('submit',async e=>{e.preventDefault();try{await api('/courses'+(c?'/'+c.id:''),{method:c?'PUT':'POST',body:JSON.stringify({code:code.value,name:name.value,active:active.checked})});back.remove();await refresh();render()}catch(e){msg(e.message,true)}});box.append(form)}
function groupsView(main){
 const panel=el('section',{class:'card'});
 panel.append(node('h2','','Gruppi e collaborazione'));
 if(S.me.role==='admin'){
  panel.append(btn('+ Crea gruppo',()=>{
   const {box,back}=modal('Nuovo gruppo');
   const name=input('name','Nome del gruppo');
   box.append(field('Nome',name),btn('Salva',async()=>{
    try{await api('/groups',{method:'POST',body:JSON.stringify({name:name.value})});back.remove();await refresh();render()}
    catch(e){msg(e.message,true)}
   },'primary'));
  },'primary'));
 }
 for(const g of S.groups)panel.append(el('div',{class:'rowtask'},[node('div','taskmain',g.name),btn('Membri',()=>membersForm(g),'small')]));
 main.append(panel);
}

function membersForm(g){const {box}=modal('Membri — '+g.name);const list=el('div');box.append(list);async function show(){const members=await api(`/groups/${g.id}/members`);list.replaceChildren(...members.map(m=>el('div',{class:'rowtask'},[node('span','taskmain',m.display_name),tag(m.role)])))}show().catch(e=>msg(e.message,true));const memberSelect=select('user_id',S.users.map(u=>[String(u.id),u.display_name])),role=select('role',[['member','Membro'],['manager','Responsabile']]);box.append(field('Aggiungi utente',memberSelect),field('Ruolo',role),btn('Aggiungi / aggiorna',async()=>{try{await api(`/groups/${g.id}/members`,{method:'POST',body:JSON.stringify({user_id:Number(memberSelect.value),role:role.value})});await show()}catch(e){msg(e.message,true)}},'primary'))}
function settings(main){const card=el('section',{class:'card'});card.append(node('h2','','Utenti e sistema'),node('p','sub','Account indipendenti da Home Assistant; accesso remoto da proteggere tramite HTTPS e Cloudflare Access.'));if(S.me.role==='admin'){card.append(btn('+ Utente',userForm,'primary'),btn('Scarica backup',async()=>{try{const r=await api('/backup');const blob=await r.blob(),url=URL.createObjectURL(blob),a=el('a',{href:url,download:'nextdo-backup.zip'});a.click();URL.revokeObjectURL(url)}catch(e){msg(e.message,true)}}),btn('Importa backup NextDo',restoreForm,'primary'),btn('Genera monitor',displayForm),btn('Elabora promemoria',async()=>{try{const r=await api('/reminders/process',{method:'POST'});msg('Promemoria creati: '+r.processed)}catch(e){msg(e.message,true)}}),btn('Avanza ricorrenze completate',async()=>{try{const r=await api('/recurrences/process',{method:'POST'});msg('Attività avanzate: '+r.advanced);await refresh()}catch(e){msg(e.message,true)}}));}for(const u of S.users)card.append(el('div',{class:'rowtask'},[node('span','taskmain',u.display_name+' ('+u.username+')'),tag(u.role)]));main.append(card);const card2=el('section',{class:'card',style:'margin-top:15px'},[node('h2','','Notifiche')]);api('/notifications').then(n=>{if(!n.length)card2.append(node('p','muted','Nessun promemoria'));for(const item of n)card2.append(el('div',{class:'rowtask'},[node('span','taskmain',item.message),tag(item.seen?'Letta':'Nuova'),btn('Segna letta',async()=>{await api(`/notifications/${item.id}/read`,{method:'POST'});render()},'small')]))}).catch(()=>{});main.append(card2);NextDoWorkspace.settings(main);NextDoMicrosoft.settings(main)}

function restoreForm(){
 const {box,back}=modal('Ripristina un backup NextDo');
 box.append(node('p','sub','Seleziona un archivio ZIP esportato da NextDo. Non usare qui i backup di Home Assistant. Il ripristino sostituisce note, scadenze, utenti, CdS e allegati; salva prima una copia dei dati attuali sul Raspberry.'));
 const f=el('input',{class:'field',type:'file',accept:'.zip,application/zip'});
 const confirmation=input('confirm','Digita RIPRISTINA');confirmation.setAttribute('autocomplete','off');
 box.append(field('Archivio NextDo (.zip)',f),field('Conferma scrivendo RIPRISTINA',confirmation));
 const action=btn('Verifica e ripristina',async()=>{
  if(!f.files?.length){msg('Seleziona un archivio ZIP NextDo',true);return}
  if(confirmation.value!=='RIPRISTINA'){msg('Digita RIPRISTINA per confermare',true);return}
  if(!window.confirm('Il ripristino sostituirà i dati attuali di NextDo. Continuare?'))return;
  const form=new FormData();form.append('file',f.files[0]);form.append('confirm','RIPRISTINA');action.disabled=true;
  try{const result=await api('/backup/import',{method:'POST',body:form});back.remove();alert('Backup ripristinato. Copia di sicurezza precedente: '+result.pre_restore_backup+'\\nAccedi con le credenziali contenute nel backup.');location.reload()}
  catch(e){action.disabled=false;msg(e.message,true)}
 },'primary');
 box.append(el('div',{class:'actions'},[btn('Annulla',()=>back.remove()),action]));
}
function userForm(){
 const {box,back}=modal('Nuovo utente NextDo');
 const form=el('form',{class:'formgrid'});
 const u=input('username','Nome utente'),d=input('display_name','Nome completo');
 const p=input('password','Password (almeno 8 caratteri)','','password');
 const r=select('role',[['user','Utente'],['admin','Amministratore']]);
 const update=()=>{p.placeholder='Password (almeno '+(r.value==='admin'?12:8)+' caratteri)'};
 r.addEventListener('change',update);update();
 form.append(field('Username',u),field('Nome visualizzato',d),field('Password',p),field('Ruolo',r),el('button',{type:'submit',class:'btn primary',text:'Crea utente'}));
 form.addEventListener('submit',async e=>{
  e.preventDefault();const length=r.value==='admin'?12:8;
  if(p.value.length<length)return msg('Servono almeno '+length+' caratteri per il ruolo selezionato',true);
  try{await api('/users',{method:'POST',body:JSON.stringify({username:u.value,display_name:d.value,password:p.value,role:r.value})});back.remove();await refresh();render()}
  catch(error){msg(error.message,true)}
 });
 box.append(form)
}
function displayForm(){const {box}=modal('Crea un monitor NextDo');const name=input('name','Nome monitor'),group=select('group_id',[['','Tutti i gruppi con attività pubblicate'],...S.groups.map(g=>[String(g.id),g.name])]);box.append(field('Nome schermo',name),field('Filtro gruppo',group),btn('Genera link',async()=>{try{const d=await api('/displays',{method:'POST',body:JSON.stringify({name:name.value,group_id:group.value?Number(group.value):null})});const url=new URL('display/'+encodeURIComponent(d.token),location.href).href;box.append(el('p',{class:'message',text:'Copia il link e custodiscilo: chiunque lo possieda può visualizzare le scadenze pubblicate.'}),el('textarea',{class:'field code',rows:'4',readonly:'',value:url}));msg('Monitor creato')}catch(e){msg(e.message,true)}},'primary'))}
init().catch(e=>{$('app').replaceChildren(node('div','authbox','Errore di avvio: '+e.message))});
