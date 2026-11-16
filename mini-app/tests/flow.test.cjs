'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const schema=require('../schema.js');
const directClient=require('../direct-client.js');

class FakeElement {
 constructor(tag='div'){
  this.tag=tag;this.children=[];this.listeners={};this.hidden=false;
  this.disabled=false;this.dataset={};this.value='';
  this._classes=new Set();
  this.classList={add:(...names)=>names.forEach(x=>this._classes.add(x)),
                  remove:(...names)=>names.forEach(x=>this._classes.delete(x)),
                  contains:name=>this._classes.has(name)};
  this.style={};this.textContent='';this.className='';
 }
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[...nodes];}
 addEventListener(type,fn){this.listeners[type]=fn;}
 setAttribute(name,value){this[name]=value;}
 click(){const fn=this.listeners.click;if(fn)return fn({preventDefault(){}});}
 requestSubmit(){const fn=this.listeners.submit;if(fn)fn({preventDefault(){}});}
}
function start(nativeSend=false,directSend=false,post=async()=>{throw Error('mock post not configured');},allowMotion=false){
 const nodes={};
 const ids=[
  'miniApp','choices','extra','extraInput','robot','robotArm','greet','question','hint','stepLabel',
  'progressFill','progress','back','next','reset','error','summary','extraLabel',
  'mode','disclaimer'
 ];
 for(const id of ids)nodes[id]=new FakeElement(id);
 nodes.miniApp.dataset.nativeSend=nativeSend?'true':'false';
 nodes.miniApp.dataset.directSend=directSend?'true':'false';
 nodes.miniApp.dataset.initialized='';
 nodes.progress.setAttribute=()=>{};
 const doc={getElementById:id=>nodes[id],createElement:tag=>new FakeElement(tag)};
 const wnd={NgoGrantsSchema:schema,matchMedia:()=>({matches:!allowMotion})};
 if(nativeSend||directSend)wnd.Telegram={WebApp:{ready(){},expand(){},initData:directSend?'SIGNED_FAKE_TELEGRAM_TEST_DATA':'',sendData(){throw Error('Never send in test');}}};
 if(directSend){
  wnd.NgoGrantsDirectClient=directClient;
  wnd.crypto={randomUUID:()=> '123e4567-e89b-42d3-a456-426614174000'};
  wnd.location={origin:'https://example.workers.dev'};
  wnd.fetch=post;
 }
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

test('direct-link UI waits for durable server receipt and never calls Telegram sendData',async()=>{
 const posts=[];
 const app=start(false,true,async(url,options)=>{
  posts.push({url,options});
  return {status:201,json:async()=>({ok:true,order_id:423,status:'created'})};
 });
 reachRole(app);
 app.next(); // funding
 app.next(); // summary
 assert.equal(app.nodes.stepLabel.textContent,'Підсумок');
 assert.equal(app.nodes.mode.textContent,'Telegram · пошук із каналу');
 const send=app.nodes.summary.children.find(x=>x.textContent==='✅ Замовити каталог');
 assert.ok(send,'Direct mode must show one explicit submit button');
 await send.click();
 assert.equal(posts.length,1);
 assert.equal(posts[0].url,'https://example.workers.dev/api/mini-app/order');
 const payload=JSON.parse(posts[0].options.body);
 assert.deepEqual(Object.keys(payload).sort(),['facets','idempotencyKey','initData']);
 assert.equal(send.disabled,true);
 assert.equal(send.textContent,'Замовлення підтверджено');
 assert.ok(app.nodes.summary.children.some(x=>/№423/.test(x.textContent)));
});
test('direct-link UI refuses unconfirmed queue commit and keeps retry enabled',async()=>{
 let count=0;
 const app=start(false,true,async()=>{
   count++;return {status:503,json:async()=>({ok:false,error:'Private detail'})};
 });
 reachRole(app);app.next();app.next();
 const send=app.nodes.summary.children.find(x=>x.textContent==='✅ Замовити каталог');
 await send.click();
 assert.equal(count,1);
 assert.equal(send.disabled,false);
 assert.equal(send.textContent,'↻ Повторити підтвердження');
 assert.match(app.nodes.error.textContent,/тимчасово недоступний/);
 assert.doesNotMatch(app.nodes.summary.children.map(x=>x.textContent).join(' '),/№\\d+/);
});


test('broad all/all request demands a concrete description instead of 139 vague results',()=>{
 const app=start();const {nodes,option,next,skip}=app;
 option('Усі типи заявників');
 option('Усі напрями');next();skip();
 option('Міжнародні можливості');
 assert.match(nodes.question.textContent,/конкретну можливість/);
 assert.equal(nodes.next.textContent,'Далі →');
 skip();
 assert.match(nodes.error.textContent,/широкого запиту/);
 assert.match(nodes.question.textContent,/конкретну можливість/);
 nodes.extraInput.value='Соціальний транспорт для маломобільних людей';
 skip();
 assert.match(nodes.question.textContent,/ролі/);
 next();next();
 const warning=nodes.summary.children.find(x=>x.className==='notice'&&/Широкий вибір/.test(x.textContent));
 assert.ok(warning);
});
test('robot arm waves on explicit hello while robot itself never bounces',()=>{
 const app=start(false,false,undefined,true);
 assert.equal(app.nodes.robotArm.classList.contains('wave'),false);
 app.nodes.greet.click();
 assert.equal(app.nodes.robotArm.classList.contains('wave'),true);
 assert.equal(app.nodes.robot.classList.contains('wave'),false);
});

test('first form choice produces one real hand wave even with reduced motion; hello repeats it',()=>{
 const app=start(); // mock prefers-reduced-motion = true
 let armWaves=0;
 const originalAdd=app.nodes.robotArm.classList.add;
 app.nodes.robotArm.classList.add=(...names)=>{
   if(names.includes('wave'))armWaves++;
   return originalAdd(...names);
 };
 assert.equal(armWaves,0);
 app.option('Громадська організація / благодійний фонд');
 assert.equal(armWaves,1,'first answer must visibly start wave');
 assert.equal(app.nodes.robotArm.classList.contains('wave'),true);
 app.option('Соціальна та гуманітарна сфера');
 assert.equal(armWaves,1,'normal navigation must not wave continuously');
 app.nodes.greet.click();
 assert.equal(armWaves,2,'explicit hello replays wave');
 assert.equal(app.nodes.robot.classList.contains('wave'),false,'body stays still');
});
