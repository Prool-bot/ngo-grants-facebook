/**
 * Offline E2E of the ACTUAL deployed v0.5 Worker createRequest function.
 * Unlike the earlier test, do NOT replace createRequest with an unconditional
 * fake commit: emulate the D1 transaction in memory to expose precommit errors.
 * No valid Telegram initData or D1 writes ever reach production.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHmac,webcrypto} from "node:crypto";
import {DatabaseSync} from "node:sqlite";
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
// Strict, genuine SQLite in-memory database reproducing the verified D1 schema.
// Unlike the permissive mock, this enforces real SQL constraints and column names.
const actions=[];
const sqlite=new DatabaseSync(":memory:");
sqlite.exec(`
CREATE TABLE requests (update_id INTEGER PRIMARY KEY, user_hash TEXT NOT NULL,
 day TEXT NOT NULL, topic TEXT NOT NULL, created_at TEXT NOT NULL,
 status TEXT NOT NULL);
CREATE UNIQUE INDEX requests_user_day ON requests(user_hash, day);
CREATE INDEX requests_status ON requests(status);
CREATE TABLE legacy_limits(user_hash TEXT NOT NULL, day TEXT NOT NULL,
 PRIMARY KEY(user_hash, day));
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE catalogs(request_id INTEGER PRIMARY KEY, topic TEXT NOT NULL,
 title TEXT NOT NULL, channel_url TEXT NOT NULL, valid_until TEXT NOT NULL,
 published_on TEXT NOT NULL);
`);
const operation=(sql)=>String(sql).trim().split(/\\s+/)[0].toUpperCase();
const classify=(sql)=>/\\brequests\\b/i.test(sql)?"requests":
 /\\blegacy_limits\\b/i.test(sql)?"legacy_limits":
 /\\bsettings\\b/i.test(sql)?"settings":
 /\\bcatalogs\\b/i.test(sql)?"catalogs":"other";
const logError=(err,sql)=>{
 const str=String(err?.message||"DB_ERROR");
 const safe=str.replace(/['\"].*?['\"]/g,"<quoted>").slice(0,180);
 actions.push("SQL_ERROR_"+classify(sql)+"_"+safe);
};
function stmt(sql){
 let args=[];
 const op=operation(sql),kind=classify(sql);
 const s={
  bind(...values){args=values;return s},
  async first(){
   actions.push("QUERY_"+op+"_"+kind+"_FIRST");
   try{return sqlite.prepare(sql).get(...args)??null}
   catch(e){logError(e,sql);throw e}
  },
  async all(){
   actions.push("QUERY_"+op+"_"+kind+"_ALL");
   try{return {success:true,results:sqlite.prepare(sql).all(...args)}}
   catch(e){logError(e,sql);throw e}
  },
  async run(){
   actions.push("QUERY_"+op+"_"+kind+"_RUN");
   try{const r=sqlite.prepare(sql).run(...args);return {success:true,meta:{changes:r.changes,last_row_id:Number(r.lastInsertRowid)}}}
   catch(e){logError(e,sql);throw e}
  },
  __sql:sql,__args:()=>args
 };
 return s;
}
const DB={
 prepare:stmt,
 async batch(statements){
  actions.push("D1_BATCH");
  sqlite.exec("BEGIN");
  try{
   const result=[];
   for(const s of statements){
    const sql=s.__sql;
    const op=operation(sql),kind=classify(sql);
    actions.push("BATCH_"+op+"_"+kind);
    const r=sqlite.prepare(sql).run(...s.__args());
    result.push({success:true,meta:{changes:r.changes,last_row_id:Number(r.lastInsertRowid)},results:[]});
   }
   sqlite.exec("COMMIT");
   actions.push("D1_COMMIT_SUCCESS");
   return result;
  }catch(e){sqlite.exec("ROLLBACK");logError(e,"batch");throw e}
 },
 async exec(){throw Error("Schema/DDL through Worker not allowed in probe")}
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
  dbRows:Number(sqlite.prepare("SELECT COUNT(*) AS n FROM requests").get().n),
  savedStatus:sqlite.prepare("SELECT status FROM requests LIMIT 1").get()?.status||null,
  operationCounts:Object.fromEntries([...new Set(actions)].map(x=>[x,actions.filter(y=>x===y).length])),
  externalCalls:0,productionD1Writes:0,realOrders:0
 };
 console.log("LIVE_V05_ACTUAL_CREATE_REQUEST_OFFLINE_DIAGNOSIS");
 console.log(JSON.stringify(result,null,2));
 // A second *different* idempotency UUID on the same Kyiv day mimics
 // reopening the Mini App, while retaining the same signed synthetic user.
 // Must fail safely as daily quota rather than an opaque 503.
 if(r.status===201){
   const otherId='223e4567-e89b-42d3-a456-426614174000';
   const other=await worker.default.fetch(new Request(
     "https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/api/mini-app/order",
     {method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({...body,idempotencyKey:otherId})}
   ),{BOT_TOKEN:fakeToken,DB,SYNC_SECRET:"OFFLINE-NO-USE",WEBHOOK_SECRET:"OFFLINE"});
   const diag=await other.json();
   console.log("SAME_USER_NEW_UUID_STATUS="+String(other.status));
   console.log("SAME_USER_NEW_UUID_SAFE_CODE="+String(diag?.error_code||diag?.status||"OTHER"));
   console.log("SAME_USER_NEW_UUID_DB_ROWS="+String(sqlite.prepare("SELECT COUNT(*) AS n FROM requests").get().n));
 }
 if(r.status!==201&&r.status!==200){
   throw Error("Actual legacy createRequest pathway returns "+r.status+
   " in an isolated synthetic offline scenario");
 }
}catch(err){
 console.error("DIAGNOSIS_RESULT="+(err instanceof Error?err.message:"Unknown failure"));
 process.exitCode=1;
}finally{globalThis.fetch=originalFetch}
