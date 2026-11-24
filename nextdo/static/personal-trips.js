/* Private, native NextDo view. No localStorage, no work task integration. */
const NextDoPersonal=(()=>{
 let generation=0,timer=null,main=null,trip=null,selected='',tab='panoramica',busy=false;
 const path='/personal';
 const clone=x=>JSON.parse(JSON.stringify(x));
 const uid=()=>crypto.getRandomValues(new Uint32Array(2)).join('-');
 const card=(title,...children)=>el('section',{class:'card travel-card'},[node('h2','',title),...children]);
 const toolbar=(...children)=>el('div',{class:'toolbar'},children);
 const safeLink=(url,label)=>{try{const p=new URL(url);if(p.protocol==='https:'&&!p.username&&!p.password)return el('a',{class:'btn small',href:p.href,target:'_blank',rel:'noopener noreferrer',text:label})}catch{}return null};
 const doc=(name,label='Apri PDF')=>name?el('a',{class:'btn small',href:'api/personal/trips/'+encodeURIComponent(trip.manifest.trip.id)+'/documents/'+encodeURIComponent(name),target:'_blank',rel:'noopener noreferrer',text:label}):null;
 const paragraph=(s)=>node('p','sub',s||'');
 const lines=a=>el('div',{},(a||[]).map(([k,v])=>el('p',{},[node('strong','',k+': '),String(v)])));
 const report=e=>{msg(e.message,true);if(e.message.includes('bloccata')){trip=null;render(main)}};
 function resetTimer(){clearTimeout(timer);timer=setTimeout(()=>{lock();if(S.view==='personal'&&main?.isConnected)render(main)},300000)}
 async function lock(){geoKey='';generation++;clearTimeout(timer);trip=null;selected='';busy=false;document.querySelectorAll('[data-personal-modal]').forEach(x=>x.remove());if(main?.isConnected)main.querySelector('#personal-content')?.replaceChildren();try{await api(path+'/lock',{method:'POST'})}catch{}}
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
  root.classList.add('travel-shell');const imports=el('details',{class:'travel-import'},[node('summary','','Importa / trasferisci viaggio'),toolbar(file,importBtn)]);root.replaceChildren(el('div',{class:'travel-picker'},[el('div',{},[node('div','travel-kicker','AREA PERSONALE · VIAGGI'),pick]),toolbar(btn('+ Nuovo viaggio',newTrip,'primary'),btn('Servizi Viaggi',servicesEditor,'small'),btn('Blocca',async()=>{await lock();render(main)})),imports]));
  if(trip)show(root);else root.append(paragraph('Seleziona un viaggio oppure importane uno.'));
 }
 async function load(id){const token=generation;try{const result=await api(path+'/trips/'+encodeURIComponent(id));if(token!==generation||S.view!=='personal')return;trip=result;selected=trip.manifest.days[0]?.date||'';tab='panoramica';render(main)}catch(e){report(e)}}
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
 const dayFmt=d=>new Date(d+'T12:00:00').toLocaleDateString('it-IT',{weekday:'short',day:'numeric',month:'short'});
 const navLink=b=>b?.map?safeLink(b.map,'Naviga'):b?.place?safeLink('https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(b.place),'Cerca su Maps'):null;
 const allDocs=m=>{const docs=new Map();for(const b of m.bookings)if(b.doc)docs.set(b.doc,b.title);for(const g of m.guides)if(g.doc)docs.set(g.doc,g.title);for(const d of m.documents)docs.set(d.file,d.title);return docs};
 const switchTab=k=>{tab=k;render(main)};
 const tripURL=()=>path+'/trips/'+encodeURIComponent(trip.manifest.trip.id);
 async function reloadView(){const token=generation,id=trip.manifest.trip.id;const r=await api(path+'/trips/'+encodeURIComponent(id));if(token!==generation)return;trip=r;render(main)}
 function servicesEditor(){
  const {box,back}=modal('Servizi Viaggi');back.setAttribute('data-personal-modal','');
  const token=generation;
  box.append(paragraph('Le chiavi sono salvate cifrate sul Raspberry per il tuo account. Non vengono inserite nei file ZIP dei viaggi. GroqCloud continua a utilizzare la configurazione NextDo.'));
  (async()=>{try{
   const cfg=await api(path+'/services');if(token!==generation||!back.isConnected)return;
   const pex=input('pexels','Incolla API key Pexels','','password'),geo=input('geoapify','Incolla API key Geoapify','','password');
   const removeP=el('input',{type:'checkbox'}),removeG=el('input',{type:'checkbox'});
   box.append(field('Pexels — '+(cfg.pexels_configured?'Configurata':'Da configurare'),pex),safeLink('https://www.pexels.com/api/','Richiedi chiave Pexels'),el('label',{},[removeP,' Rimuovi chiave Pexels']),field('Geoapify — '+(cfg.geoapify_configured?'Configurata':'Da configurare'),geo),safeLink('https://myprojects.geoapify.com/','Richiedi chiave Geoapify'),el('label',{},[removeG,' Rimuovi chiave Geoapify']),paragraph('Lascia vuoto per conservare una chiave esistente. Wikimedia è il servizio fotografico predefinito e non richiede configurazione. Pexels è facoltativo: le nuove chiavi potrebbero non essere disponibili.'),btn('Salva configurazione',async()=>{try{await api(path+'/services',{method:'POST',body:JSON.stringify({pexels:pex.value,geoapify:geo.value,remove:[...(removeP.checked?['pexels']:[]),...(removeG.checked?['geoapify']:[])]})});back.remove();msg('Servizi Viaggi aggiornati')}catch(e){report(e)}},'primary'))
  }catch(e){report(e)}})();
 }
 function coverEditor(photoTarget='cover',initialQuery=''){
  // Buttons call handlers with an event; treat that as the default cover.
  if(typeof photoTarget!=='string')photoTarget='cover';
  const {box,back}=modal(photoTarget==='cover'?'Copertina del viaggio':'Foto della tappa');back.setAttribute('data-personal-modal','');
  const file=el('input',{type:'file',accept:'image/jpeg,image/png,image/webp',class:'field'});
  const query=input('query','Es. città, paesaggio o monumento',initialQuery||trip.manifest.trip.subtitle?.split('·')[0]?.trim()||'');
  const results=el('div',{class:'travel-photo-results'}),target=tripURL(),token=generation;
  const provider=select('provider',[['commons','Wikimedia Commons · gratuito, senza chiave'],['pexels','Pexels · facoltativo (chiave API)']],'commons');
  const upload=btn('Carica foto',async()=>{if(!file.files[0])return;const data=new FormData();data.append('file',file.files[0]);try{await api(target+'/photo/upload?target='+encodeURIComponent(photoTarget),{method:'POST',body:data});back.remove();if(token===generation)await reloadView()}catch(e){report(e)}},'primary');
  box.append(paragraph('Cerca una foto della destinazione oppure carica una foto personale. Ai servizi esterni viene inviato solo il termine di ricerca.'),toolbar(file,upload),field('Servizio fotografico',provider),toolbar(safeLink('https://commons.wikimedia.org/','Wikimedia Commons'),btn('Servizi Viaggi',()=>{back.remove();servicesEditor()},'small')),field('Cerca una foto',query));
  const search=btn('Cerca fotografie',async()=>{if(search.disabled)return;search.disabled=true;results.replaceChildren(paragraph('Ricerca…'));const chosen=provider.value;try{const list=await api(path+'/photos/search',{method:'POST',body:JSON.stringify({query:query.value,provider:chosen})});if(token!==generation||!back.isConnected)return;results.replaceChildren(...list.map(r=>el('div',{class:'travel-photo-option'},[el('img',{src:r.preview,alt:r.title,loading:'lazy',referrerpolicy:'no-referrer'}),paragraph(r.credit+' · '+r.license),safeLink(r.source,chosen==='pexels'?'Foto su Pexels':'Fonte Wikimedia'),btn('Usa questa foto',async()=>{try{await api(target+'/photo',{method:'POST',body:JSON.stringify({pageid:r.pageid,provider:chosen,target:photoTarget})});back.remove();if(token===generation)await reloadView()}catch(e){report(e)}},'primary')])));if(!list.length)results.append(paragraph('Nessun risultato. Prova una città o un luogo preciso, oppure cambia servizio.'))}catch(e){results.replaceChildren(paragraph(e.message))}finally{search.disabled=false}},'primary');
  box.append(search,results);
 }
 function spotPhoto(img){
  return img?el('div',{class:'travel-spot-photo'},[el('img',{src:'data:image/jpeg;base64,'+img.jpeg,alt:'Foto della tappa',loading:'lazy'}),el('div',{class:'travel-spot-credit'},[img.credit||'',img.license?' · '+img.license:'',safeLink(img.source,img.license==='Pexels'?'Foto su Pexels':'Fonte')])]):null;
 }
 let geoKey='';
 function geoEditor(b,index){
  const {box,back}=modal('Trova indirizzo e coordinate');back.setAttribute('data-personal-modal','');
  const query=input('query','Nome e città',b.place||b.title||'');const key=input('key','API key Geoapify',geoKey,'password');const results=el('div');
  box.append(paragraph('Ricerca Geoapify: viene inviato solo il luogo che confermi. Usa la chiave salvata in Servizi Viaggi oppure inseriscine una temporanea.'),field('Luogo da cercare',query),field('Chiave temporanea (facoltativa)',key),btn('Cerca luogo',async()=>{results.replaceChildren(paragraph('Ricerca…'));try{const list=await api(path+'/geocode',{method:'POST',body:JSON.stringify({query:query.value,key:key.value})});geoKey=key.value;results.replaceChildren();for(const r of list)results.append(card(r.address,paragraph(r.lat+', '+r.lon+' · '+r.source),safeLink(r.map,'Verifica sulla mappa'),btn('Conferma questo luogo',async()=>{try{await save(t=>Object.assign(t.manifest.bookings[index],{place:r.address,map:r.map,latitude:r.lat,longitude:r.lon,geo_source:r.source}));back.remove()}catch(e){report(e)}},'primary')));if(!list.length)results.append(paragraph('Nessun risultato. Specifica città e paese.'))}catch(e){results.replaceChildren(paragraph(e.message))}},'primary'),results);
 }
 function aiEditor(){
  const {box,back}=modal('Acquisisci prenotazione con AI');back.setAttribute('data-personal-modal','');
  const docs=allDocs(trip.manifest),pick=select('doc',[['','Nessun PDF / testo incollato'],...[...docs].map(([name,title])=>[name,title])]);const text=el('textarea',{class:'field',rows:'9',placeholder:'Incolla il testo della conferma o ricevuta…'});const target=tripURL(),token=generation;
  box.append(paragraph('Carica prima un PDF in Documenti oppure incolla una conferma. L’estrazione PDF è locale. Prima dell’invio a GroqCloud elimina dati non necessari, numeri di carte, passaporti e credenziali.'),field('Documento',pick),btn('Estrai testo dal PDF',async()=>{if(!pick.value)return;try{const r=await api(target+'/documents/'+encodeURIComponent(pick.value)+'/text');text.value=r.text}catch(e){report(e)}},'small'),field('Testo da inviare all’AI (modificabile)',text),btn('Analizza con GroqCloud',async()=>{if(!text.value.trim()||!confirm('Inviare a GroqCloud il testo visibile? Nessun dato sarà salvato automaticamente.'))return;try{const source=pick.value;const b=await api(path+'/analyze-booking',{method:'POST',body:JSON.stringify({text:text.value})});if(token!==generation)return;back.remove();bookingEdit({...b,doc:source,status:b.status||'Da verificare'},-1);msg('Controlla e conferma tutti i campi proposti')}catch(e){report(e)}},'primary'));
 }
 function expenseEditor(e={},index=-1){
  editor('Ricevuta / spesa',[...fieldlist(e,[['title','Descrizione'],['date','Data','date'],['amount','Importo (es. 12.50)'],['currency','Valuta ISO (EUR, USD…)'],['category','Categoria'],['doc','Nome PDF già caricato'],['notes','Note','textarea']])],v=>save(t=>{v.currency=v.currency.toUpperCase();const arr=t.manifest.expenses||(t.manifest.expenses=[]);if(index<0)arr.push(v);else arr[index]=v}))
 }
 function show(root){
  const m=trip.manifest,tr=m.trip,st=trip.state;
  const now=new Date(),today=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0'),delta=Math.round((new Date(tr.start+'T12:00:00')-new Date(today+'T12:00:00'))/86400000);
  const status=delta>0?delta+' giorni alla partenza':today<=tr.end?'In viaggio':'Viaggio concluso';
  const hero=el('section',{class:'travel-hero'+(m.cover?' has-photo':'')},[...(m.cover?[el('img',{class:'travel-cover',src:'data:image/jpeg;base64,'+m.cover.jpeg,alt:'Copertina del viaggio'})]:[]),el('div',{class:'travel-hero-inner'},[node('div','travel-kicker','IL TUO VIAGGIO'),node('h2','',tr.title),node('p','',tr.subtitle||''),el('div',{class:'travel-hero-meta'},[node('span','travel-status',status),node('span','',dayFmt(tr.start)+' — '+dayFmt(tr.end))]),toolbar(btn('Oggi / prossima giornata',()=>{selected=m.days.find(d=>d.date>=today)?.date||m.days[0]?.date;switchTab('giornata')},'primary'),btn('Cambia copertina',coverEditor,'small'))]),...(m.cover?[el('div',{class:'travel-credit'},[m.cover.credit||'',m.cover.license?' · '+m.cover.license:'',safeLink(m.cover.source,m.cover.license==='Pexels'?'Foto su Pexels':'Fonte')])]:[])]);
  root.append(hero);
  const header=el('nav',{class:'travel-tabs'},[...[['panoramica','Panoramica'],['giornata','Itinerario'],['prenotazioni','Prenotazioni'],['guide','Guide e GPS'],['mappa','Mappa'],['spese','Spese'],['documenti','Documenti']].map(([k,l])=>btn(l,()=>switchTab(k),tab===k?'primary':'small')),el('a',{class:'btn small',href:'api/personal/trips/'+encodeURIComponent(tr.id)+'/export',download:'',text:'Esporta ZIP'})]);
  root.append(header);
  if(tab==='panoramica'){
   const all=m.days.flatMap(d=>d.checks),checked=Object.values(st.checks).reduce((a,x)=>a+x.length,0),next=m.days.find(d=>d.date>=today)||m.days[0];
   root.append(el('div',{class:'travel-metrics'},[[m.days.length,'Giornate','giornata'],[m.bookings.length,'Prenotazioni','prenotazioni'],[allDocs(m).size,'Documenti','documenti'],[checked+'/'+all.length,'Checklist','giornata']].map(([n,l,k])=>el('button',{class:'travel-metric',onclick:()=>switchTab(k)},[node('strong','',String(n)),node('span','',l)]))));
   root.append(el('div',{class:'travel-grid'},[card('Prossima tappa',paragraph(next?dayFmt(next.date)+' · '+[next.place,next.headline].filter(Boolean).join(' — '):'Da pianificare'),paragraph(next?.description),btn('Apri programma',()=>{selected=next?.date;switchTab('giornata')},'primary')),card('Organizza in pochi passaggi',paragraph('Parti da una conferma di prenotazione, da un PDF o da un testo.'),toolbar(btn('Acquisisci con AI',aiEditor,'primary'),btn('+ Prenotazione',()=>bookingEdit({},-1),'small')),btn('Aggiungi spesa',()=>expenseEditor(),'small')),card('Guide per il viaggio',...m.guides.slice(0,4).map(g=>el('div',{class:'travel-mini'},[node('strong','',g.title),doc(g.doc,'PDF')])),btn('Tutte le guide',()=>switchTab('guide'),'small')),card('Prenotazioni',...m.bookings.slice(0,4).map(b=>el('div',{class:'travel-mini'},[node('strong','',b.title),navLink(b)])),btn('Tutte le prenotazioni',()=>switchTab('prenotazioni'),'small'))]));
  }else if(tab==='mappa'){
   root.append(card('Mappa e navigazione',paragraph('Apri le destinazioni sul navigatore. Le coordinate sono disponibili dopo la ricerca e la conferma di un luogo.')));
   for(const [i,b] of m.bookings.entries())root.append(card(b.title,paragraph(b.place||'Luogo non definito'),paragraph(b.latitude!=null&&b.longitude!=null?b.latitude+', '+b.longitude+' · '+b.geo_source:''),toolbar(navLink(b),btn('Trova coordinate',()=>geoEditor(b,i),'small'))));
  }else if(tab==='spese'){
   const expenses=m.expenses||[],totals={};for(const e of expenses){const cents=Math.round(Number(e.amount)*100);totals[e.currency]=(totals[e.currency]||0)+cents}
   root.append(card('Spese registrate',paragraph(Object.entries(totals).map(([k,v])=>k+' '+(v/100).toFixed(2)).join(' · ')||'Nessuna spesa registrata'),btn('+ Ricevuta / spesa',()=>expenseEditor(),'primary')));
   for(const [i,e] of expenses.entries())root.append(card(e.title,paragraph([e.date,e.category,e.currency+' '+e.amount,e.notes].filter(Boolean).join(' · ')),toolbar(doc(e.doc),btn('Modifica',()=>expenseEditor(e,i),'small'))));
  }else if(tab==='prenotazioni'){
   root.append(toolbar(btn('+ Prenotazione',()=>bookingEdit({},-1),'primary'),btn('Acquisisci con AI',aiEditor,'primary')));
   for(const [i,b] of m.bookings.entries())root.append(card(b.title,spotPhoto(m.travel_photos?.['booking:'+b.id]),paragraph([b.type,b.date,b.status,b.ref,b.place,b.price].filter(Boolean).join(' · ')),lines(b.lines),toolbar(doc(b.doc,b.original?'Documento originale':'Apri PDF'),navLink(b),safeLink(b.source,'Fonte'),safeLink(b.extraLink,b.extraLabel||'Link'),btn('Trova coordinate',()=>geoEditor(b,i),'small'),btn('Foto della tappa',()=>coverEditor('booking:'+b.id,b.place||b.title),'small'),btn('Modifica',()=>bookingEdit(b,i),'small'))));
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
   root.append(el('div',{class:'travel-days'},m.days.map(day=>btn(dayFmt(day.date),()=>{selected=day.date;render(main)},day.date===d.date?'primary':'small'))));
   root.append(card([d.date,d.place,d.headline].filter(Boolean).join(' · '),spotPhoto(m.travel_photos?.['day:'+d.date]),paragraph(d.description),toolbar(btn('Foto della giornata',()=>coverEditor('day:'+d.date,d.place||d.headline),'small'),btn('Modifica giornata',()=>dayEdit(d),'small'),btn('+ Evento',()=>eventEdit(d,{},-1),'primary'))));
   const timeline=el('div',{class:'travel-timeline'});root.append(timeline);
   for(const [i,e] of d.events.entries()){
    const b=m.bookings.find(x=>x.id===e.bid),g=m.guides.find(x=>x.id===e.gid);
    timeline.append(card([e.time,e.title].filter(Boolean).join(' · '),paragraph([e.type,e.warning?'ATTENZIONE':'',e.details].filter(Boolean).join(' · ')),toolbar(b&&doc(b.doc),b&&navLink(b),b&&safeLink(b.source,'Fonte'),b&&safeLink(b.extraLink,b.extraLabel||'Link'),g&&doc(g.doc,'PDF guida'),g&&btn('Guide',()=>{tab='guide';render(main)},'small'),btn('Modifica',()=>eventEdit(d,e,i),'small'))))
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
