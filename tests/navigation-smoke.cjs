const assert=require('node:assert/strict');
const {createNextDoBack}=require('../nextdo/static/navigation.js');
let entries=[{external:true},null],pos=1,enabled=true,handled=true,consumed=0,backs=0,pushes=0;
const history={get state(){return entries[pos]},replaceState(s){entries[pos]=s},pushState(s){entries=entries.slice(0,pos+1);entries.push(s);pos++;pushes++},back(){backs++;if(pos>0){pos--;nav.pop({state:entries[pos]})}}};
let nav=createNextDoBack(history,()=>enabled,()=>{consumed++;return handled});
nav.arm();nav.arm();assert.equal(pushes,1);
for(let i=0;i<20;i++){history.back();assert.equal(pos,2);assert.equal(entries.length,3)}
assert.equal(consumed,20);assert.equal(backs,20);
handled=false;history.back();assert.equal(pos,0);assert.equal(backs,22);assert.equal(consumed,21);
pos=1;handled=true;nav.arm();enabled=false;history.back();assert.equal(pos,0);assert.equal(consumed,21);
pos=1;nav.arm();assert.equal(pos,1);
enabled=true;nav.arm();nav=createNextDoBack(history,()=>enabled,()=>true);history.back();assert.equal(pos,2);
console.log('Navigation sentinel: no duplicate entries, internal back, classic mode, dashboard exit, reload state OK');
