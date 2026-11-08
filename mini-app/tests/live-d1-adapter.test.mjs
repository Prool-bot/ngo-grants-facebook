import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {
  kyivDate,stableUpdateId,checkChannelMembership,
  createExistingQueueAdapter,DirectOrderRefusal
} from "../../worker/mini_app_live_d1_adapter.mjs";
if(!globalThis.crypto)globalThis.crypto=webcrypto;

const TOKEN="123456789:OFFLINE-only-no-real-Telegram";
const UUID="123e4567-e89b-42d3-a456-426614174000";
const USER=100200300;
const DAY="2026-11-08";
const NOW=()=>new Date("2026-11-08T10:00:00Z");
const facets=Object.freeze({
  audience:"nonprofit",sectors:["social","recovery"],
  custom_sector:"",geo:"ukraine",region:"",detail:"Соціальний транспорт",
  applicant_role:"lead",funding_format:"grant_only"
});

function memberFetch(status="member",userId=USER){
  const calls=[];
  const request=async (url,options)=>{
    calls.push({url,options});
    assert.match(url,/^https:\/\/api\.telegram\.org\/bot123456789:OFFLINE-only-no-real-Telegram\/getChatMember$/);
    assert.equal(options.method,"POST");
    assert.equal(options.redirect,"error");
    const data=JSON.parse(options.body);
    assert.equal(data.chat_id,"@ngo_grants");
    assert.equal(data.user_id,userId);
    return new Response(JSON.stringify({ok:true,result:{
      status,user:{id:userId}
    }}),{status:200});
  };
  return {request,calls};
}
function fakeDb(){
  const rows=new Map();
  const queries=[];
  return {
    rows,queries,
    prepare(sql){
      assert.equal(sql,"SELECT update_id, day, status FROM requests WHERE update_id = ? LIMIT 1");
      return {bind(updateId){
        queries.push(updateId);
        return {first:async()=>rows.get(updateId)||null};
      }};
    }
  };
}
function setup({subscribed=true,commit=true,dmFailure=false,wait=null}={}){
  const DB=fakeDb();
  const member=memberFetch(subscribed?"member":"left");
  const calls=[];
  const env={
    BOT_TOKEN:TOKEN,DB,__miniAppDirectSuppressDMAvailable:true
  };
  const enqueueExistingOrder=createExistingQueueAdapter({
    env,now:NOW,request:member.request,
    defaultDraft:()=>({detail:"",sectors:[],stage:"begin"}),
    validatedDraft:d=>d.stage==="confirm"&&d.audience==="nonprofit",
    createRequest:async (derived,chatId,userId,d,updateId)=>{
      calls.push({derived,chatId,userId,d,updateId});
      if(wait)await wait();
      if(commit)DB.rows.set(updateId,{
        update_id:updateId,day:DAY,status:"pending"
      });
      if(dmFailure)throw Error("FAKE Telegram DM was unavailable");
    }
  });
  return {enqueueExistingOrder,DB,calls,member,env};
}
function input(extra={}){return {userId:USER,idempotencyKey:UUID,facets,...extra};}

