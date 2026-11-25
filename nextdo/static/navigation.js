/* Single history sentinel. Never reloads or writes private data to history. */
'use strict';
function createNextDoBack(history,enabled,consume){
 const key='nextdoBackV1';
 const kind=state=>state&&state[key];
 let armed=kind(history.state)==='guard';
 function arm(){
  if(!enabled())return;
  if(kind(history.state)==='guard'){armed=true;return}
  const state=history.state&&typeof history.state==='object'?history.state:{};
  if(kind(state)!=='base')history.replaceState({...state,[key]:'base'},'');
  history.pushState({...state,[key]:'guard'},'');
  armed=true;
 }
 function pop(event){
  if(kind(event.state)==='guard'){armed=true;return}
  if(!armed||kind(event.state)!=='base'){armed=false;return}
  armed=false;
  if(enabled()&&consume()){arm();return}
  // The sentinel was consumed. Leave the original entry exactly once.
  history.back();
 }
 return {arm,pop};
}
if(typeof module!=='undefined')module.exports={createNextDoBack};
