(()=>{'use strict';
const root=document.getElementById('miniApp');
if(!root||root.dataset.initialized)return;
root.dataset.initialized='1';
const schema=window.NgoGrantsSchema;
if(!schema){document.getElementById('error').textContent='Не вдалося завантажити анкету.';return;}
const el=id=>document.getElementById(id);
const choices=el('choices'),extra=el('extra'),input=el('extraInput');
const robot=el('robot'),reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
const draft={audience:'',sectors:[],geo:'',region:'',detail:'',
 custom_sector:'',applicant_role:'lead',funding_format:'any'};
let index=0;
let reactionTimeout=null;
let focusExtra=false;
const pages=[
 {key:'audience',heading:'Хто подаватиме заявку?',help:'Виберіть тип заявника, щоб ми врахували умови участі.',options:schema.audiences},
 {key:'sectors',heading:'Які напрями вас цікавлять?',help:'Можна обрати декілька сфер. Гранти перевірятимемо для кожної окремо.',options:schema.sectors,multi:true},
 {key:'custom_sector',heading:'Потрібен точніший напрям?',help:'За бажанням додайте власний напрям. Можна пропустити.',optional:true,free:true,max:60},
 {key:'geo',heading:'Де шукаємо можливості?',help:'Географія допомагає відсіяти непридатні конкурси.',options:schema.geos},
 {key:'region',heading:'Оберіть регіон України',help:'Врахуємо вимоги щодо місця реалізації проєкту.',options:schema.regions,
   visible:()=>draft.geo==='region'},
 {key:'detail',heading:'Що саме ви плануєте?',help:'Коротко опишіть діяльність або ідею проєкту. Не зазначайте контакти.',free:true,optional:true,max:180},
 {key:'applicant_role',heading:'У якій ролі братимете участь?',help:'Конкурси можуть вимагати статусу головного заявника чи партнера.',options:schema.roles},
 {key:'funding_format',heading:'Яке фінансування вам потрібне?',help:'Виберіть лише гранти або ширший перелік можливостей.',options:schema.formats}
];
const label=k=>({audience:'Заявник',sectors:'Сфери',custom_sector:'Інший напрям',geo:'Географія',region:'Регіон',
 detail:'Діяльність',applicant_role:'Роль',funding_format:'Формат'})[k]||k;
function visible(){return pages.filter(p=>!p.visible||p.visible());}
function all(){return visible().length;}
function page(){return visible()[index]||null;}
function resetNode(n){n.replaceChildren();}
function trigger(kind='ack'){
 if(reactionTimeout!==null)clearTimeout(reactionTimeout);
 robot.classList.remove('react','wave');
 if(reduced.matches)return;
 void robot.offsetWidth;
 robot.classList.add(kind==='wave'?'wave':'react');
 reactionTimeout=setTimeout(()=>robot.classList.remove('react','wave'),720);
}
function error(msg){el('error').textContent=msg||'';}
function makeButton(text,value,selected,callback,multi){
 const b=document.createElement('button');b.type='button';
 b.className=(multi?'select-many':'choice')+(selected?' selected':'');
 b.setAttribute('aria-pressed',selected?'true':'false');
 const textEl=document.createElement('span');textEl.textContent=text;
 const mark=document.createElement('span');mark.className='arrow';
 mark.textContent=selected?'✓':multi?'＋':'→';
 b.append(textEl,mark);b.addEventListener('click',callback);
 return b;
}
function next(){
 const p=page();
 if(!p)return;
 if(p.key==='audience'&&!draft.audience)return error('Оберіть заявника.');
 if(p.key==='sectors'&&!draft.sectors.length)return error('Оберіть хоча б один напрям.');
 if(p.key==='geo'&&!draft.geo)return error('Оберіть географію.');
 if(p.key==='region'&&!draft.region)return error('Оберіть регіон.');
 index+=1;focusExtra=false;render();trigger('ack');
}
function setValue(key,value){
 draft[key]=value;
 if(key==='geo'&&value!=='region')draft.region='';
 error('');
 next();
}
function buttonOptions(p){
 const multi=Boolean(p.multi);
 for(const [value,name] of Object.entries(p.options)){
   const selected=multi?draft.sectors.includes(value):draft[p.key]===value;
   choices.append(makeButton(name,value,selected,()=>{
     if(multi){
       if(value==='all')draft.sectors=['all'];
       else{
         const prev=draft.sectors.filter(x=>x!=='all');
         draft.sectors=prev.includes(value)?prev.filter(x=>x!==value):[...prev,value];
       }
       error('');render();trigger('ack');
     }else{setValue(p.key,value);}
   },multi));
 }
}
function renderExtra(p){
 extra.hidden=false;
 el('extraLabel').textContent=p.key==='detail'?'Опишіть проєкт одним реченням':'Ваш напрям (необов’язково)';
 input.placeholder=p.key==='detail'?'Наприклад: соціальний транспорт для людей з інвалідністю':'Наприклад: документальне кіно';
 input.maxLength=p.max;
 input.value=draft[p.key]||'';
 el('next').hidden=false;
 el('next').textContent=draft[p.key]?'Далі →':'Пропустити →';
}
function renderSummary(){
 el('question').textContent='Перевірте свій запит';
 el('hint').textContent='Це ще демонстрація. Дані не передаватимуться робочому боту.';
 el('stepLabel').textContent='Підсумок';
 el('next').hidden=true;
 const wrap=el('summary');wrap.hidden=false;
 try{
  const rows=schema.describe(draft);
  const dl=document.createElement('dl');
  for(const [name,value] of rows){const row=document.createElement('div');row.className='row';
    const dt=document.createElement('dt');dt.textContent=name;const dd=document.createElement('dd');dd.textContent=value;
    row.append(dt,dd);dl.append(row);}
  wrap.append(dl);
  const note=document.createElement('p');note.className='notice';
  const live=root.dataset.nativeSend==='true';
  note.textContent=live
    ?'Після натискання Telegram передасть анкету боту. Він перевірить підписку та денний ліміт і підтвердить замовлення в чаті. Натискання саме по собі ще не означає прийняття.'
    :'✓ Анкету сформовано локально. Це лише демонстрація; замовлення не надсилається.';
  wrap.append(note);
  if(live){
    const send=document.createElement('button');
    send.type='button';send.className='primary';send.textContent='✅ Замовити каталог';
    send.style.marginTop='14px';
    const api=window.Telegram&&window.Telegram.WebApp;
    if(!api||typeof api.sendData!=='function'){
      send.disabled=true;
      note.textContent='Відкрийте застосунок із кнопки Telegram-бота. Звичайний браузер не може надіслати замовлення.';
    }else{
      send.addEventListener('click',()=>{
        if(send.disabled)return;
        try{
          const facets=schema.normalize(draft);
          const data=JSON.stringify({type:'ngo-grants-miniapp-v1',facets});
          if(new TextEncoder().encode(data).length>4096)
            throw Error('Дані завеликі для Telegram');
          send.disabled=true;
          send.textContent='Передаємо до Telegram…';
          api.sendData(data);
        }catch(_){
          send.disabled=false;
          send.textContent='✅ Замовити каталог';
          error('Не вдалося передати замовлення. Відкрийте застосунок через кнопку бота.');
        }
      });
    }
    wrap.append(send);
  }
 }catch(e){error(e.message);index=Math.max(0,index-1);}
}
function render(){
 const steps=all();const p=page(),done=!p;
 el('progressFill').style.width=(done?100:Math.round(index/steps*100))+'%';
 el('progress').setAttribute('aria-valuenow',String(done?100:Math.round(index/steps*100)));
 el('back').disabled=index===0;el('reset').disabled=false;
 el('stepLabel').textContent='Крок '+(index+1)+' із '+steps;
 extra.hidden=true;el('next').hidden=true;el('summary').hidden=true;
 resetNode(choices);resetNode(el('summary'));error('');
 if(done){renderSummary();return;}
 el('question').textContent=p.heading;el('hint').textContent=p.help;
 if(p.options)buttonOptions(p);
 if(p.free)renderExtra(p);
 if(p.multi){
    el('next').hidden=false;el('next').textContent='Продовжити →';el('next').disabled=!draft.sectors.length;
 }else if(p.options){
    el('next').hidden=true;el('next').disabled=false;
 }
}
extra.addEventListener('submit',e=>{
 e.preventDefault();const p=page();if(!p||!p.free)return;
 const value=schema.sanitizeText(input.value,p.max);
 if(/https?:\/\/|@|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b/i.test(value))
   return error('Не вказуйте посилань, адрес пошти чи контактних даних.');
 draft[p.key]=value;next();
});
el('next').addEventListener('click',()=>{
 const p=page();
 if(p&&p.free){extra.requestSubmit();return;}
 next();
});
el('back').addEventListener('click',()=>{if(index>0){index--;render();trigger('ack');}});
el('reset').addEventListener('click',()=>{
 Object.assign(draft,{audience:'',sectors:[],geo:'',region:'',detail:'',
   custom_sector:'',applicant_role:'lead',funding_format:'any'});
 index=0;render();trigger('wave');
});
if(window.Telegram&&window.Telegram.WebApp){
 try{window.Telegram.WebApp.ready();window.Telegram.WebApp.expand();}catch(_){}
}
render();
})();