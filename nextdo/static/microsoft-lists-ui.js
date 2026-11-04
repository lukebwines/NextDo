'use strict';
/* Pilot Microsoft Lists integration: delegated Microsoft Graph read-only diagnostics.
   Auth codes are shown to admins only. No token is ever sent to the browser. */
const NextDoMicrosoft=(()=>{
 const apiMethod=(path,method='POST',body)=>api('/microsoft'+path,{method,...(body?{body:JSON.stringify(body)}:{})});
 function settings(main){
  if(S.me?.role!=='admin')return;
  const panel=el('section',{class:'card microsoft-panel'});
  panel.append(node('h2','','Microsoft Lists — collegamento di prova'));
  panel.append(node('p','sub','Fase 1: solo lettura, senza modificare l’elenco SharePoint. Per accedere serve una registrazione applicazione Microsoft Entra autorizzata dall’Ateneo (client pubblico, flusso codice dispositivo e permesso delegato Sites.Read.All). Nessuna password Microsoft viene richiesta da NextDo.'));
  const state=node('p','sub','Caricamento configurazione…');
  const ui=el('div',{class:'microsoft-settings'});
  panel.append(state,ui);main.append(panel);
  api('/microsoft/config').then(config=>{
   state.textContent=config.authenticated?'Microsoft connesso per questa sessione (accesso temporaneo, solo lettura).':'Microsoft non connesso. Nessun dato è stato inviato.';
   ui.replaceChildren();
   const tenant=input('tenant_id','ID tenant Microsoft (GUID)',config.tenant_id||'');
   const client=input('client_id','ID applicazione registrata (GUID)',config.client_id||'');
   const site=input('site_url','Indirizzo sito SharePoint o collegamento alla lista',config.site_url||'');
   ui.append(field('ID tenant',tenant),field('ID applicazione (client)',client),field('Sito SharePoint',site));
   const controls=el('div',{class:'microsoft-actions'});
   controls.append(btn('Salva configurazione',async()=>{
    try{
     const result=await apiMethod('/config','POST',{tenant_id:tenant.value.trim(),client_id:client.value.trim(),site_url:site.value.trim()});
     msg('Sito configurato: '+result.site_url);render();
    }catch(error){msg(error.message,true)}
   },'small'));
   controls.append(btn('Connetti Microsoft 365',async()=>{
    try{
     const code=await apiMethod('/auth/start');
     authInstructions(ui,code);
    }catch(error){msg(error.message,true)}
   },'primary'));
   if(config.authenticated){
    controls.append(btn('Elenca liste',()=>discover(ui,config),'small'));
    controls.append(btn('Disconnetti',async()=>{
     try{await apiMethod('/auth/disconnect');render()}catch(error){msg(error.message,true)}
    },'small'));
   }
   ui.append(controls);
   if(config.list_name)ui.append(node('p','sub','Lista selezionata: '+config.list_name));
   if(config.authenticated&&config.list_id)ui.append(btn('Verifica colonne (solo lettura)',()=>inspect(ui),'small'));
  }).catch(error=>{state.textContent='Configurazione non disponibile: '+error.message});
 }
 function authInstructions(ui,data){
  ui.querySelector('.microsoft-auth')?.remove();
  const section=el('div',{class:'microsoft-auth'});
  section.append(node('h3','','Autorizzazione Microsoft'));
  section.append(node('p','sub','Apri la pagina Microsoft, inserisci il codice riportato qui e completa l’accesso. Non inserire mai la password Microsoft in NextDo.'));
  const code=el('strong',{class:'microsoft-code',text:data.user_code});
  const link=el('a',{href:data.verification_uri,target:'_blank',rel:'noopener noreferrer',text:'Apri pagina di accesso Microsoft'});
  section.append(code,link,btn('Verifica autorizzazione',async()=>{
   try{
    const result=await apiMethod('/auth/check');
    if(result.status==='connected'){msg('Collegamento Microsoft autorizzato (solo lettura)');render()}
    else msg('Autorizzazione non ancora completata. Riprova dopo alcuni secondi.');
   }catch(error){msg(error.message,true)}
  },'primary'));
  ui.append(section);
 }
 async function discover(ui,config){
  try{
   const data=await api('/microsoft/lists');
   ui.querySelector('.microsoft-discovery')?.remove();
   const section=el('div',{class:'microsoft-discovery'});
   section.append(node('h3','','Liste accessibili sul sito'),node('p','sub','Sito: '+(data.site.name||data.site.url||'Selezionato')));
   if(!data.lists.length){
    section.append(node('p','sub','Nessuna lista trovata o visibile per l’account Microsoft collegato.'));
   }else{
    const chooser=select('sharepoint_list',data.lists.map(x=>[x.id,x.name]),config.list_id||data.lists[0].id);
    section.append(field('Scegli l’elenco Microsoft Lists già creato',chooser),
     btn('Seleziona elenco',async()=>{
      try{
       const result=await apiMethod('/list/select','POST',{list_id:chooser.value});
       msg('Elenco collegato: '+result.list_name);render();
      }catch(error){msg(error.message,true)}
     },'small'));
   }
   ui.append(section);
  }catch(error){msg(error.message,true)}
 }
 async function inspect(ui){
  try{
   const data=await api('/microsoft/list/inspect');
   ui.querySelector('.microsoft-inspection')?.remove();
   const section=el('div',{class:'microsoft-inspection'});
   section.append(node('h3','','Controllo struttura: '+data.list_name));
   section.append(node('p','sub',data.message));
   section.append(node('p','sub','Colonne presenti: '+(data.column_names.join(', ')||'nessuna')));
   const missing=data.needed_for_sync.filter(x=>!data.column_names.includes(x));
   if(missing.length)section.append(node('p','sub','Colonne ancora da configurare in una fase successiva, dopo autorizzazione: '+missing.join(', ')));
   else section.append(node('p','sub','Colonne necessarie già presenti. Nessuna modifica effettuata.'));
   ui.append(section);
  }catch(error){msg(error.message,true)}
 }
 return {settings};
})();
