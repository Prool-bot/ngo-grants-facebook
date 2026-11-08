/**
 * Simulate actual ENABLED candidate v0.5 Worker with verified Telegram initData and
 * D1 persistent readback. The legacy createRequest is intercepted BEFORE
 * touching D1, and Telegram network calls are fully mocked. No real orders.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHmac,webcrypto} from "node:crypto";
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const path=process.argv[2];
if(!path)throw Error("Expected private staged Worker JS path");
let source=readFileSync(path,"utf-8");
if(!source.includes("NGO_MINI_APP_DIRECT_API_DORMANT_V05"))
  throw Error("Unexpected Worker version; do not test public API");
const FLAG="const __ngoMiniAppDirectRouteEnabled=true;";
if(source.split(FLAG).length!==2)
  throw Error("Activated v0.5 stage must have exactly one enabled route gate");
// Only for this completely isolated process, replace the existing queue
// transaction. This ensures no real D1 or Telegram user data is touched.
const anchor=/async function createRequest\(env,chat,userId,d,updateId\)\{/g;
if([...source.matchAll(anchor)].length!==1)
  throw Error("Expected exactly one private Worker createRequest function");
source=source.replace(anchor,`$&
  globalThis.__directMiniAppLegacyCalls.push({chat,userId,updateId,draftStage:d.stage});
  if(!env.__miniAppHttpOrderMode)throw Error("Expected direct no-DM flag");
  await env.DB.__commit(updateId,userId,d);
  return {accepted:true};
`);
globalThis.__directMiniAppLegacyCalls=[];
let worker;
try{
  worker=await import("data:text/javascript;base64,"+
    Buffer.from(source).toString("base64"));
}catch(_){
  throw Error("Private Worker offline import failed; code withheld");
}

const URL="https://ngo-grants-instant-bot.oleh-protasoff.workers.dev";
const PATH="/api/mini-app/order";
const USER=145222;
const token="123456789:OFFLINE-DIRECT-ONLY-BOT-TOKEN";
const uuid="123e4567-e89b-42d3-a456-426614174000";
const facets={
  audience:"nonprofit",sectors:["social","recovery"],
  custom_sector:"",geo:"ukraine",region:"",
  detail:"Соціальний транспорт",applicant_role:"lead",
  funding_format:"grant_only"
};
const dbRows=new Map(),status={value:"member"},realCalls=[];
const fakeDb={
  async __commit(id,userId,draft){
    if(!Number.isSafeInteger(id)||id<=2**51||userId!==USER||
       draft.stage!=="confirm")throw Error("Bad fake queue arguments");
    const day=new Intl.DateTimeFormat("en-CA",{
      timeZone:"Europe/Kyiv",year:"numeric",month:"2-digit",day:"2-digit"
    }).format(new Date());
    dbRows.set(id,{update_id:id,day,status:"pending"});
  },
  prepare(sql){
    assert.equal(sql,"SELECT update_id, day, status FROM requests WHERE update_id = ? LIMIT 1");
    return {bind(id){return {first:async()=>dbRows.get(id)||null};}};
  }
};
const environment={BOT_TOKEN:token,DB:fakeDb};
const oldFetch=globalThis.fetch;
globalThis.fetch=async(url,options)=>{
  const method=String(url).split("/").at(-1);
  realCalls.push(method);
  assert.equal(method,"getChatMember","No external network except mocked member check");
  const body=JSON.parse(options.body);
  assert.equal(body.chat_id,"@ngo_grants");
  assert.equal(body.user_id,USER);
  return new Response(JSON.stringify({ok:true,result:{
    user:{id:USER},status:status.value
  }}),{status:200,headers:{"content-type":"application/json"}});
};

function sign(uid=USER,now=Math.floor(Date.now()/1000)){
  const p=new URLSearchParams({
    auth_date:String(now),
    user:JSON.stringify({id:uid,first_name:"Synthetic"}),
    query_id:"offline-only"
  });
  const canonical=[...p].sort(([a],[b])=>a.localeCompare(b))
    .map(([k,v])=>k+"="+v).join("\n");
  const secret=createHmac("sha256","WebAppData").update(token).digest();
  p.set("hash",createHmac("sha256",secret).update(canonical).digest("hex"));
  return p.toString();
}
async function submit(input,options={}){
  return worker.default.fetch(new Request(URL+PATH,{
    method:"POST",headers:{
      "content-type":"application/json",
      ...(options.origin?{origin:options.origin}:{})
    },
    body:JSON.stringify(input)
  }),environment);
}
try{
  // Main Mini App direct page is ready for later BotFather registration.
  const direct=await worker.default.fetch(new Request(URL+"/mini-app/direct"),environment);
  assert.equal(direct.status,200);
  const html=await direct.text();
  assert.match(html,/data-native-send="false" data-direct-send="true"/);
  assert.match(html,/telegram-web-app\.js/);
  assert.match(html,/NGO Grants AI/);
  assert.doesNotMatch(html,/BOT_TOKEN|WEBHOOK_SECRET|SYNC_SECRET/);

  const invalid=await submit({initData:"invalid",facets,idempotencyKey:uuid});
  assert.equal(invalid.status,401);
  assert.equal(dbRows.size,0);
  const userInput={initData:sign(),facets,idempotencyKey:uuid};
  const created=await submit(userInput);
  assert.equal(created.status,201);
  const receipt=await created.json();
  assert.equal(receipt.ok,true);
  assert.equal(receipt.status,"created");
  assert.ok(receipt.order_id>2**51&&Number.isSafeInteger(receipt.order_id));
  assert.equal(dbRows.size,1);
  assert.equal(globalThis.__directMiniAppLegacyCalls.length,1);

  const again=await submit(userInput);
  assert.equal(again.status,200);
  const existing=await again.json();
  assert.equal(existing.status,"existing");
  assert.equal(existing.order_id,receipt.order_id);
  assert.equal(globalThis.__directMiniAppLegacyCalls.length,1);

  status.value="left";
  const unsubscribed=await submit({...userInput,
     idempotencyKey:"223e4567-e89b-42d3-a456-426614174000"});
  assert.equal(unsubscribed.status,403);
  assert.equal(dbRows.size,1);
  status.value="member";
  const forbiddenOrigin=await submit(userInput,{origin:"https://malicious.invalid"});
  assert.equal(forbiddenOrigin.status,403);
  const invalidFacet=await submit({
    ...userInput,facets:{...facets,sectors:["not-allowed"]}
  });
  assert.equal(invalidFacet.status,400);
  const absent=await worker.default.fetch(new Request(URL+PATH),environment);
  assert.equal(absent.status,405);

  const old=await worker.default.fetch(new Request(URL+"/mini-app"),environment);
  assert.equal(old.status,200);
  assert.equal(old.headers.get("x-ngo-mini-app-version"),"0.4");
  console.log("MINI_APP_DIRECT_ACTUAL_WORKER_FAKE_D1_E2E_PASS");
  console.log("SIGNED_INITDATA_ACCEPTED=1;DURABLE_RECEIPT=1;RETRY_EXISTING=1");
  console.log("UNSUBSCRIBED_REJECTED=1;FORGED_SESSION_REJECTED=1;BAD_ORIGIN_REJECTED=1");
  console.log("EXISTING_KEYBOARD_MINIAPP_INTACT=1");
  console.log("PRODUCTION_D1_WRITES=0;REAL_TELEGRAM_CALLS=0;REAL_ORDERS=0");
}finally{
  globalThis.fetch=oldFetch;
  delete globalThis.__directMiniAppLegacyCalls;
}
