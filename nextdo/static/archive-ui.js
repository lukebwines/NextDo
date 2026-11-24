'use strict';
/* All archive operations use server-side permissions and filtered selections. */
const NextDoArchive=(()=>{
 const periods=[['all','Tutto lo storico'],['7','Ultimi 7 giorni'],['30','Ultimi 30 giorni'],['90','Ultimi 90 giorni'],['year','Anno corrente'],['unknown','Data non disponibile']];
 const kinds=[['all','Tutti i tipi'],['agenda','Scadenze e appuntamenti'],['task','Attività e scadenze'],['appointment','Appuntamenti'],['note','Note']];
 const units=['B','KiB','MiB','GiB','TiB'];
 function bytes(n){n=Number(n)||0;let i=0;while(n>=1024&&i<units.length-1){n/=1024;i++}return n.toLocaleString('it-IT',{maximumFractionDigits:i?1:0})+' '+units[i]}
 function periodTitle(p){return p==='year'?'Completate · anno corrente':'Completate · '+p+' giorni'}
 function open(period='all',kind='all'){S.archivePeriod=period;S.archiveKind=kind;S.searchTerm='';changeView('archive')}
 function filters({period='all',kind='all',state='done',includeState=false}={}){
  const wrap=el('div',{class:'archive-filters'});
  const controls={period:select('archive-period',periods,period),month:el('input',{type:'month',class:'field',name:'archive-month'}),kind:select('archive-kind',kinds,kind),
   course_id:select('archive-course',[['','Tutti i CdS'],...S.courses.map(c=>[String(c.id),c.code+' — '+c.name])]),project_id:select('archive-project',[['','Tutti i progetti'],...S.projects.map(p=>[String(p.id),p.title])]),
   label:input('archive-label','Etichetta esatta'),query:input('archive-query','Cerca titolo o descrizione')};
  if(includeState)controls.state=select('archive-state',[['done','Completate'],['open','Non completate'],['all','Tutte le attività']],state);
  for(const [key,label] of Object.entries({state:'Stato',period:'Periodo',month:'Mese e anno',kind:'Tipo',course_id:'Corso di studio',project_id:'Progetto',label:'Etichetta',query:'Ricerca'}))if(controls[key]){
   controls[key].setAttribute('aria-label',label);wrap.append(field(label,controls[key]))
  }
  function params(){const q=new URLSearchParams({state});for(const [key,ctrl] of Object.entries(controls))if(ctrl.value)q.set(key,ctrl.value);return q}
  return {wrap,controls,params}
 }
 function card(title,description=''){return el('section',{class:'card archive-card'},[node('h2','',title),...(description?[node('p','sub',description)]:[])])}
 function preferences(main){
  const c=card('Dashboard · Attività completate','Il periodo riguarda la data di effettivo completamento, non la data di scadenza. Il conteggio non elimina alcuna attività.');
  const period=select('completed-period',periods.filter(x=>!['all','unknown'].includes(x[0])),S.archiveSummary.period);
  period.setAttribute('aria-label','Periodo contatore completate');
  c.append(field('Periodo del contatore',period),btn('Salva periodo',async()=>{try{await api('/archive/preferences',{method:'POST',body:JSON.stringify({period:period.value})});S.archiveSummary=await api('/archive/summary');msg('Periodo salvato')}catch(e){msg(e.message,true)}},'primary'));
  if(S.archiveSummary.unknown)c.append(node('p','sub',S.archiveSummary.unknown+' impegni completati senza data storica certa rimangono nell’Archivio, ma non nel contatore temporale.'));
  main.append(c)
 }
 function render(main){
  const c=card('Storico attività','Tutte le attività completate accessibili al tuo account. I filtri riguardano la data di completamento; le date storiche mancanti sono consultabili separatamente.');
  const f=filters({period:S.archivePeriod,kind:S.archiveKind});
  const results=el('div',{class:'archive-results','aria-live':'polite'});
  let page=1,requestId=0;
  async function load(reset=false){
   if(reset)page=1;S.archivePeriod=f.controls.period.value;S.archiveKind=f.controls.kind.value;
   const seq=++requestId;results.replaceChildren(node('p','sub','Caricamento archivio…'));
   const q=f.params();q.set('page',String(page));q.set('page_size','40');
   try{
    const res=await api('/archive/items?'+q);
    if(seq!==requestId)return;
    const max=Math.max(1,Math.ceil(res.total/res.page_size));
    if(page>max){page=max;return load()}
    results.replaceChildren(el('div',{class:'archive-result-head'},[node('strong','',res.total+' attività nello storico'),node('span','sub','Pagina '+page+' di '+max)]));
    for(const t of res.items){
     const row=taskrow(t);const date=node('span','archive-completion','Completata: '+(t.completed_at?fmt(t.completed_at):'data non disponibile'));
     row.querySelector('.taskmain').append(date);results.append(row)
    }
    if(!res.items.length)results.append(node('p','empty','Nessuna attività corrisponde ai filtri'));
    const prev=btn('← Precedente',()=>{page--;load()},'small');prev.disabled=page<=1;
    const next=btn('Successiva →',()=>{page++;load()},'small');next.disabled=page>=max;
    results.append(el('div',{class:'archive-pagination'},[prev,node('span','sub',String(page)+' / '+max),next]));
   }catch(e){if(seq===requestId)results.replaceChildren(node('p','sub',e.message))}
  }
  const exp=btn('Esporta selezione ZIP / Excel',()=>exportDialog(f.params()),'primary');
  c.append(f.wrap,el('div',{class:'actions'},[btn('Applica filtri',()=>load(true),'small'),exp]),results);
  for(const ctrl of Object.values(f.controls)){ctrl.addEventListener('change',()=>load(true));if(ctrl.tagName==='INPUT')ctrl.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();load(true)}})}
  main.append(c);load();
 }
 function exportDialog(q){
  const {box}=modal('Esportazione massiva');
  box.append(node('p','sub','Lo ZIP contiene l’indice Excel, una scheda testuale per attività e tutti gli allegati originali in cartelle ordinate per anno, mese e attività. Per le attività non completate si usa la data di creazione; i completamenti senza data certa hanno una cartella separata.'));
  const content=el('div',{},[node('p','sub','Verifica della selezione…')]);box.append(content);
  api('/archive/preview?'+q).then(p=>{
   content.replaceChildren(node('strong','',p.tasks+' attività · '+p.attachments+' allegati · '+bytes(p.bytes)),node('p','sub',p.eligible_cleanup+' allegati di attività completate potenzialmente rimovibili dopo verifica dello ZIP.'));
   if(p.missing)content.append(node('p','message error',p.missing+' allegati mancanti: esportazione bloccata.'));
   const list=el('div',{class:'archive-preview-list'});
   for(const t of p.sample)list.append(el('div',{class:'rowtask'},[node('span','taskmain',t.title),tag(t.attachments+' allegati')]));
   if(p.tasks>p.sample.length)list.append(node('p','sub','Anteprima delle prime '+p.sample.length+' attività. Il file include tutte le '+p.tasks+' attività selezionate.'));
   const details=el('details',{},[node('summary','','Anteprima della selezione'),list]);content.append(details);
   if(p.tasks&&!p.missing&&p.bytes<=p.limit_bytes){
    const download=el('a',{class:'btn primary archive-download',href:'api/archive/export?'+q,download:'',target:'_blank',rel:'noopener'},['Scarica ZIP ordinato']);
    content.append(download,node('p','sub','Il browser scarica il file direttamente. Aprirlo e conservarlo in una posizione sicura. Nessun allegato viene eliminato durante l’esportazione. Limite 500 MiB per selezione, inclusi i dati delle schede.'))
   }else if(p.bytes>p.limit_bytes)content.append(node('p','message','Selezione oltre 500 MiB: restringere il periodo o scegliere un progetto.'));
  }).catch(e=>content.replaceChildren(node('p','sub',e.message)))
 }
 function storage(main){
  const summary=card('Spazio occupato','Misurazione dei file nella cartella dati di NextDo. Lo spazio libero si riferisce al volume di archiviazione, condiviso con eventuali altri servizi.');
  const content=el('div',{},[node('p','sub','Misurazione in corso…')]);summary.append(content);
  const exportCard=card('Esporta archivio e allegati','Seleziona completate o tutte le attività visibili al tuo account. Nessun dato degli spazi personali altrui viene incluso.');
  const f=filters({includeState:true});exportCard.append(f.wrap,btn('Verifica selezione ed esporta',()=>exportDialog(f.params()),'primary'));
  const clean=card('Libera spazio dagli allegati','Prima scarica e conserva lo ZIP. Seleziona la copia effettivamente salvata: NextDo verifica i contenuti tramite SHA-256. Solo gli allegati di attività ancora completate e modificabili possono essere rimossi. Le attività e lo storico restano.');
  const file=el('input',{type:'file',class:'field',accept:'.zip,application/zip','aria-label':'ZIP salvato da verificare'});
  const verification=el('div',{class:'archive-verification'});
  let version=0;
  const check=btn('Verifica ZIP salvato',async()=>{
   const selected=file.files[0];if(!selected)return msg('Seleziona lo ZIP salvato',true);
   if(selected.size>550*1024*1024)return msg('ZIP superiore a 550 MiB',true);
   const seq=++version;check.disabled=true;file.disabled=true;verification.replaceChildren(node('p','sub','Verifica del contenuto in corso…'));
   try{
    const body=new FormData();body.append('file',selected);const result=await api('/archive/verify-export',{method:'POST',body});
    if(seq!==version)return;
    verification.replaceChildren(node('strong','',result.count+' allegati verificati · '+bytes(result.bytes)+' recuperabili'),node('p','sub',result.skipped+' non rimovibili o già assenti. Le attività restano nel database.'));
    if(!result.token)return;
    const list=el('div',{class:'archive-preview-list'});
    for(const a of result.sample)list.append(el('div',{class:'rowtask'},[node('span','taskmain',a.title+' — '+a.filename),tag(bytes(a.size))]));
    if(result.count>result.sample.length)list.append(node('p','sub','Prime '+result.sample.length+' voci; la conferma riguarda tutti i '+result.count+' allegati verificati. Consultare l’indice Excel dello ZIP.'));
    const confirmInput=input('archive-confirm','ELIMINA ALLEGATI');confirmInput.setAttribute('aria-label','Conferma eliminazione allegati');confirmInput.setAttribute('autocomplete','off');
    const del=btn('Elimina allegati verificati',async()=>{
     if(seq!==version||confirmInput.value!=='ELIMINA ALLEGATI')return msg('Digitare ELIMINA ALLEGATI',true);
     if(!window.confirm('Rimuovere '+result.count+' allegati dal server? La copia ZIP salvata resterà l’unico archivio esterno. Le attività non saranno eliminate.'))return;
     del.disabled=true;
     try{
      const out=await api('/archive/cleanup',{method:'POST',body:JSON.stringify({token:result.token,confirm:confirmInput.value})});
      verification.replaceChildren(node('p','message','Allegati rimossi: '+out.removed+' · Spazio file liberato: '+bytes(out.freed_bytes)+(out.unlink_failed?' · File non rimossi fisicamente: '+out.unlink_failed:'')));
      file.value='';await refresh();await measure();
     }catch(e){msg(e.message,true);del.disabled=false}
    },'danger');
    verification.append(list,node('p','sub','Verifica valida 20 minuti. Conservare lo ZIP in un archivio protetto. L’eliminazione non è annullabile da NextDo.'),field('Digitare ELIMINA ALLEGATI',confirmInput),del)
   }catch(e){verification.replaceChildren(node('p','message error',e.message))}finally{check.disabled=false;file.disabled=false}
  },'small');
  file.addEventListener('change',()=>{version++;verification.replaceChildren()});
  clean.append(field('Copia ZIP salvata',file),check,verification);
  const maintenance=card('Manutenzione SQLite','L’ottimizzazione verifica l’integrità e compatta le pagine libere. Non elimina attività o allegati. Può rallentare temporaneamente il servizio.');
  maintenance.append(btn('Verifica e ottimizza database',async()=>{
   const {box,back}=modal('Ottimizzazione database');
   const confirmInput=input('vacuum-confirm','OTTIMIZZA');
   box.append(node('p','sub','Effettuare prima un backup. Durante l’operazione gli accessi al database possono attendere. Digitare OTTIMIZZA per confermare.'),field('Conferma',confirmInput),btn('Ottimizza',async()=>{if(confirmInput.value!=='OTTIMIZZA')return msg('Digitare OTTIMIZZA',true);const button=box.querySelector('.btn.primary');button.disabled=true;try{const r=await api('/archive/vacuum',{method:'POST',body:JSON.stringify({confirm:confirmInput.value})});back.remove();msg('Integrità verificata · recuperati '+bytes(r.freed_bytes));await measure()}catch(e){msg(e.message,true);button.disabled=false}},'primary'))
  },'small'));
  async function measure(){
   try{
    const s=await api('/archive/storage');
    const entries=[['database','Database SQLite','#4aa5ff'],['attachments','Allegati attività','#f4b65f'],['backups','Backup locali','#ae8aff'],['personal','Area personale · file','#48cba0'],['other','Altri dati','#8595ab']];
    const bar=el('div',{class:'storage-bar','aria-label':'Distribuzione spazio dati'});
    for(const [k,label,color] of entries)if(s.parts[k])bar.append(el('span',{style:'width:'+100*s.parts[k]/Math.max(1,s.total)+'%;background:'+color,title:label+': '+bytes(s.parts[k])}));
    const legend=el('div',{class:'storage-legend'});
    for(const [k,label,color] of entries)legend.append(el('div',{class:'storage-line'},[el('span',{class:'storage-dot',style:'background:'+color}),node('span','',label),node('strong','',bytes(s.parts[k]))]));
    content.replaceChildren(el('div',{class:'storage-kpis'},[el('div',{},[node('span','sub','Dati NextDo'),node('strong','',bytes(s.total))]),el('div',{},[node('span','sub','Spazio libero volume'),node('strong','',bytes(s.disk_free))]),el('div',{},[node('span','sub','Allegati registrati · tutti gli account'),node('strong','',String(s.attachment_count))]),el('div',{},[node('span','sub','Attività completate visibili'),node('strong','',String(s.completed_visible))])]),bar,legend,node('p','sub','Volume: '+bytes(s.disk_total)+' complessivi · '+bytes(s.disk_used)+' utilizzati. Pagine SQLite libere (stima): '+bytes(s.db_reclaimable_estimate)+'.'),node('p','sub','Completate senza data storica certa: '+s.completed_unknown+'. L’area personale è misurata solo in aggregato: non è inclusa nell’esportazione o nella pulizia.'),btn('Aggiorna misurazione',measure,'small'))
   }catch(e){content.replaceChildren(node('p','message error',e.message),btn('Riprova',measure,'small'))}
  }
  main.append(summary,exportCard,clean,maintenance);measure();
 }
 return {open,render,preferences,storage,periodTitle};
})();
