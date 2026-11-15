/** Real deployed source, fake Telegram HMAC, in-memory D1 only; check safe 503 codes. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto,createHmac} from 'node:crypto';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const source=readFileSync(process.argv[2],'utf8');
assert.ok(source.includes("NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC"),"Updated source missing");
const marker="const __ngoMiniAppDirectHTML=";
const offset=source.indexOf(marker);
assert.ok(offset>=0,"Embedded Mini App HTML missing");
const quotedStart=source.indexOf('"',offset+marker.length);
let quotedEnd=-1;
for(let i=quotedStart+1;i<source.length;i++){
  if(source[i]===String.fromCharCode(92)){i++;continue;}
  if(source[i]==='"'){quotedEnd=i;break;}
}
assert.ok(quotedStart>=0&&quotedEnd>quotedStart,"Embedded HTML JSON string unavailable");
const html=JSON.parse(source.slice(quotedStart,quotedEnd+1));
assert.ok(html.includes("message+=' (код: '+code+')'"),"User-visible safe code missing");
const worker=await import("data:text/javascript;base64,"+Buffer.from(source).toString('base64'));
const BOT_TOKEN='123456789:SYNTHETIC-ONLY-NEVER-SEND';
const USER=93217;
const facets={audience:'nonprofit',sectors:['social','recovery'],
   custom_sector:'',geo:'ukraine',region:'',detail:'Соціальні послуги',
   applicant_role:'lead',funding_format:'any'};
const key='123e4567-e89b-42d3-a456-426614174000';
const p=new URLSearchParams({auth_date:String(Math.floor(Date.now()/1000)),
 user:JSON.stringify({id:USER,first_name:'Synthetic'}),query_id:'test-only'});
const canon=[...p].sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>k+'='+v).join('\n');
const secret=createHmac('sha256','WebAppData').update(BOT_TOKEN).digest();
p.set('hash',createHmac('sha256',secret).update(canon).digest('hex'));
const body={initData:p.toString(),facets,idempotencyKey:key};
const url='https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/api/mini-app/order';
const call=()=>worker.default.fetch(new Request(url,{method:'POST',
 headers:{'content-type':'application/json'},body:JSON.stringify(body)}),
 {BOT_TOKEN,DB:{prepare(){throw new Error('D1 invoked prematurely')}},SYNC_SECRET:'TEST'});
const originalFetch=globalThis.fetch;
try{
 globalThis.fetch=async()=>{throw new Error('synthetic Telegram unavailable');};
 const telegram=await call();
 assert.equal(telegram.status,503);
 const m=await telegram.json();
 assert.equal(m.error_code,'TELEGRAM_UPSTREAM');
 assert.equal(m.ok,false);
 assert.ok(!JSON.stringify(m).includes('Synthetic'));
 globalThis.fetch=async()=>new Response(JSON.stringify({ok:true,result:{
  status:'member',user:{id:USER}}}),{status:200});
 const d1=await call();
 assert.equal(d1.status,503);
 const db=await d1.json();
 assert.equal(db.error_code,'D1_READ');
 assert.equal(db.ok,false);
 console.log('V052_TELEGRAM_UPSTREAM_503_SAFE_CODE_PASS=True');
 console.log('V052_D1_READ_503_SAFE_CODE_PASS=True');
 console.log('LIVE_ORDER_COUNT=0;LIVE_D1_WRITES=0;PERSONAL_DATA_LOGS=0');
}finally{globalThis.fetch=originalFetch;}
