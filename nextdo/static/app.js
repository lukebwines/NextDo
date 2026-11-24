'use strict';
const S={me:null,csrf:'',tasks:[],courses:[],groups:[],users:[],view:'dashboard',settingsTab:'general',dayFilter:'',editing:null,month:new Date(),light:localStorage.getItem('nextdo-light')==='1',listPreset:'all',labelFilter:'',searchTerm:'',projects:[],courseAssignees:[],collaborators:[],courseCollaborators:[],myCourseIds:[],selectedProject:null,projectMode:localStorage.getItem('nextdo-project-view')==='gantt'?'gantt':'kanban',ganttZoom:localStorage.getItem('nextdo-gantt-zoom')||'normal'};
const $=id=>document.getElementById(id), priority={low:'Bassa',normal:'Normale',high:'Alta',critical:'Critica'}, statuses={review:'Da verificare',todo:'Da fare',doing:'In corso',waiting:'In attesa',done:'Completata'};
function el(tag,attrs={},children=[]){const n=document.createElement(tag);for(const [k,v] of Object.entries(attrs)){if(k==='class')n.className=v;else if(k==='text')n.textContent=v;else if(k==='html')throw Error('Unsafe HTML');else if(k.startsWith('on'))n.addEventListener(k.slice(2),v);else if(k==='value')n.value=v;else if(k==='checked')n.checked=!!v;else if(k==='style')n.setAttribute('style',v);else n.setAttribute(k,v)}for(const c of (Array.isArray(children)?children:[children]))if(c!=null)n.append(typeof c==='string'?document.createTextNode(c):c);return n}
function node(tag,cls,txt){return el(tag,{class:cls,text:txt})}
function msg(t,error=false){const d=el('div',{class:'notice'+(error?' error':'')},[t]);document.body.append(d);setTimeout(()=>d.remove(),5000)}
async function api(path,opts={}){let headers={'X-NextDo-CSRF':S.csrf,...(opts.headers||{})};if(opts.body&&!(opts.body instanceof FormData))headers['Content-Type']='application/json';const res=await fetch('api'+path,{credentials:'same-origin',...opts,headers});if(!res.ok){let d;try{d=await res.json()}catch{}throw Error(typeof d?.detail==='string'?d.detail:`Errore HTTP ${res.status}`)}return res.headers.get('content-type')?.includes('application/json')?res.json():res}
const opt=(v,t)=>el('option',{value:v,text:t});const input=(name,placeholder='',value='',type='text')=>el('input',{class:'field',name,placeholder,value,type});
const field=(title,control)=>el('div',{},[node('label','label',title),control]);
const select=(name,options,value='')=>{const s=el('select',{class:'field',name});for(const [v,t] of options)s.append(opt(v,t));s.value=value??'';return s};
const wrap=(...x)=>el('div',{},x);const btn=(text,fn,cls='')=>el('button',{type:'button',class:'btn '+cls,onclick:fn,text});
function fmt(d){if(!d)return 'Senza data';if(/^\d{4}-\d{2}-\d{2}$/.test(d)){const [y,m,day]=d.split('-').map(Number);return new Date(y,m-1,day).toLocaleDateString('it-IT',{dateStyle:'medium'})}const dt=new Date(d);return isNaN(dt)?d:dt.toLocaleString('it-IT',{dateStyle:'medium',timeStyle:'short'})}
function tag(text,cls=''){return node('span','pill '+cls,text)}
function localDay(d=new Date()){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')}
function today(){return localDay()}
function dueDay(t){if(!t.due_at)return '';const d=t.due_at;if(/^\d{4}-\d{2}-\d{2}$/.test(d))return d;const dt=new Date(d);return isNaN(dt)?'':localDay(dt)}
function dayOffset(n){const d=new Date();d.setDate(d.getDate()+n);return localDay(d)}
function agendaMatch(t,preset){
 const d=dueDay(t),open=t.status!=='done';
 return preset==='all'||(preset==='done'&&!open)||(open&&(
 (preset==='review'&&t.status==='review')||(preset==='urgent'&&['high','critical'].includes(t.priority))||
 (preset==='overdue'&&!!d&&d<today())||(preset==='today'&&d===today())||
 (preset==='tomorrow'&&d===dayOffset(1))||(preset==='week'&&d>=today()&&d<=dayOffset(6))||
 (preset==='future'&&d>dayOffset(6))||(preset==='undated'&&!d)));
}
function agendaOrder(a,b){return (dueDay(a)||'9999').localeCompare(dueDay(b)||'9999')||(a.due_at||'').localeCompare(b.due_at||'')||a.id-b.id}
function agendaOpen(preset='all',day=''){S.searchTerm='';changeView('agenda',preset,'',null,day)}
function settingsOpen(tab='general'){S.settingsTab=tab;changeView('settings')}
function brand(){return el('img',{class:'nextdo-brand',src:'assets/nextdo.svg',alt:'',width:'44',height:'44'})}
function themeButton(){const b=btn(S.light?'Tema scuro':'Tema chiaro',()=>{S.light=!S.light;localStorage.setItem('nextdo-light',S.light?'1':'0');document.body.classList.toggle('light',S.light);b.textContent=S.light?'Tema scuro':'Tema chiaro'},'small');return b}
function dtLocal(raw){if(!raw)return '';if(/^\d{4}-\d{2}-\d{2}$/.test(raw))return raw+'T12:00';const d=new Date(raw);if(isNaN(d))return raw.slice(0,16);const z=new Date(d.getTime()-d.getTimezoneOffset()*60000);return z.toISOString().slice(0,16)}
async function init(){document.body.classList.toggle('light',S.light);const csrf=await api('/csrf');S.csrf=csrf.csrf;const setup=await api('/setup');if(setup.needs_setup)return loginView(true);try{S.me=await api('/me');if(new URLSearchParams(location.search).get('gmail')==='connected'){S.view='settings';S.settingsTab='incoming'}await refresh();render()}catch{loginView(false)}}
function loginView(setup){const box=el('form',{class:'authbox'});box.append(el('div',{class:'logo'},[brand(),node('span','name','NextDo')]),node('h1','',setup?'Prima configurazione':'Accedi'),node('p','sub',setup?'Crea il primo account amministratore. La password deve avere almeno 12 caratteri.':'Usa le credenziali personali NextDo.'));const u=input('username','Nome utente');const p=input('password','Password','','password');box.append(field('Nome utente',u));if(setup)box.append(field('Nome visualizzato',input('display_name','Nome visualizzato')));box.append(field('Password',p));if(setup)box.append(field('Codice installazione (visibile nei log NextDo)',input('setup_token','Codice locale di prima attivazione')));const submit=el('button',{class:'btn primary',type:'submit',style:'width:100%;margin-top:20px',text:setup?'Crea amministratore':'Accedi'});box.append(submit);box.addEventListener('submit',async e=>{e.preventDefault();try{const data=Object.fromEntries(new FormData(box));if(setup){await api('/setup',{method:'POST',body:JSON.stringify(data)});msg('Amministratore creato: effettua l’accesso');loginView(false)}else{await api('/login',{method:'POST',body:JSON.stringify({...data,display_name:''})});S.me=await api('/me');await refresh();render()}}catch(e){msg(e.message,true)}});$('app').replaceChildren(box)}
async function refresh(){
 const out=await Promise.all([api('/tasks'),api('/courses'),api('/groups'),api('/users'),api('/projects'),api('/my-courses')]);
 [S.tasks,S.courses,S.groups,S.users,S.projects,S.myCourseIds]=out;
 S.courseAssignees=await api('/course-assignee-defaults');
 [S.collaborators,S.courseCollaborators]=await Promise.all([api('/collaborators'),api('/course-collaborators')]);
}
const iconDefs={paperclip:['M21.44 11.05l-8.49 8.49a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.41 17.4a2 2 0 0 1-2.83-2.83l8.49-8.49'],check:['M9 11l3 3L22 4','M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11'],home:['M3 10l9-7 9 7','M5 9v12h14V9','M9 21v-8h6v8'],list:['M8 6h13','M8 12h13','M8 18h13','M3 6h.01','M3 12h.01','M3 18h.01'],calendar:['M8 2v4','M16 2v4','M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2z'],note:['M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8l-5-5H8z','M16 3v5h5','M8 13h8','M8 17h5'],archive:['M3 4h18v5H3z','M5 9v12h14V9','M10 13h4'],settings:['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8','M4 12a8 8 0 0 1 16 0 8 8 0 0 1-16 0'],bell:['M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9','M10 21h4'],search:['M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16','M21 21l-4.35-4.35'],user:['M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2','M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8'],clock:['M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20','M12 6v6l4 2'],alert:['M12 3L2 21h20L12 3z','M12 9v4','M12 17h.01'],tag:['M3 3h8l10 10-8 8L3 11V3z','M7 7h.01'],plus:['M12 5v14','M5 12h14'],chevron:['M9 18l6-6-6-6']};
Object.assign(iconDefs,{refresh:['M20 7v5h-5','M4 17v-5h5','M5.5 8a7.5 7.5 0 0 1 12.8-2L20 12','M4 12l1.7 6a7.5 7.5 0 0 0 12.8-2'],sun:['M12 2v2','M12 20v2','M2 12h2','M20 12h2','M5 5l1.5 1.5','M17.5 17.5L19 19','M5 19l1.5-1.5','M17.5 6.5L19 5','M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10'],appointment:['M8 2v4','M16 2v4','M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2z','M12 12v4l3 2'],range:['M8 2v4','M16 2v4','M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2z','M7 14h10','M7 17h7'],folder:['M3 6h7l2 2h9v12H3z'],school:['M2 9l10-5 10 5-10 5z','M6 11v6l6 3 6-3v-6','M22 9v7'],plane:['M3 12l7 1 5 7 2-1-2-7 6-6c2-2 0-4-2-2l-6 6-7-2z']});
function ico(name,cls=''){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','2');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');svg.setAttribute('class','ico '+cls);svg.setAttribute('aria-hidden','true');for(const d of iconDefs[name]||iconDefs.check){const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',d);svg.append(p)}return svg}
function changeView(view,preset='all',label='',projectId=null,day=''){S.dayFilter=day;if(S.view==='personal'&&view!=='personal')NextDoPersonal.lock();if(view==='projects')S.selectedProject=projectId;S.view=view;S.listPreset=preset;S.labelFilter=label;render()}
function render(){
 const app=$('app');app.replaceChildren();
 const layout=el('div',{class:'app'}),sidebar=el('aside',{class:'sidebar'}),main=el('main',{class:'main'});
 const logo=el('div',{class:'logo'},[brand(),el('span',{},[node('span','name','NextDo'),node('small','brand-sub','Tasks · Note · Agenda')])]);
 sidebar.append(logo);
 const menu=el('button',{type:'button',class:'mobile-nav-toggle','aria-expanded':'false','aria-label':'Apri menu'},[ico('list'),node('span','','Menu')]);
 const navContainer=el('nav',{class:'nav-sections','aria-label':'Navigazione principale'});
 menu.addEventListener('click',()=>{const open=sidebar.classList.toggle('menu-open');menu.setAttribute('aria-expanded',String(open))});sidebar.append(menu,navContainer);
 const reviewCount=S.tasks.filter(t=>['task','appointment'].includes(t.kind)&&t.status==='review').length;
 const groups=[
 ['OPERATIVITÀ',[['dashboard','home','Dashboard'],['calendar','calendar','Calendario'],['agenda','clock','Agenda'],['tasks','list','Attività e scadenze'],['appointments','appointment','Appuntamenti'],['review','alert','Da verificare'],['notes','note','Note']]],
 ['ORGANIZZAZIONE',[['projects','folder','Progetti'],['courses','school','Corsi di Studio'],['archive','archive','Archivio']]],
 ['SPAZIO PERSONALE',[['mine','note','Il mio spazio'],['personal','plane','Area personale']]],
 ['STRUMENTI',[['settings','settings','Impostazioni']]]];
 for(const [group,navs] of groups){const section=el('div',{class:'nav-group'},[node('div','nav-heading',group)]);
 for(const [id,icon,title] of navs){const active=id==='review'?S.view==='agenda'&&S.listPreset==='review':id==='agenda'?S.view==='agenda'&&S.listPreset!=='review':id==='projects'?['projects','project-progress'].includes(S.view):S.view===id;
 const b=el('button',{type:'button',class:'nav '+(active?'active':''),title,'aria-current':active?'page':'false',onclick:()=>{S.searchTerm='';if(id==='review')agendaOpen('review');else changeView(id)}},[ico(icon),node('span','navtext',title),...(id==='review'&&reviewCount?[node('span','nav-count',String(reviewCount))]:[])]);section.append(b)}navContainer.append(section)}
 const labels=[...new Set(S.tasks.flatMap(t=>t.labels||[]))].sort((a,b)=>a.localeCompare(b,'it')).slice(0,12);
 const labelBox=el('div',{class:'sidebar-labels'},[node('div','sidebar-labels-heading','Etichette')]);
 if(!labels.length)labelBox.append(node('p','sidebar-empty','Nessuna etichetta'));
 labels.forEach((label,i)=>labelBox.append(el('button',{class:'label-link',onclick:()=>changeView('tasks','all',label)},[el('span',{class:'label-dot',style:'--dot-color:'+['#8c83ff','#f87283','#58cdbb','#ffad55','#48c4ff'][i%5]}),node('span','',label)])));
 const labelDetails=el('details',{class:'nav-label-details'},[node('summary','','Etichette'),labelBox]);navContainer.append(labelDetails);
 navContainer.append(el('div',{class:'bottom'},[node('div','muted labeltext',S.me.display_name),btn('Esci',async()=>{if(S.view==='personal')await NextDoPersonal.lock();await api('/logout',{method:'POST'});S.me=null;loginView(false)},'small')]));
 layout.append(sidebar,main);app.append(layout);
 const toolbar=el('div',{class:'appbar'});
 const search=el('form',{class:'global-search'},[ico('search'),input('global-search','Cerca attività e note...',S.searchTerm)]);
 search.addEventListener('submit',e=>{e.preventDefault();S.searchTerm=search.querySelector('input').value;changeView('tasks')});
 toolbar.append(search,el('button',{type:'button',class:'iconbutton','aria-label':'Aggiorna dati',title:'Aggiorna dati',onclick:async()=>{try{await refresh();render();msg('Dati aggiornati')}catch(e){msg(e.message,true)}}},[ico('refresh')]),el('button',{type:'button',class:'iconbutton',title:'Notifiche',onclick:()=>settingsOpen('notifications')},[ico('bell')]),el('button',{type:'button',class:'iconbutton',title:'Profilo e impostazioni',onclick:()=>settingsOpen('general')},[ico('user')]));
 main.append(toolbar);
 const titles={dashboard:'Centro operativo',agenda:'Agenda', 'project-progress':'Avanzamenti e cronoprogrammi',mine:'Il mio spazio',tasks:'Attività e scadenze',appointments:'Appuntamenti',projects:'Progetti',notes:'Note',calendar:'Calendario',courses:'Corsi di Studio',groups:'Gruppi',archive:'Archivio',personal:'Area personale',settings:'Impostazioni'};
 const header=el('div',{class:'top'},[el('div',{},[node('h1','',titles[S.view]),node('div','sub',S.view==='dashboard'?new Date().toLocaleDateString('it-IT',{weekday:'long',day:'numeric',month:'long',year:'numeric'}):S.view==='agenda'&&S.dayFilter?'Impegni del '+fmt(S.dayFilter):'Organizza le attività, rispetta le scadenze.')]),el('div',{class:'top-actions'},[themeButton(),...(['personal','settings','dashboard','project-progress'].includes(S.view)?[]:[btn('+ Nuova',()=>taskForm(null,S.view==='appointments'?'appointment':S.view==='notes'?'note':'task'),'primary')])])]);
 main.append(header);
 if(S.view==='dashboard')dashboard(main);else if(['tasks','appointments','notes','archive','mine','agenda'].includes(S.view))taskList(main,S.view);else if(S.view==='projects')NextDoWorkspace.projectView(main);else if(S.view==='project-progress'){main.append(btn('← Torna ai progetti',()=>changeView('projects'),'small'));const progress=el('div',{class:'project-progress-page'});NextDoProgress.dashboard(progress);if(!progress.children.length)progress.append(node('div','empty','Nessun progetto in evidenza o attività assegnata'));main.append(progress)}else if(S.view==='calendar')calendar(main);else if(S.view==='courses')coursesView(main);else if(S.view==='groups')groupsView(main);else if(S.view==='personal')NextDoPersonal.render(main);else settings(main);
}
function taskrow(t){const row=el('div',{class:'rowtask'});const cb=el('input',{type:'checkbox',checked:t.status==='done',title:t.status==='review'?'Verificare la scadenza prima di completarla':'Completa attività'});if(t.can_complete===false||t.status==='review')cb.disabled=true;cb.addEventListener('change',async()=>{try{if(t.completion_mode==='per_course'&&t.courses.length){taskForm(t);cb.checked=t.status==='done';return}await api(`/tasks/${t.id}/toggle`,{method:'POST'});await refresh();render()}catch(e){msg(e.message,true)}});const main=el('div',{class:'taskmain'},[el('button',{type:'button',class:'tasktitle task-open',onclick:()=>taskForm(t)},[t.title]),el('div',{},[node('span','muted',fmt(t.due_at)+' · '),...(t.kind==='appointment'?[tag('Appuntamento')]:t.kind==='task'?[tag('Scadenza')]:[]),...(t.status==='review'?[tag('Da verificare','high')]:[]),tag(priority[t.priority],t.priority),...t.courses.slice(0,3).map(c=>tag(c.code)),...(t.labels||[]).slice(0,2).map(x=>tag(x))])]);const edit=btn('Apri',()=>taskForm(t),'small');row.append(cb,main,edit,...(['task','appointment'].includes(t.kind)?[workAckButton(t)]:[]));return row}
function dashboardRow(t){
 const d=dueDay(t),past=!!d&&d<today(),appointment=t.kind==='appointment';
 const cls=past?'overdue':t.status==='review'?'review':appointment?'appointment':'deadline';
 const row=el('div',{class:'dash-task-row '+cls+(t.priority==='critical'?' critical':'')});
 const cb=el('input',{type:'checkbox','aria-label':'Completa '+t.title,title:t.status==='review'?'Verificare prima di completare':'Completa attività'});
 cb.disabled=t.status==='review'||t.can_complete===false;
 cb.addEventListener('change',async()=>{if(t.completion_mode==='per_course'&&t.courses?.length){taskForm(t);cb.checked=false;return}cb.disabled=true;try{await api('/tasks/'+t.id+'/toggle',{method:'POST'});await refresh();render()}catch(e){cb.checked=false;cb.disabled=false;msg(e.message,true)}});
 const date=d?new Date(d+'T12:00:00'):null;
 const tile=el('span',{class:'date-tile'},date?[node('span','tile-weekday',date.toLocaleDateString('it-IT',{weekday:'short'})),node('strong','tile-day',String(date.getDate())),node('span','tile-month',date.toLocaleDateString('it-IT',{month:'short'}))]:[ico('calendar'),node('span','tile-month','Senza data')]);
 const when=!d?'Senza data':past?'Trascorsa · '+fmt(t.due_at):d===today()?'Oggi · '+fmt(t.due_at):d===dayOffset(1)?'Domani · '+fmt(t.due_at):fmt(t.due_at);
 const info=el('button',{type:'button',class:'dash-task-title',onclick:()=>taskForm(t),'aria-label':'Apri '+t.title},[tile,el('span',{class:'dash-task-copy'},[
 node('span','dash-due',when),node('strong','dash-task-name',t.title),
 el('span',{class:'dash-task-meta'},[tag(appointment?'Appuntamento':'Attività / scadenza',appointment?'normal':''),...(t.status==='review'?[tag('Da verificare','high')]:[]),...(past?[tag('Trascorsa','critical')]:[]),...(['high','critical'].includes(t.priority)?[tag(priority[t.priority],t.priority)]:[]),...(t.labels||[]).slice(0,1).map(v=>tag(v,'label-tag'))])
 ]),ico('chevron')]);
 row.append(cb,info,workAckButton(t));return row
}
function dashboardPanel(title,icon,items,action,empty,cls=''){
 const panel=el('section',{class:'card bento-panel '+cls});
 panel.append(el('div',{class:'card-head'},[ico(icon),node('h2','',title),node('span','panel-count',String(items.length)),btn('Vedi tutte',action,'textlink')]));
 const list=el('div',{class:'bento-list'});
 for(const t of items.sort(agendaOrder))list.append(dashboardRow(t));
 if(!items.length)list.append(el('div',{class:'bento-empty'},[ico('check'),node('span','',empty)]));
 panel.append(list);return panel
}
function monthShift(delta){S.month=new Date(S.month.getFullYear(),S.month.getMonth()+delta,1)}
function monthDays(month){const y=month.getFullYear(),m=month.getMonth(),start=(new Date(y,m,1).getDay()+6)%7;return Array.from({length:42},(_,i)=>new Date(y,m,1-start+i))}
function miniCalendar(pending){
 const card=el('section',{class:'card bento-panel bento-calendar'});
 const title=node('h2','',S.month.toLocaleDateString('it-IT',{month:'long',year:'numeric'}));
 card.append(el('div',{class:'card-head'},[ico('calendar'),title,el('div',{class:'calendar-nav'},[
 el('button',{type:'button',class:'btn small','aria-label':'Mese precedente',onclick:()=>{monthShift(-1);render()}},['‹']),
 el('button',{type:'button',class:'btn small','aria-label':'Mese successivo',onclick:()=>{monthShift(1);render()}},['›'])
 ])]));
 const grid=el('div',{class:'mini-month'});
 for(const w of ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'])grid.append(node('span','mini-weekday',w));
 for(const d of monthDays(S.month)){
  const key=localDay(d),events=pending.filter(t=>dueDay(t)===key);
  const types=[...new Set(events.map(t=>t.status==='review'?'review':t.kind==='appointment'?'appointment':'deadline'))];
  const cell=el('button',{type:'button',class:'mini-day '+(d.getMonth()!==S.month.getMonth()?'outside ':'')+(key===today()?'today ':'')+(events.length?'has-events':''),'aria-label':d.toLocaleDateString('it-IT',{dateStyle:'long'})+': '+events.length+' impegni',onclick:()=>agendaOpen('all',key)},[node('span','',String(d.getDate())),el('span',{class:'mini-dots'},types.map(x=>el('span',{class:'mini-dot '+x})))]);
  grid.append(cell)
 }
 card.append(grid,el('div',{class:'calendar-legend'},[['appointment','Appuntamento'],['deadline','Scadenza'],['review','Da verificare']].map(([cls,name])=>el('span',{},[el('i',{class:'mini-dot '+cls}),name]))),
 el('div',{class:'calendar-footer'},[btn('Oggi',()=>{S.month=new Date();render()},'small'),btn('Apri calendario →',()=>changeView('calendar'),'textlink')]));
 return card
}
function dashboard(main){
 main.classList.add('dashboard-page');
 const all=S.tasks.filter(t=>['task','appointment'].includes(t.kind));
 const pending=all.filter(t=>t.status!=='done');
 const metrics=[['Scadute / trascorse','overdue','clock'],['Oggi','today','sun'],['Domani','tomorrow','appointment'],['Prossimi 7 giorni','week','range'],['Da verificare','review','alert'],['Completate','done','check']];
 const summary=el('div',{class:'dash-metrics bento-metrics'});
 for(const [name,preset,icon] of metrics){const n=all.filter(t=>agendaMatch(t,preset)).length;summary.append(el('button',{type:'button',class:'metric metric-'+preset,onclick:()=>agendaOpen(preset),'aria-label':name+': '+n+' attività, apri elenco filtrato'},[el('span',{class:'metric-icon'},[ico(icon)]),node('span','metric-label',name),node('strong','metric-value',String(n))]))}
 main.append(summary);
 const overdue=pending.filter(t=>agendaMatch(t,'overdue'));
 const near=pending.filter(t=>agendaMatch(t,'week'));
 const rest=pending.filter(t=>!near.includes(t)&&!overdue.includes(t));
 const reviews=rest.filter(t=>t.status==='review');
 const later=rest.filter(t=>t.status!=='review'&&dueDay(t));
 const undated=rest.filter(t=>t.status!=='review'&&!dueDay(t));
 const left=el('div',{class:'bento-stack bento-main'},[
 ...(overdue.length?[dashboardPanel('Scadute e appuntamenti trascorsi','alert',overdue,()=>agendaOpen('overdue'),'Nessuna attività scaduta','bento-overdue')]:[]),
 dashboardPanel('Prossimi impegni','clock',near,()=>agendaOpen('week'),'Nessun impegno imminente','bento-upcoming'),
 dashboardPanel('Altre attività da verificare','alert',reviews,()=>agendaOpen('review'),'Nessun’altra proposta da verificare','bento-review')
 ]);
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
 const actionsCard=el('section',{class:'card bento-panel bento-actions'},[el('div',{class:'card-head'},[ico('plus'),node('h2','','Azioni rapide')])]);
 for(const [kind,label,icon] of [['task','Nuova attività','list'],['appointment','Nuovo appuntamento','calendar'],['note','Nuova nota','note']])actionsCard.append(el('button',{type:'button',class:'quick-link',onclick:()=>taskForm(null,kind)},[ico(icon),node('span','',label),ico('chevron')]));
 actionsCard.append(extract);
 const board=el('div',{class:'bento-grid'},[left,miniCalendar(pending),el('div',{class:'bento-stack bento-side'},[actionsCard,quick,dashboardPanel('Senza data','list',undated,()=>agendaOpen('undated'),'Nessuna attività senza data','bento-undated')])]);
 main.append(board,dashboardPanel('Prossime scadenze e impegni','calendar',later,()=>agendaOpen('future'),'Nessun altro impegno programmato','bento-later'));
 const footer=el('div',{class:'dashboard-footer'},[btn('Tutte le attività · '+pending.length,()=>agendaOpen(),'small'),btn('Urgenti · '+pending.filter(t=>agendaMatch(t,'urgent')).length,()=>agendaOpen('urgent'),'small')]);main.append(footer)
}
function labelDistribution(pending){
 const groups=new Map();for(const t of pending)for(const label of t.labels||[])groups.set(label,(groups.get(label)||0)+1);
 const count=[...groups.entries()].sort((a,b)=>b[1]-a[1]).slice(0,5);const breakdown=el('section',{class:'card dash-breakdown'});breakdown.append(node('h2','','Distribuzione per etichetta'));
 const chart=el('div',{class:'breakdown-inner'});const colors=['#8e80ff','#409bff','#51d8a2','#ffad43','#5dc6ea'];const all=count.reduce((n,v)=>n+v[1],0);let pct=0;const segments=count.map(([name,n],i)=>{const first=pct;pct+=n/all*100;return colors[i]+' '+first+'% '+pct+'%'});
 const ring=el('div',{class:'donut',style:'background:'+(all?'conic-gradient('+segments.join(',')+')':'conic-gradient(#31465e 0 100%)')},[node('span','donut-count',String(pending.length)),node('span','donut-label','attività')]);
 const legend=el('div',{class:'chart-legend'});count.forEach(([name,num],i)=>legend.append(el('div',{class:'legend-row'},[el('span',{class:'legend-dot',style:'background:'+colors[i]}),node('span','',name),node('strong','',String(num))])));if(!count.length)legend.append(node('span','muted','Nessuna etichetta assegnata'));chart.append(ring,legend);breakdown.append(chart);return breakdown;

}
function canExportICS(t){return ['task','appointment'].includes(t.kind)&&t.status!=='review'&&!!t.due_at}
async function downloadICS(ids,includeDetails){
 const response=await api('/calendar/export',{method:'POST',body:JSON.stringify({task_ids:ids,include_details:includeDetails})});
 const url=URL.createObjectURL(await response.blob());
 const link=el('a',{href:url,download:ids.length===1?'nextdo-'+ids[0]+'.ics':'nextdo-calendario.ics'});
 document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
 msg('File ICS scaricato. Aprirlo nel calendario desiderato.');
}
function outboundRequestId(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('')}
async function sendCalendarMail(ids,details){
 const cfg=await api('/outbound-mail/config');
 if(!cfg.enabled)return msg('Collaudare e abilitare Posta in uscita nelle Impostazioni',true);
 const {box,back}=modal('Invia ICS via email');
 const recipient=select('recipient',[['','Selezionare destinatario'],...cfg.recipients.map(x=>[x,x])]);
 const status=node('p','sub','');
 const send=btn('Invia ICS',async()=>{
  if(!recipient.value)return msg('Seleziona un destinatario',true);
  if(!confirm('Inviare '+ids.length+' voci di calendario a '+recipient.value+'?'+(details?' Sono inclusi descrizione e collegamenti.':'')))return;
  send.disabled=true;recipient.disabled=true;
  try{
   const result=await api('/outbound-mail/send-ics',{method:'POST',body:JSON.stringify({request_id:outboundRequestId(),recipient:recipient.value,task_ids:ids,include_details:details,confirmed:true})});
   status.textContent=result.detail;msg(result.detail,!['delivered','queued'].includes(result.status));
  }catch(e){status.textContent=e.message+' — Controllare il registro prima di un nuovo invio.';msg(e.message,true)}
 },'primary');
 box.append(node('p','sub','Mittente: '+cfg.sender+' · '+ids.length+' voci. Solo destinatari autorizzati. Invio manuale, nessun invito automatico.'),field('Destinatario',recipient),status,send,btn('Chiudi',()=>back.remove(),'small'));
}
function calendarExportForm(tasks){
 const candidates=tasks.filter(canExportICS);
 if(!candidates.length)return msg('Nessuna attività confermata con data da esportare',true);
 const {box,back}=modal(candidates.length===1?'Esporta nel calendario':'Esporta scadenze e appuntamenti');
 const selected=new Set(candidates.length===1?[candidates[0].id]:[]);
 const list=el('div',{style:'max-height:45vh;overflow:auto'});
 const details=el('input',{type:'checkbox'});
 const count=node('p','sub','');
 const checks=[];
 const run=btn('Scarica ICS / Apri nel calendario',async()=>{
  if(!selected.size)return;
  run.disabled=true;
  try{await downloadICS([...selected],details.checked);back.remove()}catch(e){msg(e.message,true)}finally{run.disabled=!selected.size}
 },'primary');
 function update(){count.textContent=selected.size+' di '+candidates.length+' selezionate';run.disabled=!selected.size}
 for(const t of candidates){
  const cb=el('input',{type:'checkbox',checked:selected.has(t.id)});
  checks.push([t.id,cb]);cb.addEventListener('change',()=>{if(cb.checked)selected.add(t.id);else selected.delete(t.id);update()});
  list.append(el('label',{class:'rowtask'},[cb,el('div',{class:'taskmain'},[
   node('strong','',t.title),node('p','sub',(t.kind==='appointment'?'Appuntamento':'Scadenza')+' · '+fmt(t.due_at)+(t.kind==='appointment'&&/^\d{4}-\d{2}-\d{2}$/.test(t.due_at)?' · orario da definire':''))
  ])]));
 }
 const selection=el('div',{class:'actions'},[btn('Seleziona tutte',()=>{for(const [id,cb] of checks){selected.add(id);cb.checked=true}update()},'small'),btn('Deseleziona tutte',()=>{selected.clear();checks.forEach(([,cb])=>cb.checked=false);update()},'small')]);
 box.append(node('p','sub','Esportazione dei dati salvati. Scadenze come eventi giornalieri; appuntamenti con l’orario registrato, senza durata inventata. Le date non ancora confermate e le note sono escluse.'),
  selection,list,count,el('label',{class:'rowtask'},[details,' Includi descrizione, luogo e collegamenti espliciti']),
  node('p','sub','Includere i dettagli solo se autorizzati a trasferirli nel calendario esterno. Aprire il file .ics scaricato con il calendario scelto. Nessuna sincronizzazione automatica.'),
  el('div',{class:'actions'},[btn('Annulla',()=>back.remove()),run,...(S.me.role==='admin'?[btn('Invia ICS via email',async()=>{if(!selected.size)return msg('Seleziona almeno una voce',true);try{await sendCalendarMail([...selected],details.checked)}catch(e){msg(e.message,true)}},'small')]:[])]));
 update();
}
function taskList(main,view){const tools=el('div',{class:'toolbar'});const search=input('q','Cerca testo, attività o note…');const csel=select('course',[['','Tutti i CdS'],...S.courses.map(c=>[String(c.id),c.code+' — '+c.name])]);const gsel=select('group',[['','Tutti i gruppi'],...S.groups.map(g=>[String(g.id),g.name])]);const status=select('status',[['','Tutti gli stati'],...Object.entries(statuses)]);const preset=select('preset',[['all','Tutte'],['review','Da verificare'],['urgent','Urgenti'],['overdue','Scadute / trascorse'],['today','Oggi'],['tomorrow','Domani'],['week','Prossimi 7 giorni'],['future','Oltre 7 giorni'],['undated','Senza data'],['done','Completate']],S.listPreset);search.value=S.searchTerm||'';for(const [control,label] of [[search,'Cerca attività'],[csel,'Filtra per CdS'],[gsel,'Filtra per gruppo'],[status,'Filtra per stato'],[preset,'Filtra per periodo o priorità']])control.setAttribute('aria-label',label);tools.append(search,csel,gsel,status,preset);if(S.dayFilter)tools.append(btn('Data: '+fmt(S.dayFilter)+' ×',()=>agendaOpen(),'small'));if(S.labelFilter)tools.append(btn('Etichetta: '+S.labelFilter+' ×',()=>changeView(view),'small'));if(view==='notes')tools.append(btn('+ Nota',()=>taskForm(null,'note'),'primary'));if(view==='tasks'&&S.me.role==='admin')tools.append(btn('Importa calendario Excel',calendarImportForm,'small'));if(view==='tasks'&&S.me.role==='admin')tools.append(btn('Email → Scadenze AI',emailIntakeForm,'small'));main.append(tools);const panel=el('section',{class:'card'});main.append(panel);function draw(){panel.replaceChildren();let tasks=S.tasks.filter(t=>view==='mine'?t.scope==='personal':view==='notes'?t.kind==='note':view==='archive'?t.status==='done':(view==='agenda'?['task','appointment'].includes(t.kind):t.kind===(view==='appointments'?'appointment':'task'))&&(t.status!=='done'||preset.value==='done'));tasks=tasks.filter(t=>(!search.value||(t.title+' '+t.description).toLowerCase().includes(search.value.toLowerCase()))&&(!csel.value||t.courses.some(c=>c.id==csel.value))&&(!gsel.value||t.group_id==gsel.value)&&(!status.value||t.status===status.value)&&(!S.labelFilter||(t.labels||[]).includes(S.labelFilter))&&agendaMatch(t,preset.value)&&(!S.dayFilter||dueDay(t)===S.dayFilter));panel.append(node('h2','',`${tasks.length} elementi`));if(tasks.some(canExportICS))panel.append(btn('Esporta ICS',()=>calendarExportForm(tasks),'small'));if(!tasks.length)panel.append(node('p','empty','Nessun elemento trovato'));tasks.sort(agendaOrder).forEach(t=>panel.append(taskrow(t)));if(['tasks','agenda'].includes(view)&&tasks.length)panel.append(el('details',{class:'list-analytics'},[node('summary','','Distribuzione per etichetta'),labelDistribution(tasks.filter(t=>t.status!=='done'))]))}for(const x of [search,csel,gsel,status,preset])x.addEventListener('input',draw);draw()}
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
 const type=select('kind',[['task','Scadenza / attività'],['appointment','Appuntamento'],['note','Nota libera']],t?.kind||kind);
 const pr=select('priority',Object.entries(priority),t?.priority||suggestion?.priority||'normal');
 const st=select('status',Object.entries(statuses),t?.status||'todo');
 const rawDue=t?.due_at||suggestion?.due_at||'';
 const dateOnly=type.value==='appointment'&&/^\d{4}-\d{2}-\d{2}$/.test(rawDue);
 const due=input('due_at','',dateOnly?rawDue:dtLocal(rawDue),dateOnly?'date':'datetime-local');
 const unknownTime=el('input',{type:'checkbox',checked:dateOnly});
 const unknownWrap=el('label',{class:'full'},[unknownTime,' Orario appuntamento non definito']);
 function syncAppointment(){unknownWrap.hidden=type.value!=='appointment';const wanted=type.value==='appointment'&&unknownTime.checked?'date':'datetime-local';if(due.type!==wanted){const old=due.value;due.type=wanted;due.value=wanted==='date'?old.slice(0,10):old.length===10?'':old;} }
 unknownTime.addEventListener('change',syncAppointment);type.addEventListener('change',syncAppointment);syncAppointment();
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
  modeWrap.hidden=!['cds','common','group','project'].includes(scope.value);
 }
 scope.addEventListener('change',updateScope);
 form.append(field('Titolo *',title),field('Tipologia',type),el('div',{class:'full'},[field('Descrizione / nota',desc)]),field('Priorità',pr),field('Stato',st),field('Inizio previsto (facoltativo)',start),field('Data e ora scadenza / appuntamento',due),unknownWrap,field('Ricorrenza',rec),field('Ambito / visibilità',scope),courseWrap,projectWrap,groupWrap,field('Responsabile',assigned),modeWrap,field('Etichette (separate da virgola)',labels),field('Promemoria in minuti prima della scadenza',reminders),displayWrap);
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
 if(t&&canExportICS(t))actions.append(btn('Aggiungi al calendario · ICS',()=>calendarExportForm([t]),'small'));
 else if(t&&['task','appointment'].includes(t.kind))form.append(node('p','sub','Esportazione ICS disponibile dopo la conferma e il salvataggio di una data.'));
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
 if(t?.status==='review')form.append(node('p','sub','Scadenza da verificare: controlla la fonte, il termine e gli eventuali CdS. Per confermarla imposta lo stato Da fare, quindi salva.'));
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
    due_at:due.value?(type.value==='appointment'&&unknownTime.checked?due.value:new Date(due.value).toISOString()):null,recurrence:rec.value,
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


async function emailIntakeForm(){
 if(S.me.role!=='admin')return msg('Funzione riservata all’amministratore',true);
 const {box,back}=modal('Email selezionate → Scadenze AI');
 box.append(node('p','sub','Nessun collegamento a Microsoft 365. Puoi caricare un file .eml, incollare il testo di una email, oppure leggere una casella dedicata IMAP. GroqCloud elabora i testi su server esterni: usare solo contenuti autorizzati. Nessuna scadenza viene salvata automaticamente.'));
 const imapPanel=el('div',{class:'full card'});
 const mailbox=el('div',{class:'full'});
 const emailList=el('div',{style:'max-height:260px;overflow:auto'});
 const preview=el('div',{class:'full',style:'max-height:45vh;overflow:auto'});
 const analyzeNotice=node('p','sub','');
 const methods=el('section',{class:'full',style:'display:flex;flex-direction:column;gap:10px'});
 const eml=el('input',{type:'file',accept:'.eml',class:'field'});
 const subject=input('mail_subject','Oggetto (facoltativo)');
 const pasted=el('textarea',{class:'field',rows:'6',placeholder:'Incolla solo il testo dell’email selezionata. Non includere dati non necessari.'});
 const buttons=el('div',{class:'actions'});
 const analyzeFile=btn('Analizza file .eml',async()=>{
  if(!eml.files?.length)return msg('Seleziona un messaggio .eml',true);
  const fd=new FormData();fd.append('file',eml.files[0]);
  await review('/email-intake/analyze-upload',{method:'POST',body:fd});
 },'small');
 const analyzePaste=btn('Analizza testo selezionato',async()=>{
  if(!pasted.value.trim())return msg('Incolla prima il testo',true);
  await review('/email-intake/analyze-text',{method:'POST',
    body:JSON.stringify({subject:subject.value,text:pasted.value})});
 },'primary');
 buttons.append(analyzeFile,analyzePaste);
 methods.append(field('Carica una email .eml',eml),
   node('p','sub','In alternativa, incolla soltanto il messaggio da analizzare:'),subject,pasted,buttons);
 box.append(methods,imapPanel,analyzeNotice,preview,btn('Chiudi',()=>back.remove(),'small'));
 let currentConfig;
 async function settings(){
  try{currentConfig=await api('/email-intake/config')}catch(e){msg(e.message,true);return}
  renderMailbox();
 }
 function renderMailbox(){
  imapPanel.replaceChildren();
  imapPanel.append(node('h3','','Casella dedicata IMAP'),
   node('p','sub',currentConfig?.imap_configured?
    'Lettura manuale in sola lettura: NextDo non sposta, non elimina e non contrassegna come letti i messaggi.':
    'Casella non configurata. Puoi già analizzare file .eml o testo incollato dopo aver configurato GroqCloud in Impostazioni.'));
  if(currentConfig?.imap_configured){
   const load=btn('Controlla le ultime 25 email',async()=>{
    load.disabled=true;emailList.replaceChildren(node('p','sub','Lettura messaggi...'));
    try{
     const result=await api('/email-intake/messages');
     emailList.replaceChildren();
     if(!result.messages?.length)emailList.append(node('p','sub','Casella vuota.'));
     for(const mail of result.messages||[]){
      const item=el('div',{class:'rowtask'},[
       el('div',{class:'taskmain'},[
        node('strong','',mail.subject||'Senza oggetto'),
        node('p','sub',mail.sender+' · '+mail.date)
       ]),
       btn('Analizza',()=>review('/email-intake/analyze-message',
        {method:'POST',body:JSON.stringify({uid:mail.uid})}),'small')
      ]);
      emailList.append(item);
     }
    }catch(e){emailList.replaceChildren();msg(e.message,true)}
    finally{load.disabled=false}
   },'small');
   imapPanel.append(load,emailList);
  }
 }
 async function review(path,options){
  preview.replaceChildren();
  analyzeNotice.textContent='Analisi GroqCloud in corso: verranno estratte soltanto proposte da confermare.';
  for(const b of [analyzeFile,analyzePaste])b.disabled=true;
  try{
   const result=await api(path,options);
   analyzeNotice.textContent='Analisi completata. Nessun dato salvato. Verifica oggetto, frase originale e data di ogni proposta.';
   preview.append(node('h3','','Proposte dall’email: '+(result.source?.subject||'senza oggetto')));
   const already=S.tasks.some(t=>t.description?.includes(result.source?.source_hash||'@@@'));
   if(already)preview.append(node('p','project-assignment-warning','Attenzione: un’attività derivata da questa email risulta già presente tra le scadenze visibili.'));
   if(!result.proposals?.length)preview.append(node('p','sub','Nessuna attività verificabile individuata. È possibile inserire manualmente una scadenza.'));
   for(const p of result.proposals||[]){
    const row=el('section',{class:'card',style:'margin-bottom:10px'});
    row.append(node('strong','',p.title),
     node('p','sub',(p.kind==='appointment'?'Appuntamento proposto: ':'Scadenza proposta: ')+(p.due_date||'[DA VERIFICARE]')+(p.appointment_time?' '+p.appointment_time:'')+' · Data sempre da confermare'),
     node('p','sub','Frase originale: “'+p.evidence+'”'));
    row.append(btn('Prepara scadenza',()=>{
     taskForm(null,p.kind||'task',{title:p.title,description:p.description,
      due_at:p.due_date?(p.kind==='appointment'?(p.appointment_time?p.due_date+'T'+p.appointment_time+':00':p.due_date):p.due_date+'T12:00:00'):''},{scope:'personal',focus:p.due_date?'due':undefined});
    },'primary'));
    preview.append(row);
   }
  }catch(e){analyzeNotice.textContent='Analisi non completata: '+e.message;msg(e.message,true)}
  finally{for(const b of [analyzeFile,analyzePaste])b.disabled=false}
 }
 await settings();
}

function pasteForm(){const {box,back}=modal('Incolla nota e rileva scadenze');const txt=el('textarea',{class:'field',rows:'10',placeholder:'Incolla una comunicazione o una nota…'});box.append(field('Testo originale',txt));box.append(el('p',{class:'sub',text:'Il rilevamento è locale e non utilizza servizi di AI esterni. Le date e le priorità devono sempre essere confermate.'}),el('div',{class:'actions'},[btn('Annulla',()=>back.remove()),btn('Analizza testo',async()=>{try{const suggestion=await api('/extract',{method:'POST',body:JSON.stringify({text:txt.value})});if(suggestion.detected_dates.length>1)msg('Rilevate più date: verificare quelle aggiuntive nella descrizione.');suggestion.due_at=suggestion.detected_dates[0]?suggestion.detected_dates[0]+'T12:00:00':'';back.remove();taskForm(null,'task',suggestion)}catch(e){msg(e.message,true)}},'primary')]))}
function calendar(main){
 const bar=el('div',{class:'toolbar calendar-toolbar'});
 const title=node('h2','',S.month.toLocaleDateString('it-IT',{month:'long',year:'numeric'}));
 bar.append(el('button',{type:'button',class:'btn','aria-label':'Mese precedente',onclick:()=>{monthShift(-1);render()}},['‹']),title,el('button',{type:'button',class:'btn','aria-label':'Mese successivo',onclick:()=>{monthShift(1);render()}},['›']),btn('Oggi',()=>{S.month=new Date();render()}),btn('Esporta ICS',()=>calendarExportForm(S.tasks.filter(t=>dueDay(t).startsWith(localDay(S.month).slice(0,7)))),'small'));
 main.append(bar);
 const grid=el('div',{class:'monthgrid full-calendar'});
 for(const name of ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'])grid.append(node('div','day head',name));
 for(const d of monthDays(S.month)){
  const key=localDay(d),events=S.tasks.filter(t=>dueDay(t)===key).sort(agendaOrder);
  const cell=el('div',{class:'day '+(d.getMonth()!==S.month.getMonth()?'outside ':'')+(key===today()?'today':'')},[el('button',{type:'button',class:'calendar-day-number','aria-label':'Apri agenda del '+fmt(key),onclick:()=>agendaOpen('all',key)},[String(d.getDate())])]);
  for(const t of events)cell.append(el('button',{type:'button',class:'item '+(t.status==='review'?'review':t.kind==='appointment'?'appointment':'deadline')+(t.status==='done'?' done':''),onclick:()=>taskForm(t),title:t.title},[(t.kind==='appointment'?'◷ ':'')+(t.status==='review'?'[Da verificare] ':'')+t.title]));
  grid.append(cell)
 }
 main.append(grid)
}
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
function emailIntakeSettings(main,mode='all'){
 if(S.me.role!=='admin')return;
 const card=el('section',{class:'card',style:'margin-top:15px'});
 card.append(node('h2','',mode==='imap'?'Casella IMAP facoltativa':'Configurazione GroqCloud'),
  node('p','sub','GroqCloud elabora il testo su server esterni. Non inviare comunicazioni istituzionali senza autorizzazione. Nessuna integrazione Microsoft 365.'));
 const grid=el('div',{class:'formgrid'});card.append(grid);main.append(card);
 api('/email-intake/config').then(cfg=>{
  const host=input('imap_host','Es. imap.gmail.com',cfg.imap_host);
  const port=input('imap_port','993',String(cfg.imap_port||993),'number');
  const user=input('imap_user','Casella dedicata',cfg.imap_user);
  const password=input('imap_password','Lascia vuoto per mantenere quella salvata','','password');
  const model=input('groq_model','Modello GroqCloud',cfg.groq_model||'openai/gpt-oss-120b');
  const key=input('groq_api_key','Lascia vuoto per mantenere la chiave salvata','','password');
  key.setAttribute('autocomplete','new-password');password.setAttribute('autocomplete','new-password');
  if(mode!=='imap')grid.append(node('p','sub','Chiave GroqCloud: '+(cfg.groq_key_configured?'già configurata':'non configurata')+'. Per il test con testo incollato non occorre configurare IMAP.'),field('Modello GroqCloud',model),field('API key GroqCloud',key));
  if(mode!=='ai')grid.append(field('Server IMAP',host),field('Porta SSL/TLS',port),field('Utente casella',user),field('Password casella dedicata',password));
  grid.append(btn('Salva impostazioni email e AI',async()=>{
   try{
    const current=await api('/email-intake/config');
    const result=await api('/email-intake/config',{method:'POST',body:JSON.stringify({
     imap_host:mode==='ai'?current.imap_host:host.value,imap_port:mode==='ai'?current.imap_port:Number(port.value),imap_user:mode==='ai'?current.imap_user:user.value,
     imap_password:mode==='ai'?'':password.value,groq_model:mode==='imap'?current.groq_model:model.value,groq_api_key:mode==='imap'?'':key.value})});
    key.value='';password.value='';
    msg('Configurazione salvata. Chiave GroqCloud: '+(result.groq_key_configured?'configurata':'non configurata'));
   }catch(e){msg(e.message,true)}
  },'primary'));
 }).catch(e=>msg(e.message,true));
}
function emailPromptSettings(main){
 if(S.me.role!=='admin')return;
 const card=el('section',{class:'card',style:'margin-top:15px'});
 card.append(node('h2','','Intelligenza artificiale · Prompt email'),
  node('p','sub','Personalizza le istruzioni operative per GroqCloud. La prova usa il prompt presente nell’editor, anche prima di salvarlo, e non crea attività. Le regole tecniche rimangono obbligatorie.'));
 const body=el('div');card.append(body);main.append(card);
 api('/email-intake/prompt').then(cfg=>{
  const prompt=el('textarea',{class:'field',rows:'12',maxlength:'12000'});prompt.value=cfg.prompt;
  const subject=input('subject','Oggetto email di prova');
  const sample=el('textarea',{class:'field',rows:'7',maxlength:'14000',placeholder:'Incolla il testo da analizzare (senza allegati)'});
  const result=el('div');
  const actions=el('div',{class:'actions'});
  const details=el('details',{},[node('summary','','Regole obbligatorie (sola lettura)'),el('pre',{style:'white-space:pre-wrap;overflow-wrap:anywhere'},cfg.fixed_rules)]);
  actions.append(btn('Salva prompt',async()=>{
   try{const r=await api('/email-intake/prompt',{method:'POST',body:JSON.stringify({prompt:prompt.value})});prompt.value=r.prompt;msg('Prompt salvato')}
   catch(e){msg(e.message,true)}
  },'primary'),btn('Ripristina predefinito',async()=>{
   if(!confirm('Ripristinare il prompt predefinito? Il prompt personalizzato verrà sostituito.'))return;
   try{const r=await api('/email-intake/prompt/reset',{method:'POST'});prompt.value=r.prompt;msg('Prompt predefinito ripristinato')}catch(e){msg(e.message,true)}
  },'small'));
  const test=btn('Prova prompt',async()=>{
   if(!prompt.value.trim()||!sample.value.trim())return msg('Inserire il prompt e un testo di prova',true);
   test.disabled=true;result.replaceChildren(node('p','sub','Analisi in corso…'));
   try{const r=await api('/email-intake/prompt/test',{method:'POST',body:JSON.stringify({prompt:prompt.value,subject:subject.value,text:sample.value})});
    showMailProposals(result,r);
   }catch(e){result.replaceChildren(node('p','sub',e.message))}finally{test.disabled=false}
  },'primary');
  body.append(field('Prompt personalizzabile',prompt),actions,details,node('h3','','Simulazione senza salvataggio'),
    node('p','sub','Il testo di prova viene inviato a GroqCloud. Usare dati autorizzati, preferibilmente anonimizzati.'),
    field('Oggetto',subject),field('Testo email',sample),test,result);
 }).catch(e=>body.append(node('p','sub',e.message)));
}
function showMailProposals(target,result){
 target.replaceChildren(node('h3','','Risultato simulazione · nessuna attività creata'));
 const proposals=result.proposals||[];
 if(!proposals.length)target.append(node('p','sub','Nessuna proposta verificabile'));
 for(const p of proposals)target.append(el('div',{class:'rowtask'},[el('div',{class:'taskmain'},[
  node('strong','',p.title),node('p','sub',(p.manual_review?'Revisione manuale':p.kind==='appointment'?'Appuntamento':'Attività')+' · '+(p.due_date||'Senza data')+(p.appointment_time?' · '+p.appointment_time:'')),
  node('p','sub',p.evidence||''),node('p','sub',p.description||'')
 ])]));
}
function openRetainedMail(entry,refreshHistory){
 const {box,back}=modal('Email ricevuta');
 const content=el('div');box.append(content,btn('Chiudi',()=>back.remove(),'small'));
 const base='/cloudflare-mail/history/'+encodeURIComponent(entry.message_hash);
 api(base).then(r=>{
  const src=r.source||{};
  content.append(node('h3','',src.subject||'Senza oggetto'),
    node('p','sub','Mittente: '+(src.sender||'Non disponibile')+' · '+(src.date||'')),
    node('p','sub','Testo disponibile fino al '+r.retained_until+' UTC. Allegati non conservati; testo analizzabile fino a 14.000 caratteri.'),
    el('pre',{style:'white-space:pre-wrap;overflow-wrap:anywhere;max-height:40vh;overflow:auto'},src.text||''));
  const linked=el('div');linked.append(node('h3','','Attività già generate'));
  if(!r.linked_tasks?.length)linked.append(node('p','sub','Nessuna attività collegata'));
  for(const t of r.linked_tasks||[]){
   const row=el('div',{class:'rowtask'},[node('span','taskmain',t.task_id==null?'Attività eliminata':(t.title||'Attività')+' · '+t.status)]);
   if(t.task_id!=null)row.append(btn('Apri attività',async()=>{try{const task=await api('/tasks/'+t.task_id);taskForm(task)}catch(e){msg(e.message,true)}},'small'));
   linked.append(row);
  }
  content.append(linked);
  if(!['queued','processing','retry'].includes(r.status)){
   const result=el('div');
   const preview=btn('Rianalizza con il prompt salvato',async()=>{
    preview.disabled=true;result.replaceChildren(node('p','sub','Rianalisi in corso…'));
    try{const a=await api(base+'/reanalyze',{method:'POST'});showMailProposals(result,a);
     result.append(node('p','sub','Le attività già create non sono modificate. È possibile aprirle e correggerle manualmente.'))}
    catch(e){result.replaceChildren(node('p','sub',e.message))}finally{preview.disabled=false}
   },'primary');
   const actions=el('div',{class:'actions'},[preview]);
   if(['processed','failed'].includes(r.status)&&!r.linked_tasks?.length&&!entry.tasks_created&&!entry.duplicates)actions.append(btn('Rimetti in coda',async()=>{
    if(!confirm('Rielaborare questo messaggio e creare le attività proposte, da verificare?'))return;
    try{await api(base+'/requeue',{method:'POST'});back.remove();await refreshHistory();msg('Email rimessa in coda')}catch(e){msg(e.message,true)}
   },'small'));
   actions.append(btn('Elimina testo email',async()=>{
    if(!confirm('Eliminare il testo conservato? Il registro e le attività generate rimarranno.'))return;
    try{await api(base+'/text',{method:'DELETE'});back.remove();await refreshHistory();msg('Testo eliminato')}catch(e){msg(e.message,true)}
   },'small'));
   content.append(actions,result);
  }
 }).catch(e=>content.append(node('p','sub',e.message)));
}
function gmailAutoSettings(main){
 if(S.me.role!=='admin')return;
 const panel=el('section',{class:'card',style:'margin-top:15px'});
 const grid=el('div',{class:'formgrid'}),activity=el('div',{class:'full'});
 panel.append(node('h2','','Gmail → scadenze automatiche'),
  node('p','sub','Accesso Google OAuth senza password Gmail. NextDo elabora solo messaggi con etichetta NextDo; il permesso Google gmail.readonly consente tecnicamente la lettura dell’intera casella. Prima di inoltrare email UNIVR verificare le autorizzazioni dell’Ateneo.'),
  node('p','sub','Sono elaborati soltanto i messaggi ricevuti dopo l’attivazione. Controllo automatico ogni 5 minuti. Le proposte vengono create come scadenze private Da verificare, senza assegnazioni automatiche.'),
  grid,activity);
 main.append(panel);
 const load=async()=>{
  try{
   const cfg=await api('/gmail-auto/config');
   grid.replaceChildren();
   const client=input('client_id','Client ID OAuth Google',cfg.client_id||'');
   const secret=input('client_secret','Lascia vuoto per mantenere il segreto salvato','','password');
   secret.setAttribute('autocomplete','new-password');
   const redirect=input('redirect_uri','URI di reindirizzamento OAuth',
     cfg.redirect_uri||location.origin+'/api/gmail-auto/callback');
   const enabled=el('input',{type:'checkbox',checked:cfg.enabled});
   grid.append(node('p','sub','Collegamento: '+(cfg.connected?'Gmail connesso'+(cfg.account?' — '+cfg.account:''):'non collegato')+
       ' · Client Secret: '+(cfg.client_secret_configured?'presente':'da configurare')),
      field('Google OAuth Client ID',client),field('Google OAuth Client Secret',secret),
      field('Redirect URI HTTPS (da registrare in Google Cloud)',redirect),
      el('label',{class:'full'},[enabled,' Abilita acquisizione automatica']));
   const actions=el('div',{class:'actions full'});
   const save=btn('Salva impostazioni Gmail',async()=>{
    try{
     const result=await api('/gmail-auto/config',{method:'POST',body:JSON.stringify({
      client_id:client.value.trim(),client_secret:secret.value,redirect_uri:redirect.value.trim(),enabled:enabled.checked
     })});
     msg(result.enabled?'Controllo Gmail attivo ogni 5 minuti':'Impostazioni Gmail salvate');
     await load();
    }catch(e){msg(e.message,true)}
   },'primary');
   actions.append(save);
   actions.append(btn('Collega Google',async()=>{
    try{
     const r=await api('/gmail-auto/connect',{method:'POST'});
     window.location.assign(r.authorization_url);
    }catch(e){msg(e.message,true)}
   },'small'));
   if(cfg.connected){
    const run=btn('Controlla adesso',async()=>{
     run.disabled=true;
     try{
      const r=await api('/gmail-auto/run',{method:'POST'});
      msg('Scadenze create: '+r.created+' · email elaborate: '+r.processed+
       ' · duplicati: '+r.duplicates+' · errori: '+r.errors);
      await refresh();await loadHistory();
     }catch(e){msg(e.message,true)}finally{run.disabled=false}
    },'small');
    if(!cfg.enabled)run.disabled=true;
    actions.append(run,btn('Disconnetti Gmail',async()=>{
     if(!confirm('Disattivare l’automazione e revocare il collegamento locale? Le attività già create resteranno.'))return;
     try{await api('/gmail-auto/disconnect',{method:'POST'});await load();}catch(e){msg(e.message,true)}
    },'small'));
   }
   grid.append(actions);
   await loadHistory();
  }catch(e){grid.replaceChildren(node('p','sub','Impostazioni Gmail non disponibili: '+e.message))}
 };
 const loadHistory=async()=>{
  activity.replaceChildren(node('h3','','Registro acquisizioni Gmail'));
  try{
   const rows=await api('/gmail-auto/history');
   if(!rows.length){activity.append(node('p','sub','Nessun messaggio acquisito.'));return}
   for(const item of rows.slice(0,20)){
    const status={processed:'Elaborata',duplicate:'Duplicata',ignored:'Esclusa',skipped:'Non analizzabile',processing:'In elaborazione',error:'Errore'}[item.status]||item.status;
    activity.append(el('div',{class:'rowtask'},[
     node('span','taskmain',status+' · Gmail '+item.gmail_id+' · attività create: '+item.created+
       (item.error?' · '+item.error:'')),
     node('span','sub',item.completed_at||'')
    ]));
   }
  }catch(e){activity.append(node('p','sub','Impossibile leggere il registro: '+e.message))}
 };
 load();
}

function automaticICSSettings(main){
 if(S.me.role!=='admin')return;
 const card=el('section',{class:'card',style:'margin-top:15px'});
 main.append(card);
 async function draw(){
  card.replaceChildren(node('h2','','Regola automatica · Email → ICS'),node('p','sub','Per le nuove email ricevute tramite Cloudflare, invia un unico ICS con le nuove voci con data verificabile nel testo. Le proposte restano Da verificare; nessun invito, nessuna risposta al mittente originale. Le date trascorse, le richieste senza data e le proposte ambigue non vengono inviate.'));
  try{
   const cfg=await api('/outbound-mail/automatic-ics');
   card.append(tag(cfg.enabled?'Regola attiva':'Regola disattivata',cfg.enabled?'low':''));
   if(!cfg.ready)card.append(node('p','sub','Prima completare il collaudo e abilitare la posta in uscita.'));
   const recipient=select('auto_recipient',[['','Selezionare destinatario'],...cfg.recipients.map(x=>[x,x])],cfg.recipient);
   const enable=el('input',{type:'checkbox',checked:cfg.enabled});
   const consent=el('input',{type:'checkbox'});
   card.append(field('Destinatario fisso verificato',recipient),el('label',{class:'rowtask'},[enable,' Abilita invio automatico ICS']),el('label',{class:'rowtask'},[consent,' Autorizzo l’invio di titoli e date delle proposte AI a questo indirizzo, senza testo originale.']));
   const save=btn('Salva regola',async()=>{save.disabled=true;try{
    if(enable.checked&&(!recipient.value||!consent.checked))return msg('Scegliere il destinatario e confermare l’autorizzazione',true);
    await api('/outbound-mail/automatic-ics',{method:'POST',body:JSON.stringify({enabled:enable.checked,recipient:recipient.value,confirmed:consent.checked})});
    msg('Regola salvata');await draw()
   }catch(e){msg(e.message,true)}finally{save.disabled=false}},'primary');
   card.append(save,node('h3','','Registro regola automatica'));
   if(!cfg.history.length)card.append(node('p','sub','Nessun invio automatico registrato.'));
   for(const row of cfg.history)card.append(node('p','sub',fmt(new Date(row.created_epoch*1000).toISOString())+' · '+row.message_hash.slice(0,12)+' · '+row.detail));
  }catch(e){card.append(node('p','sub',e.message))}
 }
 draw()
}
function outboundMailSettings(main){
 if(S.me.role!=='admin')return;
 const card=el('section',{class:'card',style:'margin-top:15px'});
 card.append(node('h2','','Posta in uscita · Cloudflare'),node('p','sub','Invio manuale ICS tramite API REST. Non modifica la ricezione Cloudflare. I destinatari devono essere verificati anche nel pannello Cloudflare.'));
 const form=el('div',{class:'formgrid'}),history=el('div',{});card.append(form,history);main.append(card);
 async function load(){
  try{
   const cfg=await api('/outbound-mail/config');form.replaceChildren();
   const account=input('account','Account ID Cloudflare',cfg.account_id);
   const sender=input('sender','Mittente del sottodominio dedicato',cfg.sender);
   const token=input('token',cfg.token_configured?'Token salvato (lascia vuoto per mantenerlo)':'Token API','','password');token.autocomplete='new-password';
   const recipients=el('textarea',{class:'field',rows:'3',placeholder:'Un indirizzo verificato per riga'});recipients.value=cfg.recipients.join('\n');
   const state=node('p','sub',cfg.enabled?'Invio abilitato':cfg.tested?'Prova accettata: confermare ricezione':'Invio disabilitato · collaudo necessario');
   const save=btn('Salva configurazione',async()=>{save.disabled=true;try{
    await api('/outbound-mail/config',{method:'POST',body:JSON.stringify({account_id:account.value,sender:sender.value,token:token.value,recipients:recipients.value.split(/[\n,;]+/).map(x=>x.trim()).filter(Boolean)})});token.value='';msg('Configurazione salvata. Eseguire il collaudo.');await load()
   }catch(e){msg(e.message,true)}finally{save.disabled=false}},'primary');
   form.append(state,field('Account ID',account),field('Mittente',sender),field('Token API · Email Sending Edit',token),field('Destinatari verificati e autorizzati',recipients),save);
   if(cfg.token_configured){
    const recipient=select('test_recipient',[['','Scegli destinatario di prova'],...cfg.recipients.map(x=>[x,x])]);
    const test=btn('Invia email di prova con ICS',async()=>{
     if(!recipient.value)return msg('Seleziona destinatario di prova',true);
     if(!confirm('Inviare un solo evento fittizio a '+recipient.value+'?'))return;
     test.disabled=true;
     try{const result=await api('/outbound-mail/test',{method:'POST',body:JSON.stringify({recipient:recipient.value,request_id:outboundRequestId()})});msg(result.detail,!['delivered','queued'].includes(result.status));await load()}catch(e){msg(e.message,true);await showHistory()}finally{test.disabled=false}
    },'small');
    form.append(field('Destinatario test',recipient),test);
    if(cfg.tested&&!cfg.enabled){
     const received=el('input',{type:'checkbox'});
     const enable=btn('Abilita invio manuale',async()=>{if(!received.checked)return;try{await api('/outbound-mail/enable',{method:'POST',body:JSON.stringify({enabled:true,confirmed_received:true})});await load();msg('Invio manuale abilitato')}catch(e){msg(e.message,true)}},'primary');
     enable.disabled=true;received.onchange=()=>enable.disabled=!received.checked;
     form.append(el('label',{class:'full'},[received,' Ho ricevuto e aperto correttamente l’ICS di prova']),enable);
    }
    if(cfg.enabled)form.append(btn('Disabilita invio',async()=>{try{await api('/outbound-mail/enable',{method:'POST',body:JSON.stringify({enabled:false})});await load()}catch(e){msg(e.message,true)}},'danger'));
   }
   await showHistory()
  }catch(e){form.replaceChildren(node('p','sub',e.message))}
 }
 async function showHistory(){
  history.replaceChildren(node('h3','','Registro invii'),node('p','sub','Consegna o accodamento riportati da Cloudflare; se l’esito è incerto non ripetere automaticamente. Registro senza titoli o contenuto, conservato 90 giorni (pulizia al prossimo invio).'));
  try{const rows=await api('/outbound-mail/history');if(!rows.length)history.append(node('p','sub','Nessun invio registrato.'));for(const row of rows)history.append(node('p','sub',fmt(new Date(row.created_epoch*1000).toISOString())+' · '+(row.kind==='test'?'Prova':(row.kind==='auto'?'ICS automatico':'ICS')+' ('+row.task_count+')')+' · '+row.detail))}catch(e){history.append(node('p','sub',e.message))}
 }
 load()
}
function cloudflareMailSettings(main){
 if(S.me.role!=='admin')return;
 const card=el('section',{class:'card',style:'margin-top:15px'});
 card.append(node('h2','','Posta in arrivo Cloudflare → Scadenze'),
  node('p','sub','Ricezione diretta delle email senza Gmail, OAuth Google o password della posta. Cloudflare inoltra le sole comunicazioni autorizzate a NextDo tramite un Worker firmato. GroqCloud elabora il testo su server esterni: verificare le autorizzazioni prima di inoltrare comunicazioni istituzionali.'),
  node('p','sub','Per evitare conflitti DNS, usare un sottodominio dedicato alle email. Esempio non attivo: scadenze@posta.archis.uk.'),
  node('p','sub','La ricezione va abilitata solo dopo la configurazione del Worker su Cloudflare. Ogni scadenza sarà privata dell’Admin e contrassegnata «Da verificare».'));
 const grid=el('div',{class:'formgrid'}),secretArea=el('div',{class:'full'}),
  historyArea=el('div',{class:'full'});
 card.append(grid,secretArea,historyArea);
 main.append(card);
 async function showHistory(){
  historyArea.replaceChildren(node('h3','','Registro email ricevute'),node('p','sub','Testo cifrato per 30 giorni; nessun allegato conservato. Le attività e il registro restano dopo la scadenza del testo.'));
  try{
   const history=await api('/cloudflare-mail/history');
   if(!history.length){historyArea.append(node('p','sub','Nessun messaggio ricevuto.'));return}
   for(const e of history.slice(0,20)){
    const names={queued:'In coda',processing:'In analisi',processed:'Elaborata',
     duplicate:'Duplicata',retry:'Da ritentare',failed:'Errore definitivo'};
    const meta=(names[e.status]||e.status)+' · '+(e.received_at||'')+
       ' · attività create: '+e.tasks_created+
       (e.error?' · '+e.error:'');
    const row=el('div',{class:'rowtask'},[el('div',{class:'taskmain'},[
      node('strong','',e.subject||'Oggetto non disponibile'),
      node('p','sub',meta),
      node('p','sub',e.message_hash.slice(0,12)+' · '+(e.text_available?'Testo disponibile':'Testo non conservato'))
    ])]);
    if(e.text_available)row.append(btn('Visualizza / rianalizza',()=>openRetainedMail(e,showHistory),'small'));
    else if(e.status==='processed'&&!e.tasks_created&&!e.duplicates)row.append(node('p','sub','Reinoltrare l’email per analizzarla di nuovo.'));
    historyArea.append(row);
   }
  }catch(e){historyArea.append(node('p','sub','Registro non disponibile: '+e.message))}
 }
 async function load(){
  try{
   const cfg=await api('/cloudflare-mail/config');
   grid.replaceChildren();
   const recipient=input('recipient','Esempio: scadenze@posta.archis.uk',cfg.recipient||'');
   const sender=input('allowed_sender','Separa gli indirizzi con una virgola',cfg.allowed_sender||'');
   const active=el('input',{type:'checkbox',checked:cfg.enabled});
   const url=el('input',{class:'field',readOnly:true,value:location.origin+cfg.ingest_path});
   grid.append(node('p','sub','Segreto Worker: '+(cfg.secret_configured?'configurato':'non configurato')+
      ' · Ricezione: '+(cfg.enabled?'attiva':'disattivata')),
    field('Indirizzo email dedicato (da creare in Cloudflare)',recipient),
    field('Mittenti autorizzati per gli inoltri',sender),
    field('Endpoint HTTPS NextDo per il Worker',url),
    el('label',{class:'full'},[active,' Abilita la ricezione automatica']));
   const actions=el('div',{class:'actions full'});
   actions.append(btn('Salva impostazioni Cloudflare',async()=>{
    try{
     await api('/cloudflare-mail/config',{method:'POST',body:JSON.stringify({
      recipient:recipient.value,allowed_sender:sender.value,enabled:active.checked
     })});
     msg('Impostazioni Cloudflare salvate');await load();
    }catch(e){msg(e.message,true)}
   },'primary'));
   actions.append(btn('Genera / rigenera segreto Worker',async()=>{
    if(!confirm('Il segreto precedente, se presente, cesserà di funzionare. NextDo disattiverà la ricezione finché non avrai aggiornato il Worker. Continuare?'))return;
    try{
     const result=await api('/cloudflare-mail/secret',{method:'POST'});
     secretArea.replaceChildren();
     const box=el('textarea',{class:'field',readOnly:true,rows:'3'});
     box.value=result.secret;
     const copy=btn('Copia segreto',async()=>{
      try{await navigator.clipboard.writeText(box.value);msg('Segreto copiato')}catch(e){box.select();msg('Seleziona e copia il segreto mostrato',true)}
     },'small');
     secretArea.append(node('p','sub','Copia ora questo segreto nelle variabili protette del Worker Cloudflare come NEXTDO_SIGNING_SECRET. Non comparirà più dopo aver lasciato questa schermata.'),box,copy);
     msg('Segreto generato. Ricezione disattivata fino a nuova conferma.');
     active.checked=false;
    }catch(e){msg(e.message,true)}
   },'small'));
   actions.append(btn('Ritenta email fallite',async()=>{
    if(!confirm('Rimettere in coda i messaggi non elaborati per errori? Non verranno creati duplicati.'))return;
    try{
     const r=await api('/cloudflare-mail/retry-failed',{method:'POST'});
     msg('Email rimesse in coda: '+r.queued);
     await showHistory();
    }catch(e){msg(e.message,true)}
   },'small'));
   actions.append(btn('Elabora la coda adesso',async()=>{
    try{
     const result=await api('/cloudflare-mail/process',{method:'POST'});
     msg('Elaborate: '+result.processed+' · scadenze create: '+result.created+
       ' · errori: '+result.errors);
     await refresh();await showHistory();
    }catch(e){msg(e.message,true)}
   },'small'));
   grid.append(actions,
    el('div',{class:'full'},[el('a',{
      href:'https://github.com/lukebwines/NextDo/blob/main/docs/cloudflare-mail.md',
      target:'_blank',rel:'noopener noreferrer',
      text:'Guida alla configurazione del Worker Cloudflare'
    })]));
   await showHistory();
  }catch(e){grid.replaceChildren(node('p','sub','Impostazioni Cloudflare non disponibili: '+e.message))}
 }
 load();
}

function settings(main){
 main.classList.add('settings-page');
 const admin=S.me.role==='admin';
 const categories=[['general','user','Profilo e preferenze','Account, password, tema'],['notifications','bell','Notifiche','Promemoria e avvisi'],['android','calendar','App Android','Dispositivi e notifiche push'],...(admin?[
 ['users','user','Utenti e organizzazione','Account, gruppi, collaboratori'],
 ['incoming','note','Posta in entrata','Cloudflare e IMAP'],
 ['outgoing','paperclip','Posta in uscita','Cloudflare e registro'],
 ['ai','alert','Intelligenza artificiale','GroqCloud e prompt'],
 ['automation','clock','Automazioni','Regola email → ICS e ricorrenze'],
 ['integrations','list','Integrazioni','Microsoft Lists e monitor'],
 ['backup','archive','Sicurezza e backup','Esportazione e ripristino']
 ]:[])];
 if(!categories.some(c=>c[0]===S.settingsTab))S.settingsTab='general';
 const shell=el('div',{class:'settings-shell'}),nav=el('nav',{class:'settings-nav','aria-label':'Categorie impostazioni'}),content=el('div',{class:'settings-content'});
 const search=input('settings-search','Cerca una categoria…');search.setAttribute('aria-label','Cerca impostazioni');
 nav.append(search);
 const items=el('div',{class:'settings-nav-list'});nav.append(items);
 for(const [id,icon,title,desc] of categories){const b=el('button',{type:'button',class:'settings-link '+(S.settingsTab===id?'active':''),'aria-current':S.settingsTab===id?'page':'false',onclick:()=>{S.settingsTab=id;render()}},[ico(icon),el('span',{},[node('strong','',title),node('small','',desc)]),ico('chevron')]);items.append(b)}
 search.addEventListener('input',()=>{const q=search.value.toLocaleLowerCase('it').trim();for(const item of items.children)item.hidden=!item.textContent.toLocaleLowerCase('it').includes(q)});
 const chosen=categories.find(c=>c[0]===S.settingsTab);
 content.append(el('div',{class:'settings-heading'},[ico(chosen[1]),el('div',{},[node('h2','',chosen[2]),node('p','sub',chosen[3])])]));
 function section(title,desc=''){const card=el('section',{class:'card settings-card'},[node('h2','',title),...(desc?[node('p','sub',desc)]:[])]);content.append(card);return card}
 if(S.settingsTab==='general'){
  const card=section('Preferenze','Account indipendente da Home Assistant. Proteggere l’accesso remoto tramite HTTPS e Cloudflare Access.');
  card.append(themeButton(),node('p','sub','Versione NextDo 0.2.0-test'));
  NextDoWorkspace.settings(content,'profile')
 }else if(S.settingsTab==='notifications'){
  const card=section('Notifiche');if(admin)card.append(btn('Elabora promemoria',async()=>{try{const r=await api('/reminders/process',{method:'POST'});msg('Promemoria creati: '+r.processed);render()}catch(e){msg(e.message,true)}},'small'));
  api('/notifications').then(n=>{if(!n.length)card.append(node('p','muted','Nessun promemoria'));for(const item of n)card.append(el('div',{class:'rowtask'},[node('span','taskmain',item.message),tag(item.seen?'Letta':'Nuova'),btn('Segna letta',async()=>{await api('/notifications/'+item.id+'/read',{method:'POST'});render()},'small')]))}).catch(e=>card.append(node('p','sub',e.message)))
 }else if(S.settingsTab==='android'){
  const card=section('NextDo Android · Professionale','Associa e gestisci i dispositivi; l’area Viaggi rimane invariata.');card.append(btn('Dispositivi e associazione',workMobileEditor,'primary'));if(admin)card.append(btn('Configura push Firebase',workPushEditor,'small'))
 }else if(admin){
  if(S.settingsTab==='users'){const card=section('Gestione organizzazione');card.append(btn('+ Utente',userForm,'primary'),btn('Gruppi',()=>changeView('groups'),'small'));NextDoWorkspace.settings(content,'organization')}
  if(S.settingsTab==='incoming'){cloudflareMailSettings(content);emailIntakeSettings(content,'imap');const legacy=el('details',{class:'card settings-details'},[node('summary','','Gmail OAuth · configurazione facoltativa')]);content.append(legacy);legacy.addEventListener('toggle',()=>{if(legacy.open&&!legacy.dataset.loaded){legacy.dataset.loaded='1';gmailAutoSettings(legacy)}})}
  if(S.settingsTab==='outgoing')outboundMailSettings(content);
  if(S.settingsTab==='ai'){emailIntakeSettings(content,'ai');emailPromptSettings(content)}
  if(S.settingsTab==='automation'){automaticICSSettings(content);const card=section('Ricorrenze');card.append(btn('Avanza ricorrenze completate',async()=>{try{const r=await api('/recurrences/process',{method:'POST'});msg('Attività avanzate: '+r.advanced);await refresh();render()}catch(e){msg(e.message,true)}}))}
  if(S.settingsTab==='integrations'){NextDoMicrosoft.settings(content);section('Monitor NextDo').append(btn('Genera monitor',displayForm))}
  if(S.settingsTab==='backup'){const card=section('Backup e ripristino','Scaricare una copia prima di importare un archivio.');card.append(btn('Scarica backup',async()=>{try{const r=await api('/backup');const blob=await r.blob(),url=URL.createObjectURL(blob),a=el('a',{href:url,download:'nextdo-backup.zip'});a.click();setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){msg(e.message,true)}}),btn('Importa backup NextDo',restoreForm,'primary'))}
 }
 shell.append(nav,content);main.append(shell)
}

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

async function workMobileEditor(){
 const {box,back}=modal('NextDo Android · Professionale');
 const code=node('p','sub','Genera un codice monouso valido 5 minuti. Il dispositivo avrà accesso in sola lettura alle scadenze e agli appuntamenti visibili nel tuo account, per 30 giorni. L’associazione Viaggi non cambia.');
 const list=el('div');
 const refresh=async()=>{try{const devices=await api('/work-mobile/devices');list.replaceChildren();for(const d of devices){list.append(el('div',{class:'rowtask'},[node('div','taskmain',d.label+' · '+(d.revoked?'Revocato':d.expires*1000<=Date.now()?'Scaduto':'Attivo fino al '+new Date(d.expires*1000).toLocaleString('it-IT'))),...(!d.revoked?[btn('Revoca',async()=>{if(!confirm('Revocare questo dispositivo professionale?'))return;try{await api('/work-mobile/devices/'+encodeURIComponent(d.id)+'/revoke',{method:'POST'});await refresh()}catch(e){msg(e.message,true)}},'small')]:[])]))}}catch(e){msg(e.message,true)}};
 if(S.me.role==='admin')box.append(btn('Configura push Firebase',workPushEditor,'small'));
 box.append(code,btn('Genera codice',async()=>{try{const r=await api('/work-mobile/pair',{method:'POST'});const inputCode=el('input',{class:'field',value:r.code,readonly:'readonly'});code.replaceChildren(document.createTextNode('Codice monouso (5 minuti): '),inputCode);inputCode.select()}catch(e){msg(e.message,true)}},'primary'),list,btn('Chiudi',()=>back.remove(),'small'));await refresh();
}

function workAckButton(t){
 if(t.work_acknowledged)return tag('Presa visione','normal');
 return btn('Presa visione',async()=>{try{await api('/work-mobile/ack/'+t.id,{method:'POST',body:JSON.stringify({revision:t.work_revision})});await refresh();render()}catch(e){msg(e.message,true)}},'small');
}
async function workPushEditor(){
 const {box,back}=modal('Push Firebase · NextDo');
 const status=node('p','sub','Caricamento…');
 const android=el('input',{type:'file',accept:'.json,application/json',class:'field'}),service=el('input',{type:'file',accept:'.json,application/json',class:'field'});
 const refreshStatus=async()=>{try{const r=await api('/work-mobile/push/config');status.textContent=r.configured?'Configurato: '+r.project_id+' (consegna effettiva da verificare sul telefono)':'Firebase non configurato'}catch(e){status.textContent=e.message}};
 box.append(status,node('p','sub','Registra in Firebase un’app Android con pacchetto uk.archis.nextdoviaggi. Carica google-services.json e la chiave JSON del service account autorizzato a Firebase Cloud Messaging. La chiave privata resta sul Raspberry, non viene inclusa nell’APK. Google riceve solo token e segnale generico di aggiornamento.'),
 field('google-services.json',android),field('Service account JSON',service),
 btn('Salva configurazione',async()=>{try{if(!android.files[0]||!service.files[0])throw Error('Seleziona entrambi i file');if(android.files[0].size>100000||service.files[0].size>100000)throw Error('File troppo grande');await api('/work-mobile/push/config',{method:'POST',body:JSON.stringify({android:JSON.parse(await android.files[0].text()),service:JSON.parse(await service.files[0].text())})});android.value='';service.value='';await refreshStatus();msg('Configurazione salvata. Sincronizza gli avvisi sul telefono.')}catch(e){msg(e.message,true)}},'primary'),
 btn('Disabilita push',async()=>{if(!confirm('Rimuovere configurazione e registrazioni push? I promemoria locali rimangono attivi.'))return;try{await api('/work-mobile/push/disable',{method:'POST'});await refreshStatus()}catch(e){msg(e.message,true)}},'small'),btn('Chiudi',()=>back.remove(),'small'));
 await refreshStatus();
}
