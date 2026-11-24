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
  root.classList.add('travel-shell');const imports=el('details',{class:'travel-import'},[node('summary','','Importa / trasferisci viaggio'),paragraph('Gli ZIP con diario ripristinano anche la cronologia privata inclusa.'),toolbar(file,importBtn)]);root.replaceChildren(el('div',{class:'travel-picker'},[el('div',{},[node('div','travel-kicker','AREA PERSONALE · VIAGGI'),pick]),toolbar(btn('+ Nuovo viaggio',newTrip,'primary'),btn('Servizi Viaggi',servicesEditor,'small'),btn('App Android',mobileEditor,'small'),btn('Blocca',async()=>{await lock();render(main)})),imports]));
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
 const bookingTypes=[['flight','Volo'],['hotel','Hotel'],['car','Auto a noleggio'],['train','Treno'],['attraction','Attrazione'],['restaurant','Ristorante'],['other','Altro']];
 const fieldTemplates={flight:['Compagnia','Numero volo','Terminal','Check-in'],hotel:['Check-in','Check-out','Camera'],car:['Società','Ritiro','Riconsegna','Categoria'],train:['Numero treno','Carrozza','Posto'],attraction:['Orario','Biglietto'],restaurant:['Orario','Persone'],other:[]};
 const roleTemplates={flight:['Partenza','Scalo','Arrivo'],hotel:['Alloggio'],car:['Ritiro','Riconsegna'],train:['Partenza','Fermata','Arrivo'],attraction:['Attrazione'],restaurant:['Ristorante'],other:['Tappa']};
 function bookingKind(b){
  if(bookingTypes.some(([k])=>k===b.kind))return b.kind;
  const v=String(b.type||'').toLowerCase();
  if(/vol[io]|flight|aere/.test(v))return 'flight';
  if(/hotel|alloggio|accommodation|albergo/.test(v))return 'hotel';
  if(/auto|car rental|noleggio/.test(v))return 'car';
  if(/tren[oi]|train/.test(v))return 'train';
  if(/attrazion|bigliett|attraction/.test(v))return 'attraction';
  if(/ristorant|restaurant/.test(v))return 'restaurant';
  return 'other';
 }
 function bookingEdit(b,index){
  const {box,back}=modal('Prenotazione');back.setAttribute('data-personal-modal','');
  const kind=select('kind',bookingTypes,bookingKind(b));
  const spec=[['type','Categoria originale / personalizzata'],['title','Titolo'],['ref','Riferimento'],['date','Data / periodo'],['status','Stato'],['place','Luogo originale (testo)'],['price','Prezzo'],['map','Link mappa originale HTTPS'],['source','Link fonte HTTPS'],['extraLink','Link aggiuntivo HTTPS'],['extraLabel','Etichetta link'],['doc','Nome PDF già caricato']];
  const form=el('form',{class:'formgrid'},[field('Tipologia',kind)]),controls={};
  for(const [k,label] of spec){const c=input(k,'',b[k]||'');controls[k]=c;form.append(field(label,c))}
  const details=el('textarea',{class:'field',rows:'4',value:pairsText(b.lines)});
  const extra=el('textarea',{class:'field',rows:'5',value:pairsText(b.fields)});
  const insert=btn('Inserisci campi del modello',()=>{const pairs=readPairs(extra.value),known=new Set(pairs.map(x=>x[0]));for(const k of fieldTemplates[kind.value])if(!known.has(k))pairs.push([k,'']);extra.value=pairsText(pairs)},'small');
  form.append(field('Dettagli originali (etichetta | valore)',details),field('Campi specifici e personalizzati',extra),insert,el('div',{class:'actions full'},[btn('Annulla',()=>back.remove()),el('button',{type:'submit',class:'btn primary',text:'Salva'})]));
  form.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;try{const v=Object.fromEntries(Object.entries(controls).map(([k,c])=>[k,c.value]));if(!v.title.trim())throw Error('Inserire un titolo');const n={...b,...v,kind:kind.value,type:v.type||bookingTypes.find(x=>x[0]===kind.value)[1],id:b.id||'booking-'+uid(),lines:readPairs(details.value),fields:readPairs(extra.value)};await save(t=>{if(index<0)t.manifest.bookings.push(n);else t.manifest.bookings[index]=n});back.remove()}catch(e){report(e)}finally{busy=false}});
  box.append(form);
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
 function mobileEditor(){
  const {box,back}=modal('NextDo Viaggi · Android');back.setAttribute('data-personal-modal','');
  const token=generation,list=el('div'),code=el('div');
  const reload=async()=>{try{const ds=await api(path+'/mobile/devices');if(token!==generation||!back.isConnected)return;list.replaceChildren(...ds.map(d=>card(d.label,paragraph(d.revoked?'Revocato':new Date(d.expires*1000)<new Date()?'Scaduto':'Associato fino al '+new Date(d.expires*1000).toLocaleDateString('it-IT')),d.revoked?null:btn('Revoca',async()=>{if(!confirm('Revocare questo dispositivo? I dati offline già scaricati restano sul telefono fino alla cancellazione locale.'))return;try{await api(path+'/mobile/devices/'+encodeURIComponent(d.id)+'/revoke',{method:'POST'});reload()}catch(e){report(e)}},'small'))));if(!ds.length)list.append(paragraph('Nessun dispositivo associato'))}catch(e){report(e)}};
  box.append(paragraph('Usa l’app Android solo con un URL HTTPS diretto e sicuro di NextDo, raggiungibile dal telefono. L’ingress di Home Assistant non è un URL API autonomo. L’app accede soltanto ai tuoi viaggi e può salvare la cronologia importata dopo conferma.'),btn('Genera codice di associazione',async()=>{try{const r=await api(path+'/mobile/pair',{method:'POST'});if(token!==generation||!back.isConnected)return;const value=input('pair','',r.code);value.readOnly=true;code.replaceChildren(paragraph('Codice monouso valido 5 minuti. Non condividerlo.'),value,btn('Copia codice',async()=>{try{await navigator.clipboard.writeText(value.value);msg('Codice copiato')}catch{value.select();msg('Copia manualmente il codice selezionato')}},'small'))}catch(e){report(e)}},'primary'),code,list);reload();
 }
 function servicesEditor(){
  const {box,back}=modal('Servizi Viaggi');back.setAttribute('data-personal-modal','');
  const token=generation;
  box.append(paragraph('GroqCloud rimane dedicato all’analisi delle prenotazioni. Geoapify serve per indirizzi e coordinate. Le immagini si caricano dal dispositivo, senza chiavi API fotografiche.'));
  (async()=>{try{
   const cfg=await api(path+'/services');if(token!==generation||!back.isConnected)return;
   const geo=input('geoapify','Incolla API key Geoapify','','password'),removeG=el('input',{type:'checkbox'});
   box.append(field('Geoapify — '+(cfg.geoapify_configured?'Configurata':'Da configurare'),geo),safeLink('https://myprojects.geoapify.com/','Richiedi chiave Geoapify'),el('label',{},[removeG,' Rimuovi chiave Geoapify']),paragraph('Chiave cifrata sul Raspberry, esclusa dagli ZIP. Lascia vuoto per mantenere la chiave esistente.'),btn('Salva configurazione',async()=>{try{await api(path+'/services',{method:'POST',body:JSON.stringify({geoapify:geo.value,remove:removeG.checked?['geoapify']:[]})});back.remove();msg('Servizi Viaggi aggiornati')}catch(e){report(e)}},'primary'))
  }catch(e){report(e)}})();
 }
 function coverEditor(photoTarget='cover',initialQuery=''){
  if(typeof photoTarget!=='string')photoTarget='cover';
  const {box,back}=modal(photoTarget==='cover'?'Copertina del viaggio':'Immagine della tappa');back.setAttribute('data-personal-modal','');
  const file=el('input',{type:'file',accept:'image/jpeg,image/png,image/webp',class:'field'});
  const preview=el('div',{class:'travel-spot-photo'}),target=tripURL(),token=generation;
  const upload=btn('Salva immagine',async()=>{
   if(!file.files[0]||upload.disabled)return;
   upload.disabled=true;const data=new FormData();data.append('file',file.files[0]);
   try{await api(target+'/photo/upload?target='+encodeURIComponent(photoTarget),{method:'POST',body:data});back.remove();if(token===generation)await reloadView()}catch(e){report(e);upload.disabled=false}
  },'primary');upload.disabled=true;
  file.addEventListener('change',()=>{
   preview.replaceChildren();upload.disabled=true;const selected=file.files[0];
   if(!selected)return;
   if(!['image/jpeg','image/png','image/webp'].includes(selected.type)||selected.size>5*1024*1024){preview.append(paragraph('Seleziona una foto JPEG, PNG o WebP fino a 5 MB.'));return}
   const reader=new FileReader();
   reader.onload=()=>{if(token!==generation||!back.isConnected||file.files[0]!==selected)return;preview.replaceChildren(el('img',{src:reader.result,alt:'Anteprima immagine'}));upload.disabled=false};
   reader.onerror=()=>preview.replaceChildren(paragraph('Impossibile leggere il file.'));
   reader.readAsDataURL(selected);
  });
  box.append(card('Carica dal dispositivo',paragraph('Fotografie personali o immagini create in ChatGPT. Formati JPEG, PNG e WebP, fino a 5 MB. Le immagini sono salvate localmente nel viaggio.'),file,preview,upload));
 }
 function spotPhoto(img){
  return img?el('div',{class:'travel-spot-photo'},[el('img',{src:'data:image/jpeg;base64,'+img.jpeg,alt:'Foto della tappa',loading:'lazy'}),el('div',{class:'travel-spot-credit'},[img.credit||'',img.license?' · '+img.license:'',safeLink(img.source,'Fonte')])]):null;
 }
 let geoKey='';
 const located=p=>typeof p?.lat==='number'&&typeof p?.lon==='number';
 const locationNav=p=>located(p)?safeLink('https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(p.lat+','+p.lon),'Naviga'):p?.address?safeLink('https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(p.address),'Cerca su Maps'):null;
 const locationLine=p=>el('div',{class:'travel-mini'},[el('div',{},[node('strong','',p.role?p.role+' · '+p.label:p.label),paragraph([p.code,p.address,p.time,located(p)?p.lat+', '+p.lon:'Coordinate da verificare'].filter(Boolean).join(' · '))]),locationNav(p)]);
 function placeEditor(initial,roles,onSave){
  const {box,back}=modal('Luogo e coordinate');back.setAttribute('data-personal-modal','');
  const loc={...initial,id:initial.id||'loc-'+uid()};
  const role=input('role','Es. Partenza, Scalo, Arrivo',loc.role||''),label=input('label','Nome della tappa',loc.label||''),code=input('code','Codice aeroporto/stazione (facoltativo)',loc.code||''),when=input('time','Data / ora (facoltativa)',loc.time||''),query=input('query','Nome, indirizzo, città e paese',loc.address||loc.label||''),notes=el('textarea',{class:'field',rows:'3',value:loc.notes||''});
  const results=el('div'),chosen=el('div');let candidate=located(loc)?{address:loc.address,lat:loc.lat,lon:loc.lon,map:loc.map,source:loc.source}:null;
  const draw=()=>chosen.replaceChildren(paragraph(candidate?'Coordinate selezionate: '+candidate.lat+', '+candidate.lon:'Coordinate non ancora confermate'));
  draw();
  query.addEventListener('input',()=>{candidate=null;draw()});
  const find=btn('Cerca con Geoapify',async()=>{if(find.disabled)return;find.disabled=true;results.replaceChildren(paragraph('Ricerca…'));try{const list=await api(path+'/geocode',{method:'POST',body:JSON.stringify({query:query.value,key:geoKey})});if(!back.isConnected)return;results.replaceChildren();for(const r of list)results.append(card(r.address,paragraph(r.lat+', '+r.lon+' · '+r.source),safeLink(r.map,'Verifica'),btn('Seleziona',()=>{candidate=r;query.value=r.address;if(!label.value.trim())label.value=r.address;draw();results.replaceChildren()},'primary')));if(!list.length)results.append(paragraph('Nessun risultato. Specifica il nome completo, città e paese.'))}catch(e){results.replaceChildren(paragraph(e.message))}finally{find.disabled=false}},'primary');
  const commit=btn('Salva luogo',async()=>{if(commit.disabled)return;if(!label.value.trim())return msg('Inserire il nome del luogo',true);commit.disabled=true;try{const next={id:loc.id,role:role.value,label:label.value.trim(),code:code.value,time:when.value,address:query.value.trim(),notes:notes.value};if(candidate)Object.assign(next,{lat:candidate.lat,lon:candidate.lon,map:candidate.map,source:candidate.source});await onSave(next);back.remove()}catch(e){report(e);commit.disabled=false}},'primary');
  box.append(paragraph('Ruoli suggeriti: '+roles.join(' · ')+'. Ogni luogo ha coordinate indipendenti. Il testo originale della prenotazione non viene modificato.'),field('Ruolo',role),field('Nome',label),field('Codice',code),field('Data / ora',when),field('Indirizzo da cercare',query),toolbar(find,btn('Servizi Viaggi',servicesEditor,'small')),results,chosen,field('Note',notes),toolbar(commit,btn('Annulla',()=>back.remove(),'small')));
 }
 function geoEditor(b,index){
  const {box,back}=modal('Luoghi della prenotazione');back.setAttribute('data-personal-modal','');
  const roles=roleTemplates[bookingKind(b)],draft=clone(b.locations||[]);
  const list=el('div');const repaint=()=>{list.replaceChildren();for(const [i,p] of draft.entries())list.append(card(p.role+' · '+p.label,locationLine(p),toolbar(btn('Modifica',()=>placeEditor(p,roles,async v=>{draft[i]=v;repaint()}),'small'),btn('↑',()=>{if(i>0){[draft[i-1],draft[i]]=[draft[i],draft[i-1]];repaint()}},'small'),btn('↓',()=>{if(i<draft.length-1){[draft[i+1],draft[i]]=[draft[i],draft[i+1]];repaint()}},'small'),btn('Rimuovi',()=>{draft.splice(i,1);repaint()},'small'))));};
  box.append(paragraph('Dati precedenti conservati: '+(b.place||'nessun luogo originale')),paragraph('Aggiungi partenza, scali, arrivo, ritiro e riconsegna o qualsiasi altro luogo. Salva l’elenco solo dopo averlo controllato.'),list,toolbar(...roles.map(r=>btn('+ '+r,()=>placeEditor({role:r},roles,async v=>{draft.push(v);repaint()}),'small')),btn('+ Luogo libero',()=>placeEditor({},roles,async v=>{draft.push(v);repaint()}),'small')));
  if(b.place&&(!draft.length))box.append(btn('Riprendi luogo originale',()=>placeEditor({role:roles[0],label:b.place,address:b.place,...(typeof b.latitude==='number'&&typeof b.longitude==='number'?{lat:b.latitude,lon:b.longitude,map:b.map,source:b.geo_source}:{})},roles,async v=>{draft.push(v);repaint()}),'small'));
  const commit=btn('Salva tutti i luoghi',async()=>{if(commit.disabled)return;commit.disabled=true;try{await save(t=>{t.manifest.bookings[index].locations=draft});back.remove()}catch(e){report(e);commit.disabled=false}},'primary');box.append(commit);repaint();
 }
 function routeEditor(d){
  const {box,back}=modal('Percorso · '+dayFmt(d.date));back.setAttribute('data-personal-modal','');
  const points=clone(d.route_points||[]),mode=select('mode',[['drive','Auto'],['walk','A piedi'],['bicycle','Bicicletta']],d.route_mode||'drive');
  const results=el('div'),list=el('div');
  const candidates=trip.manifest.bookings.flatMap(b=>(b.locations||[]).map(l=>({b,l})));
  const pick=select('location',[['','Seleziona un luogo già salvato'],...candidates.map(({b,l},i)=>[String(i),b.title+' · '+l.label])],'');
  const refresh=()=>{list.replaceChildren();for(const [i,p] of points.entries())list.append(card((i+1)+'. '+p.label,locationLine(p),toolbar(btn('Modifica',()=>placeEditor(p,['Tappa'],async v=>{points[i]=v;refresh()}),'small'),btn('↑',()=>{if(i>0){[points[i-1],points[i]]=[points[i],points[i-1]];refresh()}},'small'),btn('↓',()=>{if(i<points.length-1){[points[i+1],points[i]]=[points[i],points[i+1]];refresh()}},'small'),btn('Rimuovi',()=>{points.splice(i,1);refresh()},'small'))));};
  box.append(paragraph('Costruisci un percorso terrestre nell’ordine che preferisci. Le tappe sono copie indipendenti: nessuna modifica alle prenotazioni.'),field('Modalità',mode),list,toolbar(pick,btn('Aggiungi luogo',()=>{if(pick.value==='')return;points.push({...clone(candidates[Number(pick.value)].l),id:'loc-'+uid()});refresh()},'small')),btn('+ Nuova tappa',()=>placeEditor({role:'Tappa'},['Tappa'],async v=>{points.push(v);refresh()}),'small'),btn('Salva percorso',async()=>{try{await save(t=>{const day=t.manifest.days.find(x=>x.date===d.date);day.route_points=points;day.route_mode=mode.value});back.remove()}catch(e){report(e)}},'primary'));refresh();
 }
 function routeCard(d){
  const points=d.route_points||[],out=el('div'),mode=d.route_mode||'drive',names={drive:'Auto',walk:'A piedi',bicycle:'Bicicletta'};
  const labelTime=s=>Math.round(s/60)+' min',labelDist=m=>(m/1000).toLocaleString('it-IT',{maximumFractionDigits:1})+' km';
  const calculate=btn('Calcola distanza e tempi',async()=>{if(calculate.disabled)return;calculate.disabled=true;out.replaceChildren(paragraph('Calcolo percorso…'));try{const r=await api(tripURL()+'/route',{method:'POST',body:JSON.stringify({date:d.date})});if(!out.isConnected)return;out.replaceChildren(node('h2','',labelDist(r.distance_m)+' · '+labelTime(r.duration_s)),paragraph('Stima '+names[mode]+' · '+r.source+' · non comprende soste o traffico in tempo reale.'),...r.legs.map((l,i)=>paragraph(points[i].label+' → '+points[i+1].label+': '+labelDist(l.distance_m)+' · '+labelTime(l.duration_s))))}catch(e){out.replaceChildren(paragraph(e.message))}finally{calculate.disabled=false}},'primary');
  calculate.disabled=points.length<2||points.length>15||points.some(p=>!located(p));
  return card('Percorso della giornata',paragraph(names[mode]+' · '+points.length+' tappe'),...points.map(locationLine),toolbar(btn('Organizza percorso',()=>routeEditor(d),'small'),calculate),paragraph(calculate.disabled?'Per il calcolo occorrono da 2 a 15 tappe con coordinate confermate.':''),out);
 }
 function aiEditor(){
  const {box,back}=modal('Acquisisci prenotazione con AI');back.setAttribute('data-personal-modal','');
  const docs=allDocs(trip.manifest),pick=select('doc',[['','Nessun PDF / testo incollato'],...[...docs].map(([name,title])=>[name,title])]);const text=el('textarea',{class:'field',rows:'9',placeholder:'Incolla il testo della conferma o ricevuta…'});const target=tripURL(),token=generation;
  box.append(paragraph('Carica prima un PDF in Documenti oppure incolla una conferma. L’estrazione PDF è locale. Prima dell’invio a GroqCloud elimina dati non necessari, numeri di carte, passaporti e credenziali.'),field('Documento',pick),btn('Estrai testo dal PDF',async()=>{if(!pick.value)return;try{const r=await api(target+'/documents/'+encodeURIComponent(pick.value)+'/text');text.value=r.text}catch(e){report(e)}},'small'),field('Testo da inviare all’AI (modificabile)',text),btn('Analizza con GroqCloud',async()=>{if(!text.value.trim()||!confirm('Inviare a GroqCloud il testo visibile? Nessun dato sarà salvato automaticamente.'))return;try{const source=pick.value;const b=await api(path+'/analyze-booking',{method:'POST',body:JSON.stringify({text:text.value})});if(token!==generation)return;back.remove();bookingEdit({...b,doc:source,status:b.status||'Da verificare'},-1);msg('Controlla e conferma tutti i campi proposti')}catch(e){report(e)}},'primary'));
 }
 function expenseEditor(e={},index=-1){
  editor('Ricevuta / spesa',[...fieldlist(e,[['title','Descrizione'],['date','Data','date'],['amount','Importo (es. 12.50)'],['currency','Valuta ISO (EUR, USD…)'],['category','Categoria'],['doc','Nome PDF già caricato'],['notes','Note','textarea']])],v=>save(t=>{v.currency=v.currency.toUpperCase();const arr=t.manifest.expenses||(t.manifest.expenses=[]);if(index<0)arr.push(v);else arr[index]=v}))
 }
 function timelineView(root,tr){
  const token=generation,url=path+'/trips/'+encodeURIComponent(tr.id)+'/timeline';
  const host=el('div'),out=el('div'),day=input('timeline-day','','','date');
  let data=null;
  const active=()=>token===generation&&host.isConnected;
  const format=t=>t.slice(0,16).replace('T',' ');
  function draw(){
   out.replaceChildren();if(!data)out.append(paragraph('Nessuna cronologia importata. Sono visibili le tappe previste.'));
   const d=day.value,match=t=>!d||t.slice(0,10)===d;
   const visits=(data?.visits||[]).filter(v=>match(v.startTime)),acts=(data?.activities||[]).filter(a=>match(a.startTime));
   const paths=(data?.paths||[]).flatMap(p=>{const groups=[];let g=[];for(const x of p){if(match(x.time))g.push(x);else if(g.length){groups.push(g);g=[]}}if(g.length)groups.push(g);return groups});
   const plans=trip.manifest.days.filter(v=>!d||v.date===d).map(v=>(v.route_points||[]).filter(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon))).filter(p=>p.length);
   const pts=paths.flat().concat(visits.map(v=>v.location),acts.flatMap(a=>[a.first,a.last]),plans.flat());
   const known=acts.filter(a=>a.distanceMeters!=null),minutes=Math.round(acts.reduce((s,a)=>s+Math.max(0,Date.parse(a.endTime)-Date.parse(a.startTime)),0)/60000);
   out.append(card('Riepilogo',paragraph((data?data.from+' — '+data.to+' · ':'')+visits.length+' visite · '+acts.length+' spostamenti · '+plans.flat().length+' tappe geolocalizzate previste'),paragraph((known.length?(known.reduce((s,a)=>s+a.distanceMeters,0)/1000).toLocaleString('it-IT',{maximumFractionDigits:1})+' km registrati':'Distanza non disponibile')+' · '+minutes+' min negli spostamenti registrati. Orari originali locali; gli eventi sono attribuiti alla data di inizio.')));
   if(pts.length){
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 768 768');svg.setAttribute('width','100%');svg.style.background='#162c3f';svg.style.touchAction='none';
    const merc=p=>{const lat=Math.max(-85.05112878,Math.min(85.05112878,p.lat))*Math.PI/180;return [(p.lon+180)/360,(1-Math.asinh(Math.tan(lat))/Math.PI)/2]};
    const anchor=merc(pts[0])[0],xy=p=>{const [x,y]=merc(p);return [anchor+((x-anchor+1.5)%1)-.5,y]};
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(const p of pts){const [x,y]=xy(p);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y)}
    const z=Math.max(0,Math.min(18,Math.floor(Math.log2(1/Math.max(1e-9,maxX-minX,maxY-minY))))),n=2**z,cx=Math.floor((minX+maxX)/2*n),cy=Math.max(0,Math.min(n-1,Math.floor((minY+maxY)/2*n)));
    const project=p=>{const [x,y]=xy(p);return [(x*n-cx+1)*256,(y*n-cy+1)*256]};
    const make=(tag,attrs)=>{const n=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));svg.append(n);return n};
    const bg=make('image',{x:0,y:0,width:768,height:768});
    for(const p of plans){const coords=p.map(project);if(coords.length>1)make('polyline',{points:coords.map(a=>a.join(',')).join(' '),fill:'none',stroke:'#008b88','stroke-width':3,'stroke-dasharray':'7 5','vector-effect':'non-scaling-stroke'});for(const [x,y] of coords)make('circle',{cx:x,cy:y,r:5,fill:'#008b88',stroke:'white'})}
    for(const p of paths){const coords=p.map(project);if(coords.length>1)make('polyline',{points:coords.map(a=>a.join(',')).join(' '),fill:'none',stroke:'#e58617','stroke-width':2,'vector-effect':'non-scaling-stroke'});else make('circle',{cx:coords[0][0],cy:coords[0][1],r:3,fill:'#e58617'})}
    for(const v of visits){const [x,y]=project(v.location);make('circle',{cx:x,cy:y,r:5,fill:'#ffd49a'})}
    for(const a of acts){for(const p of [a.first,a.last]){const [x,y]=project(p);make('circle',{cx:x,cy:y,r:3,fill:'#a5b4fc'})}}
    let x=0,y=0,w=768,h=768,drag=null;const refresh=()=>svg.setAttribute('viewBox',[x,y,w,h].join(' '));
    const zoom=f=>{if(w*f<30||w*f>3200)return;x+=w*(1-f)/2;y+=h*(1-f)/2;w*=f;h*=f;refresh()};
    svg.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY,x,y];svg.setPointerCapture(e.pointerId)});
    svg.addEventListener('pointermove',e=>{if(!drag)return;const r=svg.getBoundingClientRect();x=drag[2]-(e.clientX-drag[0])*w/r.width;y=drag[3]-(e.clientY-drag[1])*h/r.height;refresh()});
    for(const e of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(e,()=>drag=null);
    const status=paragraph('Sfondo non caricato. Nessuna richiesta esterna.');
    const mapBtn=btn('Carica cartografia Geoapify',()=>{
     if(!confirm('Caricare la mappa dell’area? Geoapify riceverà gli indici delle tessere, non le visite o il tracciato.'))return;
     mapBtn.disabled=true;status.textContent='Caricamento cartografia…';
     bg.addEventListener('load',()=>{status.textContent='Geoapify · © OpenMapTiles · © OpenStreetMap contributors';mapBtn.disabled=false},{once:true});
     bg.addEventListener('error',()=>{status.textContent='Cartografia non disponibile. Verifica la chiave Geoapify.';mapBtn.disabled=false},{once:true});
     bg.setAttribute('href','api/personal/trips/'+encodeURIComponent(tr.id)+'/timeline/map/'+z+'/'+((cx%n+n)%n)+'/'+cy);
    },'small');
    out.append(card('Previsto / effettivo',toolbar(btn('+ Zoom',()=>zoom(.7),'small'),btn('− Zoom',()=>zoom(1/.7),'small'),btn('Centra',()=>{x=0;y=0;w=768;h=768;refresh()},'small'),mapBtn),svg,status,paragraph('Verde tratteggiato: collegamento schematico delle tappe previste, non percorso stradale. Arancione: percorso registrato; giallo: visite; lilla: estremi. Nessuna ricostruzione dei tratti mancanti.')));
   }
   const events=[...visits.map(v=>({v,kind:'Visita'})),...acts.map(v=>({v,kind:'Spostamento'}))].sort((a,b)=>Date.parse(a.v.startTime)-Date.parse(b.v.startTime));
   const labels={WALKING:'A piedi',IN_PASSENGER_VEHICLE:'In auto',IN_VEHICLE:'Veicolo',CYCLING:'Bicicletta',FLYING:'Volo',IN_BUS:'Autobus',IN_TRAIN:'Treno'};
   for(const {v,kind} of events.slice(0,500))out.append(card(kind+(v.mode?' · '+(labels[v.mode]||v.mode):''),paragraph(format(v.startTime)+' — '+format(v.endTime)),paragraph(v.location?v.location.lat+', '+v.location.lon:v.distanceMeters!=null?(v.distanceMeters/1000).toFixed(1)+' km':'Distanza non disponibile')));
   if(events.length>500)out.append(paragraph('Mostrati i primi 500 eventi: filtra per giornata.'));
   const planned=trip.manifest.days.find(x=>x.date===d);
   if(planned)out.append(card('Diario della giornata',spotPhoto(trip.manifest.travel_photos?.['day:'+d]),paragraph(trip.state.notes[d]||'Nessuna annotazione'),btn('Apri giornata e modifica note / foto',()=>{selected=d;switchTab('giornata')},'small')));
  }
  const loadDiary=async()=>{try{const r=await api(url);if(active()){data=r.data;draw()}}catch(e){if(active())report(e)}};
  host.append(card('Diario di bordo',paragraph('Solo il periodo confermato. Cartografia esterna facoltativa. Il backup con diario contiene posizioni private.'),field('Giornata (vuoto = tutte)',day),toolbar(btn('Aggiorna',loadDiary,'primary'),btn('Esporta ZIP con diario',()=>{if(confirm('Il file conterrà la cronologia delle posizioni. Conservarlo in modo sicuro. Continuare?')){const a=el('a',{href:'api/personal/trips/'+encodeURIComponent(tr.id)+'/export?include_timeline=true',download:''});host.append(a);a.click();a.remove()}},'small'),btn('Cancella cronologia',async()=>{if(!confirm('Eliminare la cronologia importata di questo viaggio?'))return;try{await api(url+'/clear',{method:'POST'});if(active())loadDiary()}catch(e){report(e)}},'small'))),out);
  day.addEventListener('change',draw);root.append(host);loadDiary();
 }
 function show(root){
  const m=trip.manifest,tr=m.trip,st=trip.state;
  const now=new Date(),today=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0'),delta=Math.round((new Date(tr.start+'T12:00:00')-new Date(today+'T12:00:00'))/86400000);
  const status=delta>0?delta+' giorni alla partenza':today<=tr.end?'In viaggio':'Viaggio concluso';
  const hero=el('section',{class:'travel-hero'+(m.cover?' has-photo':'')},[...(m.cover?[el('img',{class:'travel-cover',src:'data:image/jpeg;base64,'+m.cover.jpeg,alt:'Copertina del viaggio'})]:[]),el('div',{class:'travel-hero-inner'},[node('div','travel-kicker','IL TUO VIAGGIO'),node('h2','',tr.title),node('p','',tr.subtitle||''),el('div',{class:'travel-hero-meta'},[node('span','travel-status',status),node('span','',dayFmt(tr.start)+' — '+dayFmt(tr.end))]),toolbar(btn('Oggi / prossima giornata',()=>{selected=m.days.find(d=>d.date>=today)?.date||m.days[0]?.date;switchTab('giornata')},'primary'),btn('Cambia copertina',coverEditor,'small'))]),...(m.cover?[el('div',{class:'travel-credit'},[m.cover.credit||'',m.cover.license?' · '+m.cover.license:'',safeLink(m.cover.source,'Fonte')])]:[])]);
  root.append(hero);
  const header=el('nav',{class:'travel-tabs'},[...[['panoramica','Panoramica'],['giornata','Itinerario'],['prenotazioni','Prenotazioni'],['guide','Guide e GPS'],['mappa','Mappa'],['timeline','Diario di bordo'],['spese','Spese'],['documenti','Documenti']].map(([k,l])=>btn(l,()=>switchTab(k),tab===k?'primary':'small')),el('a',{class:'btn small',href:'api/personal/trips/'+encodeURIComponent(tr.id)+'/export',download:'',text:'Esporta ZIP'})]);
  root.append(header);
  if(tab==='panoramica'){
   const all=m.days.flatMap(d=>d.checks),checked=Object.values(st.checks).reduce((a,x)=>a+x.length,0),next=m.days.find(d=>d.date>=today)||m.days[0];
   root.append(el('div',{class:'travel-metrics'},[[m.days.length,'Giornate','giornata'],[m.bookings.length,'Prenotazioni','prenotazioni'],[allDocs(m).size,'Documenti','documenti'],[checked+'/'+all.length,'Checklist','giornata']].map(([n,l,k])=>el('button',{class:'travel-metric',onclick:()=>switchTab(k)},[node('strong','',String(n)),node('span','',l)]))));
   root.append(el('div',{class:'travel-grid'},[card('Prossima tappa',paragraph(next?dayFmt(next.date)+' · '+[next.place,next.headline].filter(Boolean).join(' — '):'Da pianificare'),paragraph(next?.description),btn('Apri programma',()=>{selected=next?.date;switchTab('giornata')},'primary')),card('Organizza in pochi passaggi',paragraph('Parti da una conferma di prenotazione, da un PDF o da un testo.'),toolbar(btn('Acquisisci con AI',aiEditor,'primary'),btn('+ Prenotazione',()=>bookingEdit({},-1),'small')),btn('Aggiungi spesa',()=>expenseEditor(),'small')),card('Guide per il viaggio',...m.guides.slice(0,4).map(g=>el('div',{class:'travel-mini'},[node('strong','',g.title),doc(g.doc,'PDF')])),btn('Tutte le guide',()=>switchTab('guide'),'small')),card('Prenotazioni',...m.bookings.slice(0,4).map(b=>el('div',{class:'travel-mini'},[node('strong','',b.title),navLink(b)])),btn('Tutte le prenotazioni',()=>switchTab('prenotazioni'),'small'))]));
  }else if(tab==='timeline'){
   timelineView(root,tr);
  }else if(tab==='mappa'){
   root.append(card('Mappa e navigazione',paragraph('Apri le destinazioni sul navigatore. Le coordinate sono disponibili dopo la ricerca e la conferma di un luogo.')));
   for(const [i,b] of m.bookings.entries())root.append(card(b.title,paragraph(b.place||'Luogo originale non definito'),...(b.locations||[]).map(locationLine),toolbar(navLink(b),btn('Gestisci luoghi',()=>geoEditor(b,i),'small'))));
   for(const d of m.days)if((d.route_points||[]).length)root.append(card(dayFmt(d.date),routeCard(d)));
  }else if(tab==='spese'){
   const expenses=m.expenses||[],totals={};for(const e of expenses){const cents=Math.round(Number(e.amount)*100);totals[e.currency]=(totals[e.currency]||0)+cents}
   root.append(card('Spese registrate',paragraph(Object.entries(totals).map(([k,v])=>k+' '+(v/100).toFixed(2)).join(' · ')||'Nessuna spesa registrata'),btn('+ Ricevuta / spesa',()=>expenseEditor(),'primary')));
   for(const [i,e] of expenses.entries())root.append(card(e.title,paragraph([e.date,e.category,e.currency+' '+e.amount,e.notes].filter(Boolean).join(' · ')),toolbar(doc(e.doc),btn('Modifica',()=>expenseEditor(e,i),'small'))));
  }else if(tab==='prenotazioni'){
   root.append(toolbar(btn('+ Prenotazione',()=>bookingEdit({},-1),'primary'),btn('Acquisisci con AI',aiEditor,'primary')));
   for(const [i,b] of m.bookings.entries())root.append(card(b.title,spotPhoto(m.travel_photos?.['booking:'+b.id]),paragraph([b.type,b.date,b.status,b.ref,b.place,b.price].filter(Boolean).join(' · ')),lines(b.lines),lines(b.fields),...(b.locations||[]).map(locationLine),toolbar(doc(b.doc,b.original?'Documento originale':'Apri PDF'),navLink(b),safeLink(b.source,'Fonte'),safeLink(b.extraLink,b.extraLabel||'Link'),btn('Gestisci luoghi',()=>geoEditor(b,i),'small'),btn('Foto della tappa',()=>coverEditor('booking:'+b.id,b.place||b.title),'small'),btn('Modifica',()=>bookingEdit(b,i),'small'))));
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
   root.append(routeCard(d));
   const timeline=el('div',{class:'travel-timeline'});root.append(timeline);
   for(const [i,e] of d.events.entries()){
    const b=m.bookings.find(x=>x.id===e.bid),g=m.guides.find(x=>x.id===e.gid);
    timeline.append(card([e.time,e.title].filter(Boolean).join(' · '),paragraph([e.type,e.warning?'ATTENZIONE':'',e.details].filter(Boolean).join(' · ')),toolbar(b&&doc(b.doc),b&&navLink(b),...(b?.locations||[]).map(locationNav),b&&safeLink(b.source,'Fonte'),b&&safeLink(b.extraLink,b.extraLabel||'Link'),g&&doc(g.doc,'PDF guida'),g&&btn('Guide',()=>{tab='guide';render(main)},'small'),btn('Modifica',()=>eventEdit(d,e,i),'small'))))
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
