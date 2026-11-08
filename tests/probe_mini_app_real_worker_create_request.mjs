/* Read-only actual Worker createRequest contract probe.
 * No D1 credentials. Real D1 object NEVER passed in. All Telegram network
 * calls are blocked; only fake API responses are returned in memory.
 * Do not print Worker JS source, SQL statements, user parameters or stack.
 */
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';

const filename=process.argv[2];
if(!filename)throw Error('Expected private Worker JS path from runner');
let original=readFileSync(filename,'utf8');
if(!/NGO_MINI_APP_FOP_STATUS_HINT_V04/.test(original)) throw Error('Expected approved Worker marker');
assert.match(original,/menu_version:'5\.8'/);
const tell=/async function tell\(env,chatId,text,markup=null,editId=null\)\{[\s\S]*?\n\}/;
assert.equal((original.match(tell)||[]).length,1,'Expected exactly one Telegram message helper');
original=original.replace(tell,
 'async function tell(env,chatId,text,markup=null,editId=null){'+
 'env.__fakeMessages.push({kind:"message"});return {message_id:313};}');
original+='\nexport {createRequest,defaultDraft,validatedDraft};\n';

const trace=[];
function queryClass(sql){
 if(typeof sql!=='string')return 'not-string';
 const upper=sql.trim().replace(/\s+/g,' ').toUpperCase();
 const verb=(upper.match(/\b(SELECT|INSERT|UPDATE|DELETE|CREATE|REPLACE)\b/)||[])[1]||'OTHER';
 const table=(upper.match(/\b(?:INTO|FROM|UPDATE)\s+([A-Z_][A-Z_0-9]*)/)||[])[1]||'UNKNOWN';
 const allowed=new Set(['REQUESTS','LEGACY_LIMITS','SETTINGS','CATALOGS','USERS','DRAFTS','UNKNOWN']);
 return verb+'_'+(allowed.has(table)?table:'OTHER_TABLE');
}
function statement(sql){
 const key=queryClass(sql);
 const entry={key,params:0};
 trace.push(entry);
 const query={
  bind(...args){entry.params=args.length;return query;},
  first:async()=>{trace.push({key:key+'_FIRST'});return null;},
  all:async()=>({success:true,results:[]}),
  run:async()=>{trace.push({key:key+'_RUN'});return {success:true,meta:{changes:1,last_row_id:77}}}
 };
 return query;
}
const fakeDb={
 prepare:sql=>statement(sql),
 batch:async items=>{
  trace.push({key:'D1_BATCH',count:items?.length||0});
  return (items||[]).map((_,index)=>({
     success:true,meta:{changes:1,last_row_id:77+index},results:[]
  }));
 },
 exec:async()=>{trace.push({key:'D1_EXEC_BLOCKED'});throw Error('D1 exec disabled in offline probe');}
};
const originalFetch=globalThis.fetch;
const fetchTrace=[];
globalThis.fetch=async(url,opts)=>{
 const address=String(url);
 if(!/^https:\/\/api\.telegram\.org\/botFAKE_CONTRACT_TOKEN\//.test(address))
   throw Error('External network blocked in offline contract probe');
 const action=(address.match(/\/(getChatMember|sendMessage|editMessageText|getMe)$/)||[])[1]||'unknown';
 fetchTrace.push(action);
 const response=action==='getChatMember'
  ? {ok:true,result:{status:'member',user:{id:1234}}}
  : {ok:true,result:{message_id:313,chat:{id:1234,type:'private'}}};
 return new Response(JSON.stringify(response),{status:200,
   headers:{'content-type':'application/json'}});
};
let module;
try{
 module=await import('data:text/javascript;base64,'+Buffer.from(original).toString('base64'));
}catch(_){
 throw Error('Private Worker import could not complete (source not logged)');
}
try{
 const draft=module.defaultDraft();
 Object.assign(draft,{
  audience:'nonprofit',sectors:['social'],geo:'ukraine',region:'',
  detail:'Підтримка соціальних послуг',applicant_role:'lead',
  funding_format:'grant_only',stage:'confirm'
 });
 assert.equal(module.validatedDraft(draft),true);
 const environment={
  BOT_TOKEN:'FAKE_CONTRACT_TOKEN',SYNC_SECRET:'FAKE_SYNC',
  DB:fakeDb,__fakeMessages:[]
 };
 let outcome='completed',returned=null;
 try{returned=await module.createRequest(environment,1234,1234,draft,998877);}
 catch(_){outcome='exception_sanitized';}
 const classOfReturn=returned===undefined?'undefined':returned===null?'null':
   typeof returned==='object'?'object':typeof returned;
 const keys=returned && typeof returned==='object' ?
   Object.keys(returned).filter(k=>['id','orderId','status','ok','accepted','error','success'].includes(k)):[];
 const counts={};
 for(const event of trace)counts[event.key]=(counts[event.key]||0)+1;
 const printResult={
  outcome,return_type:classOfReturn,return_safe_keys:keys,
  sql_operation_counts:counts,telegram_method_counts:Object.fromEntries(
    [...new Set(fetchTrace)].map(k=>[k,fetchTrace.filter(a=>a===k).length])),
  local_message_count:environment.__fakeMessages.length,
  attempted_real_network_calls:0,real_d1_writes:0,real_orders:0
 };
 console.log('LIVE_WORKER_CREATE_REQUEST_SAFE_MOCK_SUMMARY');
 console.log(JSON.stringify(printResult,null,2));
 if(!counts.D1_BATCH && !Object.keys(counts).some(k=>k.includes('REQUESTS_RUN')))
   throw Error('Offline createRequest did not reach existing queue transaction');
}finally{globalThis.fetch=originalFetch;}
