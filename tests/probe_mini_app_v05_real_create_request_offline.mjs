/**
 * Offline E2E of the ACTUAL deployed v0.5 Worker createRequest function.
 * Unlike the earlier test, do NOT replace createRequest with an unconditional
 * fake commit: emulate the D1 transaction in memory to expose precommit errors.
 * No valid Telegram initData or D1 writes ever reach production.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHmac,webcrypto} from "node:crypto";
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const file=process.argv[2];
if(!file)throw Error("Ephemeral worker source path required");
const source=readFileSync(file,"utf8");
if(!source.includes("const __ngoMiniAppDirectRouteEnabled=true;")||
   !source.includes("NGO_MINI_APP_DIRECT_API_DORMANT_V05"))
 throw Error("Unexpected Worker source version");
const worker=await import("data:text/javascript;base64,"+
                         Buffer.from(source).toString("base64"));
const fakeToken="123456789:SANDBOX-ONLY-FAKE-TOKEN-NO-SEND";
const userId=777123;
const reqId="123e4567-e89b-42d3-a456-426614174000";
const requestDay=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Kyiv",
  year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const facets={audience:"nonprofit",sectors:["environment","culture"],
  custom_sector:"",geo:"ukraine",region:"",
  detail:"Екологічний освітній проєкт",applicant_role:"lead",
  funding_format:"any"};
const actions=[],rows=new Map(),settings=new Map();
const operation=(sql)=>{
 let normalized=String(sql).toUpperCase().replace(/\s+/g," ");
 return normalized.match(/^\s*(SELECT|INSERT|DELETE|UPDATE|REPLACE|CREATE)/)?.[1]||"OTHER";
};
function stmt(sql){
 const op=operation(sql);
 const text=String(sql).toUpperCase();
 let args=[];
 const kind=text.includes("REQUESTS")?"requests":
  text.includes("LEGACY_LIMITS")?"legacy_limits":
  text.includes("CATALOGS")?"catalogs":
  text.includes("SETTINGS")?"settings":"other";
 const s={
  bind(...values){args=values;return s},
  async first(){
   actions.push("QUERY_"+op+"_"+kind+"_FIRST");
   if(kind==="requests" && op==="SELECT"){
     // Query by update ID is the only route allowed to return a request.
     const inputId=args.find(x=>Number.isSafeInteger(x)&&x>2**51);
     return inputId!==undefined?(rows.get(inputId)||null):null;
   }
   if(kind==="settings" && op==="SELECT"){
     if(args.length===0)return null;
     return settings.has(args[0])?{value:settings.get(args[0])}:null;
   }
   return null;
  },
  async all(){
   actions.push("QUERY_"+op+"_"+kind+"_ALL");
   return {success:true,results:[]};
  },
  async run(){
   actions.push("QUERY_"+op+"_"+kind+"_RUN");
   if(kind==="settings"){
     if(op==="INSERT" || op==="REPLACE")settings.set(args[0],args[1]);
     if(op==="DELETE")settings.delete(args[0]);
   }
   return {success:true,meta:{changes:1,last_row_id:88}};
  },
  __sql:sql,
  __args:()=>args
 };
 return s;
}
const DB={
 prepare:stmt,
 async batch(statements){
  actions.push("D1_BATCH");
  for(const s of statements){
   const sql=s.__sql.toUpperCase();
   const values=s.__args();
   if(sql.includes("INTO REQUESTS")&&
      (sql.includes("INSERT")||sql.includes("REPLACE"))){
    const id=values[0];
    assert.ok(Number.isSafeInteger(id)&&id>2**51,"Bad request ID");
    let day=values.find(x=>typeof x==="string"&&/^\d{4}-\d\d-\d\d$/.test(x));
    rows.set(id,{update_id:id,day:day||requestDay,status:"pending"});
    actions.push("INSERT_REQUESTS");
   }
   if(sql.includes("INTO SETTINGS") && values.length>=2){
      settings.set(values[0],values[1]);actions.push("INSERT_SETTINGS");
   }
  }
  return statements.map(()=>({success:true,meta:{changes:1},results:[]}));
 },
 async exec(){throw Error("Unsafe D1 exec not supported in offline simulation")}
};
const originalFetch=globalThis.fetch;
globalThis.fetch=async(url,opts)=>{
 const str=String(url);
 if(!str.startsWith("https://api.telegram.org/bot"+fakeToken+"/"))
   throw Error("Unexpected external network (blocked)");
 const action=str.split("/").at(-1);
 if(action!=="getChatMember")throw Error("Unexpected Telegram network call "+action);
 actions.push("MOCK_GET_CHAT_MEMBER");
 return new Response(JSON.stringify({ok:true,result:{
  status:"member",user:{id:userId}}}),{status:200});
};
function sign(){
 const p=new URLSearchParams({
  auth_date:String(Math.floor(Date.now()/1000)),
  user:JSON.stringify({id:userId,first_name:"Synthetic Offline"}),
  query_id:"offline"
 });
 const canonical=[...p].sort(([a],[b])=>a.localeCompare(b))
  .map(([k,v])=>k+"="+v).join("\n");
 const secret=createHmac("sha256","WebAppData").update(fakeToken).digest();
 p.set("hash",createHmac("sha256",secret).update(canonical).digest("hex"));
 return p.toString();
}
try{
 const body={initData:sign(),facets,idempotencyKey:reqId};
 const r=await worker.default.fetch(new Request(
   "https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/api/mini-app/order",
   {method:"POST",headers:{"content-type":"application/json"},
    body:JSON.stringify(body)}
 ),{BOT_TOKEN:fakeToken,DB,SYNC_SECRET:"OFFLINE-NO-USE",WEBHOOK_SECRET:"OFFLINE"});
 const safeResponse=await r.json();
 const result={status:r.status,ok:safeResponse?.ok===true,
  code:safeResponse?.error==="Не вдалося підтвердити замовлення. Спробуйте перевірити стан черги у боті."?
  "UNCLASSIFIED_503":(safeResponse?.status||"OTHER"),
  dbCommitReached:actions.includes("D1_BATCH"),
  dbInsertPrepared:actions.includes("INSERT_REQUESTS"),
  dbRows:rows.size,
  operationCounts:Object.fromEntries([...new Set(actions)].map(x=>[x,actions.filter(y=>x===y).length])),
  externalCalls:0,productionD1Writes:0,realOrders:0
 };
 console.log("LIVE_V05_ACTUAL_CREATE_REQUEST_OFFLINE_DIAGNOSIS");
 console.log(JSON.stringify(result,null,2));
 if(r.status!==201&&r.status!==200){
   throw Error("Actual legacy createRequest pathway returns "+r.status+
   " in an isolated synthetic offline scenario");
 }
}catch(err){
 console.error("DIAGNOSIS_RESULT="+(err instanceof Error?err.message:"Unknown failure"));
 process.exitCode=1;
}finally{globalThis.fetch=originalFetch}
