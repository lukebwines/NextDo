'use strict';
// File selection helpers. Files remain in browser memory until the task is saved.
const NextDoFileUI=(()=>{
 const extensions=['pdf','png','jpg','jpeg','webp','gif','bmp','txt','csv','doc','docx','xls','xlsx','ppt','pptx','rtf','odt','ods','odp'];
 const allowed=new Set(extensions.map(x=>'.'+x));
 const accept=extensions.map(x=>'.'+x).join(',');
 const maxSize=15*1024*1024;
 const maxBatch=10;
 const hasFiles=e=>e.dataTransfer&&Array.from(e.dataTransfer.types||[]).includes('Files');
 const ext=f=>(f.name.match(/\.[^.]+$/)||[''])[0].toLowerCase();
 const identity=f=>[f.name,f.size,f.lastModified].join('|');
 function validate(files,existing=[]){
  const selected=[...existing],errors=[];
  for(const file of Array.from(files||[])){
   if(!allowed.has(ext(file))){errors.push(file.name+': formato non consentito');continue}
   if(file.size>maxSize){errors.push(file.name+': dimensione superiore a 15 MB');continue}
   if(file.size===0){errors.push(file.name+': file vuoto');continue}
   if(selected.some(x=>identity(x)===identity(file)))continue;
   if(selected.length>=maxBatch){errors.push('Massimo 10 file per salvataggio');break}
   selected.push(file);
  }
  return {files:selected,errors};
 }
 function picker(host,initial=[],onError=message=>window.alert(message)){
  const panel=document.createElement('section');panel.className='file-upload-panel';
  const title=document.createElement('h3');title.textContent='Allegati';
  const zone=document.createElement('div');zone.className='file-drop-zone';zone.tabIndex=0;zone.setAttribute('role','button');
  zone.setAttribute('aria-label','Trascina i file qui oppure premi Invio per selezionarli');
  const glyph=document.createElement('span');glyph.className='file-upload-glyph';glyph.textContent='📎';
  const lead=document.createElement('strong');lead.textContent='Trascina qui PDF, immagini e documenti';
  const help=document.createElement('span');help.textContent='oppure seleziona i file • 15 MB ciascuno • massimo 10 alla volta';
  const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent='Seleziona file';
  const input=document.createElement('input');input.type='file';input.multiple=true;input.accept=accept;input.hidden=true;input.setAttribute('aria-label','Seleziona allegati');
  const names=document.createElement('ul');names.className='file-selected-list';names.setAttribute('aria-live','polite');
  zone.append(glyph,lead,help,button,input);panel.append(title,zone,names);
  let chosen=[];
  const redraw=()=>{names.replaceChildren();for(const f of chosen){
   const li=document.createElement('li');const label=document.createElement('span');
   label.textContent=f.name+' ('+Math.max(1,Math.ceil(f.size/1024))+' KB)';
   const remove=document.createElement('button');remove.className='btn small';remove.type='button';remove.textContent='Rimuovi';
   remove.setAttribute('aria-label','Rimuovi '+f.name);
   remove.addEventListener('click',()=>{chosen=chosen.filter(x=>x!==f);redraw()});
   li.append(label,remove);names.append(li);
  }};
  const add=files=>{const result=validate(files,chosen);chosen=result.files;redraw();if(result.errors.length)onError(result.errors.join('; '));return result.files.length};
  button.addEventListener('click',e=>{e.stopPropagation();input.click()});
  zone.addEventListener('click',e=>{if(e.target!==button&&e.target!==input)input.click()});
  zone.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.click()}});
  input.addEventListener('change',()=>{add(input.files);input.value=''});
  for(const element of [zone,host]){
   element.addEventListener('dragover',e=>{if(hasFiles(e)){e.preventDefault();e.stopPropagation();zone.classList.add('file-dragover');e.dataTransfer.dropEffect='copy'}});
   element.addEventListener('dragleave',e=>{if(!e.currentTarget.contains(e.relatedTarget))zone.classList.remove('file-dragover')});
   element.addEventListener('drop',e=>{if(hasFiles(e)){e.preventDefault();e.stopPropagation();zone.classList.remove('file-dragover');add(e.dataTransfer.files)}});
  }
  add(initial);
  return {element:panel,pending:()=>chosen.slice(),uploaded:f=>{chosen=chosen.filter(x=>x!==f);redraw()},open:()=>input.click(),focus:()=>zone.focus(),add};
 }
 function quickDrop(host,onFiles,onError=message=>window.alert(message)){
  host.addEventListener('dragover',e=>{if(hasFiles(e)){e.preventDefault();e.dataTransfer.dropEffect='copy';host.classList.add('file-dragover')}});
  host.addEventListener('dragleave',e=>{if(!host.contains(e.relatedTarget))host.classList.remove('file-dragover')});
  host.addEventListener('drop',e=>{if(!hasFiles(e))return;e.preventDefault();host.classList.remove('file-dragover');const result=validate(e.dataTransfer.files);if(result.errors.length)onError(result.errors.join('; '));if(result.files.length)onFiles(result.files)});
 }
 return {accept,validate,picker,quickDrop};
})();
