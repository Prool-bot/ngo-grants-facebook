'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const schema=require('../schema.js');

class FakeElement {
 constructor(tag='div'){
  this.tag=tag;this.children=[];this.listeners={};this.hidden=false;
  this.disabled=false;this.dataset={};this.value='';
  this.classList={add(){},remove(){}};
  this.style={};this.textContent='';this.className='';
 }
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[...nodes];}
 addEventListener(type,fn){this.listeners[type]=fn;}
 setAttribute(name,value){this[name]=value;}
 click(){const fn=this.listeners.click;if(fn)fn({preventDefault(){}});}
 requestSubmit(){const fn=this.listeners.submit;if(fn)fn({preventDefault(){}});}
}
function start(nativeSend=false){
 const nodes={};
 const ids=[
  'miniApp','choices','extra','extraInput','robot','question','hint','stepLabel',
  'progressFill','progress','back','next','reset','error','summary','extraLabel',
  'mode','disclaimer'
 ];
 for(const id of ids)nodes[id]=new FakeElement(id);
 nodes.miniApp.dataset.nativeSend=nativeSend?'true':'false';
 nodes.miniApp.dataset.initialized='';
 nodes.progress.setAttribute=()=>{};
 const doc={getElementById:id=>nodes[id],createElement:tag=>new FakeElement(tag)};
 const wnd={NgoGrantsSchema:schema,matchMedia:()=>({matches:true})};
 if(nativeSend)wnd.Telegram={WebApp:{ready(){},expand(){},sendData(){throw Error('Never send in test');}}};
 const app=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
 vm.runInNewContext(app,{window:wnd,document:doc,TextEncoder,setTimeout,clearTimeout});
 function option(label){
  const btn=nodes.choices.children.find(b=>b.children[0]?.textContent===label);
  if(!btn)throw Error('Option not found: '+label);
  btn.click();
 }
 const next=()=>nodes.next.click();
 const skip=()=>nodes.extra.requestSubmit();
 return {nodes,option,next,skip};
}
function reachRole(testApp){
 const {nodes,option,next,skip}=testApp;
 option('Громадська організація / благодійний фонд');
 option('Соціальна та гуманітарна сфера');
 next(); // sectors
 skip(); // custom sector
 option('Україна');
 skip(); // project detail
 assert.match(nodes.question.textContent,/ролі/);
 assert.equal(nodes.stepLabel.textContent,'Крок 6 із 7');
}
test('role has a selected default AND visible Continue button; final step also advances',()=>{
 const app=start();
 reachRole(app);
 const {nodes,option,next}=app;
 assert.equal(nodes.next.hidden,false);
 assert.equal(nodes.next.disabled,false);
 assert.equal(nodes.next.textContent,'Продовжити →');
 assert.equal(nodes.choices.children[0]['aria-pressed'],'true');
 next();
 assert.match(nodes.question.textContent,/фінансування/);
 assert.equal(nodes.stepLabel.textContent,'Крок 7 із 7');
 assert.equal(nodes.next.hidden,false);
 assert.equal(nodes.next.disabled,false);
 next();
 assert.equal(nodes.stepLabel.textContent,'Підсумок');
 assert.match(nodes.question.textContent,/Перевірте/);
 assert.equal(nodes.summary.hidden,false);
});
test('role can be changed without unexpected advance; explicit Continue is required',()=>{
 const app=start();reachRole(app);
 const {nodes,option,next}=app;
 option('Партнер');
 assert.match(nodes.question.textContent,/ролі/);
 assert.equal(nodes.choices.children[1]['aria-pressed'],'true');
 assert.equal(nodes.next.hidden,false);
 next();
 assert.match(nodes.question.textContent,/фінансування/);
});
test('live Mini App correctly labels real ordering, offline preview stays truthful',()=>{
 const online=start(true);
 assert.equal(online.nodes.mode.textContent,'Telegram · грантовий помічник');
 assert.doesNotMatch(online.nodes.disclaimer.textContent,/прототип/);
 const offline=start(false);
 assert.match(offline.nodes.mode.textContent,/Демонстрація/);
 assert.match(offline.nodes.disclaimer.textContent,/прототип/);
});

test('individual interested in business is warned about FOP eligibility without forced reclassification',()=>{
 const app=start();
 const {nodes,option,next,skip}=app;
 option('Фізична особа');
 option('Підприємництво');
 assert.match(nodes.hint.textContent,/зареєстровані як ФОП/);
 next(); // sectors
 skip(); // custom sector
 option('Україна');
 skip(); // project detail
 next(); // role
 next(); // funding
 assert.equal(nodes.stepLabel.textContent,'Підсумок');
 const warning=nodes.summary.children.find(x=>x.className==='notice'&&/зареєстрований ФОП/.test(x.textContent));
 assert.ok(warning,'Warning is required when business interests are chosen by individuals');
 const change=nodes.summary.children.find(x=>/Я ФОП \/ бізнес/.test(x.textContent));
 assert.ok(change,'User should be offered an explicit change, not an automatic one');
 change.click();
 assert.match(nodes.question.textContent,/Хто подаватиме/);
 assert.equal(nodes.choices.children[1]['aria-pressed'],'true','Registered FOP/Business should be selected explicitly');
});
