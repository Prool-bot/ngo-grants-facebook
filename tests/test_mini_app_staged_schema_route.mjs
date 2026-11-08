import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const filename=process.argv[2];
if(!filename)throw Error('Worker candidate path required');
const text=readFileSync(filename,'utf-8');
if(!text.includes("NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01"))throw Error('Missing staged schema route');
let worker;
try{worker=await import("data:text/javascript;base64,"+
 Buffer.from(text).toString("base64"));}
catch(_){throw Error('Private Worker module import failed (source suppressed)');}
const endpoint='https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/_internal/miniapp/d1-schema-audit';
let dbReads=0;
const DB={
 prepare(sql){
   if(!/^PRAGMA (table_info|index_list)\((requests|legacy_limits|settings|catalogs)\)$/.test(sql))
      throw Error('Unsafe SQL in supposed read-only schema endpoint');
   dbReads++;
   if(sql.includes('table_info')){
     return {all:async()=>({success:true,results:[{
       name:'id',type:'INTEGER',pk:1,notnull:1
     }]})};
   }
   return {all:async()=>({success:true,results:[{unique:1}]})};
 }
};
const environment={SYNC_SECRET:'FAKE_OFFLINE_SECRET',DB};
const unauthorized=await worker.default.fetch(new Request(endpoint),environment);
assert.equal(unauthorized.status,403);
assert.equal(dbReads,0);
const notAllowed=await worker.default.fetch(new Request(endpoint,{method:'POST'}),environment);
assert.equal(notAllowed.status,405);
assert.equal(dbReads,0);
const authorized=await worker.default.fetch(new Request(endpoint,{
 method:'GET',headers:{Authorization:'Bearer FAKE_OFFLINE_SECRET'}
}),environment);
assert.equal(authorized.status,200);
assert.equal(authorized.headers.get('X-Miniapp-Schema-Stage'),'1');
assert.equal(dbReads,8,'4 tables x 2 read-only PRAGMAs');
const payload=await authorized.json();
assert.equal(payload.ok,true);
assert.equal(payload.schema.requests.columns[0].name,'id');
assert.equal(payload.schema.requests.unique_indexes,1);
const url='https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/health';
const legacy=await worker.default.fetch(new Request(url),environment);
assert.notEqual(legacy.status,403);
console.log('STAGED_WORKER_PRAGMA_SCHEMA_READ_ONLY_MOCK_PASS');
console.log('UNAUTHORIZED_D1_READS=0;AUTHORIZED_PRAGMA_READS=8;REAL_D1_WRITES=0');
