/* Private, native NextDo view. No localStorage, no work task integration. */
const NextDoPersonal=(()=>{
 let generation=0,timer=null,main=null,trip=null,selected='',tab='giornata',busy=false;
 const path='/personal';
 const clone=x=>JSON.parse(JSON.stringify(x));
 const uid=()=>crypto.getRandomValues(new Uint32Array(2)).join('-');
 const card=(title,...children)=>el('section',{class:'card',style:'margin-bottom:12px'},[node('h2','',title),...children]);
 const toolbar=(...children)=>el('div',{class:'toolbar'},children);
 const safeLink=(url,label)=>{try{const p=new URL(url);if(p.protocol==='https:'&&!p.username&&!p.password)return el('a',{class:'btn small',href:p.href,target:'_blank',rel:'noopener noreferrer',text:label})}catch{}return null};
 const doc=(name,label='Apri PDF')=>name?el('a',{class:'btn small',href:'api/personal/trips/'+encodeURIComponent(trip.manifest.trip.id)+'/documents/'+encodeURIComponent(name),target:'_blank',rel:'noopener noreferrer',text:label}):null;
 const paragraph=(s)=>node('p','sub',s||'');
 const lines=a=>el('div',{},(a||[]).map(([k,v])=>el('p',{},[node('strong','',k+': '),String(v)])));
 const report=e=>{msg(e.message,true);if(e.message.includes('bloccata')){trip=null;render(main)}};
 function resetTimer(){clearTimeout(timer);timer=setTimeout(()=>{lock();if(S.view==='personal'&&main?.isConnected)render(main)},300000)}
 async function lock(){generation++;clearTimeout(timer);trip=null;selected='';busy=false;document.querySelectorAll('[data-personal-modal]').forEach(x=>x.remove());if(main?.isConnected)main.querySelector('#personal-content')?.replaceChildren();try{await api(path+'/lock',{method:'POST'})}catch{}}
 async function render(m){
  main=m;const token=++generation;let root=main.querySelector('#personal-content');if(!root){root=el('div',{id:'personal-content'});main.append(root)}root.replaceChildren(paragraph('Caricamento…'));
  try{
   const status=await api(path+'/status');if(token!==generation||!root.isConnected)return;
   if(!status.unlocked){trip=null;clearTimeout(timer);const pin=input('pin','6 cifre','','password');pin.setAttribute('inputmode','numeric');pin.maxLength=6;const confirmPin=input('confirm','Conferma PIN','','password');confirmPin.setAttribute('inputmode','numeric');confirmPin.maxLength=6;
    const f=el('form',{},[paragraph(status.configured?'Inserisci il PIN per accedere ai viaggi.':'Imposta un PIN privato di 6 cifre. Conservalo: il ripristino non è ancora disponibile.'),field('PIN',pin),...(status.configured?[]:[field('Conferma PIN',confirmPin)]),el('button',{class:'btn primary',type:'submit',text:status.configured?'Sblocca':'Imposta PIN'})]);
    f.addEventListener('submit',async e=>{e.preventDefault();try{await api(path+'/unlock',{method:'POST',body:JSON.stringify({pin:pin.value,confirm:confirmPin.value})});if(token===generation)render(main)}catch(e){report(e)}});root.replaceChildren(card('Area personale protetta',f));return;
   }
   resetTimer();await overview(root,token);
  }catch(e){if(token===generation)root.replaceChildren(paragraph(e.message))}
 }
 async function overview(root,token){
  const list=await api(path+'/trips');if(token!==generation||!root.isConnected)return;
  const pick=select('trip',[['','Seleziona viaggio'],...list.map(t=>[t.id,t.title+' · '+t.start+' — '+t.end])],trip?.manifest.trip.id||'');
  const file=el('input',{type:'file',accept:'.zip',class:'field'});
  const importBtn=btn('Importa ZIP',async()=>{if(!file.files[0])return msg('Seleziona un archivio ZIP',true);const data=new FormData();data.append('file',file.files[0]);try{const r=await api(path+'/trips/import',{method:'POST',body:data});await load(r.id);msg('Importato: '+r.bookings+' prenotazioni, '+r.days+' giornate, '+r.pdfs+' PDF')}catch(e){report(e)}},'primary');
  pick.addEventListener('change',()=>pick.value?load(pick.value):(trip=null,render(main)));
  root.replaceChildren(card('Area personale → Viaggi',toolbar(pick,btn('+ Nuovo viaggio',newTrip,'primary'),btn('Blocca',async()=>{await lock();render(main)})),toolbar(file,importBtn),paragraph('Importazione compatibile con Viaggi: manifest, prenotazioni, giornate, guide, PDF e note. Nessuna sovrascrittura automatica.')));
  if(trip)show(root);else root.append(paragraph('Seleziona un viaggio oppure importane uno.'));
 }
 async function load(id){const token=generation;try{const result=await api(path+'/trips/'+encodeURIComponent(id));if(token!==generation||S.view!=='personal')return;trip=result;selected=trip.manifest.days[0]?.date||'';tab='giornata';render(main)}catch(e){report(e)}}
 function editor(title,fields,submit){
  const {box,back}=modal(title);back.setAttribute('data-personal-modal','');const f=el('form',{class:'formgrid'});const controls={};
  for(const [key,label,value,kind] of fields){const c=kind==='textarea'?el('textarea',{class:'field',rows:'4',value:value??''}):input(key,'',value??'',kind||'text');controls[key]=c;f.append(field(label,c))}
  f.append(el('div',{class:'actions full'},[btn('Annulla',()=>back.remove()),el('button',{class:'btn primary',type:'submit',text:'Salva'})]));
  f.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;try{await submit(Object.fromEntries(Object.entries(controls).map(([k,c])=>[k,c.value])));back.remove()}catch(e){report(e)}finally{busy=false}});box.append(f)
 }
 function newTrip(){editor('Nuovo viaggio',[['title','Titolo',''],['subtitle','Destinazioni',''],['start','Partenza','','date'],['end','Rientro','','date']],async b=>{const r=await api(path+'/trips',{method:'POST',body:JSON.stringify(b)});await load(r.id)})}
 async function save(change){if(!trip)throw Error('Viaggio non selezionato');const token=generation,copy=clone(trip);change(copy);const r=await api(path+'/trips/'+encodeURIComponent(copy.manifest.trip.id),{method:'PUT',body:JSON.stringify(copy)});if(token!==generation||!trip)return;copy.revision=r.revision;trip=copy;resetTimer();render(main)}
 const fieldlist=(obj,spec)=>spec.map(([k,l,t])=>[k,l,obj[k]||'',t]);
 const pairsText=a=>(a||[]).map(x=>x.join(' | ')).join('\n');
 const readPairs=s=>s.split('\n').filter(x=>x.trim()).map(x=>{const n=x.indexOf('|');return n<0?[x.trim(),'']:[x.slice(0,n).trim(),x.slice(n+1).trim()]});
 function bookingEdit(b,index){
  const spec=[['type','Tipo'],['title','Titolo'],['ref','Riferimento'],['date','Data / periodo'],['status','Stato'],['place','Indirizzo / luogo'],['price','Prezzo'],['map','Link mappa HTTPS'],['source','Link fonte HTTPS'],['extraLink','Link aggiuntivo HTTPS'],['extraLabel','Etichetta link'],['doc','Nome PDF già caricato']];
  editor('Prenotazione',[...fieldlist(b,spec),['lines','Dettagli (etichetta | valore per riga)',pairsText(b.lines),'textarea']],v=>save(t=>{const n={...b,...v,id:b.id||'booking-'+uid(),lines:readPairs(v.lines)};if(index<0)t.manifest.bookings.push(n);else t.manifest.bookings[index]=n}))
 }
 function guideEdit(g,index){
  editor('Guida pratica',[...fieldlist(g,[['category','Categoria'],['title','Titolo'],['summary','Sintesi','textarea'],['doc','Nome PDF già caricato']]),['items','Indicazioni (etichetta | valore per riga)',pairsText(g.items),'textarea'],['links','Link (etichetta | URL HTTPS)',pairsText((g.links||[]).map(x=>[x.label,x.url])),'textarea']],v=>save(t=>{const n={...g,...v,id:g.id||'guide-'+uid(),severity:g.severity||'info',items:readPairs(v.items),links:readPairs(v.links).map(([label,url])=>({label,url}))};if(index<0)t.manifest.guides.push(n);else t.manifest.guides[index]=n}))
 }
 function dayEdit(d){editor('Giornata',fieldlist(d,[['place','Luogo'],['headline','Titolo'],['description','Descrizione','textarea']]),v=>save(t=>Object.assign(t.manifest.days.find(x=>x.date===d.date),v)))}
 function eventEdit(d,e,index){
  const refs=trip.manifest.bookings.map(b=>b.id+' = '+b.title).join('\n');const gs=trip.manifest.guides.map(g=>g.id+' = '+g.title).join('\n');
  editor('Evento',[...fieldlist(e,[['time','Orario'],['type','Tipo'],['title','Titolo'],['details','Dettagli','textarea'],['bid','ID prenotazione (facoltativo)'],['gid','ID guida (facoltativo)']]),['reference','Riferimenti disponibili (copia solo ID)',refs+'\n'+gs,'textarea']],v=>save(t=>{delete v.reference;const arr=t.manifest.days.find(x=>x.date===d.date).events;const n={...e,...v};if(index<0)arr.push(n);else arr[index]=n}))
 }
 function show(root){
  const m=trip.manifest,tr=m.trip,st=trip.state;
  const header=card(tr.title,paragraph(tr.subtitle+' · '+tr.start+' — '+tr.end),toolbar(...[['giornata','Itinerario'],['prenotazioni','Prenotazioni'],['guide','Guide e GPS'],['documenti','Documenti']].map(([k,l])=>btn(l,()=>{tab=k;render(main)},tab===k?'primary':'small')),el('a',{class:'btn small',href:'api/personal/trips/'+encodeURIComponent(tr.id)+'/export',download:'',text:'Esporta ZIP'})));
  root.append(header);
  if(tab==='prenotazioni'){
   root.append(toolbar(btn('+ Prenotazione',()=>bookingEdit({},-1),'primary')));
   for(const [i,b] of m.bookings.entries())root.append(card(b.title,paragraph([b.type,b.date,b.status,b.ref,b.place,b.price].filter(Boolean).join(' · ')),lines(b.lines),toolbar(doc(b.doc,b.original?'Documento originale':'Apri PDF'),safeLink(b.map,'Mappa / GPS'),safeLink(b.source,'Fonte'),safeLink(b.extraLink,b.extraLabel||'Link'),btn('Modifica',()=>bookingEdit(b,i),'small'))));
  }else if(tab==='guide'){
   root.append(toolbar(btn('+ Guida',()=>guideEdit({},-1),'primary')));
   for(const [i,g] of m.guides.entries())root.append(card(g.title,paragraph([g.category,g.severity,g.summary].filter(Boolean).join(' · ')),lines(g.items),toolbar(doc(g.doc),...(g.links||[]).map(l=>safeLink(l.url,l.label)),btn('Modifica',()=>guideEdit(g,i),'small'))));
  }else if(tab==='documenti'){
   const file=el('input',{type:'file',accept:'.pdf',class:'field'});
   root.append(card('Aggiungi PDF',toolbar(file,btn('Carica',async()=>{if(!file.files[0])return;const f=new FormData();f.append('file',file.files[0]);try{await api(path+'/trips/'+encodeURIComponent(tr.id)+'/documents',{method:'POST',body:f});await load(tr.id);tab='documenti';render(main)}catch(e){report(e)}},'primary'))));
   const docs=new Map();for(const b of m.bookings)if(b.doc)docs.set(b.doc,b.title);for(const g of m.guides)if(g.doc)docs.set(g.doc,g.title);for(const d of m.documents)docs.set(d.file,d.title);
   for(const [name,title] of docs)root.append(card(title,paragraph(name),doc(name)));
  }else{
   const d=m.days.find(x=>x.date===selected)||m.days[0];if(!d)return;
   root.append(toolbar(...m.days.map(day=>btn(day.date.slice(8)+'/'+day.date.slice(5,7),()=>{selected=day.date;render(main)},day.date===d.date?'primary':'small'))));
   root.append(card([d.date,d.place,d.headline].filter(Boolean).join(' · '),paragraph(d.description),toolbar(btn('Modifica giornata',()=>dayEdit(d),'small'),btn('+ Evento',()=>eventEdit(d,{},-1),'primary'))));
   for(const [i,e] of d.events.entries()){
    const b=m.bookings.find(x=>x.id===e.bid),g=m.guides.find(x=>x.id===e.gid);
    root.append(card([e.time,e.title].filter(Boolean).join(' · '),paragraph([e.type,e.warning?'ATTENZIONE':'',e.details].filter(Boolean).join(' · ')),toolbar(b&&doc(b.doc),b&&safeLink(b.map,'Mappa / GPS'),b&&safeLink(b.source,'Fonte'),b&&safeLink(b.extraLink,b.extraLabel||'Link'),g&&doc(g.doc,'PDF guida'),g&&btn('Guide',()=>{tab='guide';render(main)},'small'),btn('Modifica',()=>eventEdit(d,e,i),'small'))))
   }
   const checks=card('Checklist');for(const [i,c] of d.checks.entries()){
    const cb=el('input',{type:'checkbox',checked:(st.checks[d.date]||[]).includes(i)});cb.addEventListener('change',()=>save(t=>{const a=new Set(t.state.checks[d.date]||[]);cb.checked?a.add(i):a.delete(i);t.state.checks[d.date]=[...a]}).catch(report));checks.append(el('label',{class:'rowtask'},[cb,c]))
   }
   checks.append(btn('+ Voce',()=>editor('Nuovo promemoria',[['text','Testo','']],v=>save(t=>t.manifest.days.find(x=>x.date===d.date).checks.push(v.text))),'small'));root.append(checks);
   const notes=el('textarea',{class:'field',rows:'5',value:st.notes[d.date]||''});root.append(card('Note della giornata',notes,btn('Salva note',()=>save(t=>{t.state.notes[d.date]=notes.value}).catch(report),'primary')));
  }
 }
 return {render,lock};
})();