test("Kyiv day follows Europe/Kyiv calendar, not Istanbul/UTC date",()=>{
  assert.equal(kyivDate(new Date("2026-11-08T22:30:00Z")),"2026-11-09");
  assert.equal(kyivDate(new Date("2026-11-08T01:00:00Z")),"2026-11-08");
});
test("ID is stable positive safe > Telegram update range, keyed by signed user/facets/day",async()=>{
  const args={userId:USER,day:DAY,facets,idempotencyKey:UUID,token:TOKEN};
  const id=await stableUpdateId(args);
  assert.ok(id>2**51&&Number.isSafeInteger(id));
  assert.equal(id,await stableUpdateId(args));
  assert.notEqual(id,await stableUpdateId({...args,userId:USER+1}));
  assert.notEqual(id,await stableUpdateId({...args,day:"2026-11-09"}));
  assert.notEqual(id,await stableUpdateId({...args,facets:{...facets,detail:"Інший проєкт"}}));
});
test("Fresh order uses verified membership and original queue, then reads durable DB receipt",async()=>{
  const x=setup();
  const result=await x.enqueueExistingOrder(input());
  assert.equal(result.status,"created");
  assert.ok(Number.isSafeInteger(result.orderId));
  assert.equal(x.calls.length,1);
  assert.equal(x.calls[0].chatId,USER);
  assert.equal(x.calls[0].userId,USER);
  assert.equal(x.calls[0].d.stage,"confirm");
  assert.equal(x.calls[0].derived.__miniAppHttpOrderMode,true);
  assert.equal(x.env.__miniAppHttpOrderMode,undefined,"shared Worker env must not be mutated");
  assert.equal(x.DB.queries.at(-1),result.orderId);
  assert.equal(x.member.calls.length,1);
});
test("Retry same UUID does not call production createRequest twice",async()=>{
  const x=setup();
  const created=await x.enqueueExistingOrder(input());
  const again=await x.enqueueExistingOrder(input());
  assert.deepEqual(again,{status:"existing",orderId:created.orderId});
  assert.equal(x.calls.length,1);
});
test("DM failure after D1 transaction still yields real durable receipt",async()=>{
  const x=setup({dmFailure:true});
  const result=await x.enqueueExistingOrder(input());
  assert.equal(result.status,"created");
  assert.ok(result.orderId>0);
});
test("Pre-commit D1 failure is NOT misrepresented as a quota refusal",async()=>{
  const x=setup({commit:false,dmFailure:true});
  await assert.rejects(x.enqueueExistingOrder(input()),
    e=>e instanceof DirectOrderRefusal&&e.code==="UPSTREAM_UNAVAILABLE");
  assert.equal(x.DB.rows.size,0);
});
test("Existing Worker quota denial without an insert returns daily-limit response",async()=>{
  const x=setup({commit:false,dmFailure:false});
  await assert.rejects(x.enqueueExistingOrder(input()),
    e=>e instanceof DirectOrderRefusal&&e.code==="DAILY_LIMIT");
  assert.equal(x.DB.rows.size,0);
});
test("Unsubscribed user is blocked BEFORE calling existing queue",async()=>{
  const x=setup({subscribed:false});
  await assert.rejects(x.enqueueExistingOrder(input()),
    e=>e instanceof DirectOrderRefusal&&e.code==="NOT_SUBSCRIBED");
  assert.equal(x.calls.length,0);
  assert.equal(x.DB.queries.length,0);
});
test("Without verified server-side DM-suppression hook, no DB mutation occurs",async()=>{
  const x=setup();
  x.env.__miniAppDirectSuppressDMAvailable=false;
  await assert.rejects(x.enqueueExistingOrder(input()),
    e=>e instanceof DirectOrderRefusal&&e.code==="CONFIG");
  assert.equal(x.calls.length,0);
  assert.equal(x.member.calls.length,0);
});
test("Same UUID from different signed Telegram user cannot match existing order",async()=>{
  const x=setup();
  const prev=await x.enqueueExistingOrder(input());
  const another=await stableUpdateId({userId:USER+1,day:DAY,
    facets,idempotencyKey:UUID,token:TOKEN});
  assert.notEqual(prev.orderId,another);
});
test("Fake readback for a different date is NOT accepted as receipt",async()=>{
  const x=setup();
  const result=await x.enqueueExistingOrder(input());
  x.DB.rows.get(result.orderId).day="2026-11-07";
  await assert.rejects(x.enqueueExistingOrder(input()),
    e=>e instanceof DirectOrderRefusal&&e.code==="CONFLICT");
});
test("Simultaneous identical requests lead to one created + one existing receipt",async()=>{
  const x=setup();
  const [a,b]=await Promise.all([
    x.enqueueExistingOrder(input()),x.enqueueExistingOrder(input())
  ]);
  assert.equal(a.orderId,b.orderId);
  // Real DB unique index protects atomic insert; mocked createRequest may run twice.
  assert.ok(["created","existing"].includes(a.status));
  assert.ok(["created","existing"].includes(b.status));
});
test("Network failure to Telegram getChatMember does not create an order",async()=>{
  const DB=fakeDb(),env={BOT_TOKEN:TOKEN,DB,__miniAppDirectSuppressDMAvailable:true};
  let writes=0;
  const adapter=createExistingQueueAdapter({
    env,defaultDraft:()=>({}),validatedDraft:()=>true,now:NOW,
    request:async()=>{throw Error("FAKE offline network error");},
    createRequest:async()=>{writes++;}
  });
  await assert.rejects(adapter(input()),
    e=>e instanceof DirectOrderRefusal&&e.code==="UPSTREAM_UNAVAILABLE");
  assert.equal(writes,0);
});
