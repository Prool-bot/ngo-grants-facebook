import test from "node:test";
import assert from "node:assert/strict";
import {createHmac,webcrypto} from "node:crypto";
import {
  normalizeMiniAppFacets,handleMiniAppOrder,ORDER_PATH
} from "../../worker/mini_app_order_endpoint.mjs";
if(!globalThis.crypto)globalThis.crypto=webcrypto;

const TOKEN="123456789:OFFLINE-SIGNATURE-TEST-ONLY";
const valid={
  audience:"nonprofit",sectors:["social","recovery"],custom_sector:"",
  geo:"region",region:"kharkiv",detail:"Соціальний транспорт",
  applicant_role:"lead",funding_format:"grant_only"
};
const ID="123e4567-e89b-42d3-a456-426614174000";
const NOW=Math.floor(Date.now()/1000);
function signedData(userId=12345678){
  const params=new URLSearchParams({
    auth_date:String(NOW),
    user:JSON.stringify({id:userId,first_name:"Test"})
  });
  const check=[...params].sort(([a],[b])=>a.localeCompare(b))
    .map(([key,value])=>key+"="+value).join("\n");
  const key=createHmac("sha256","WebAppData").update(TOKEN).digest();
  params.set("hash",createHmac("sha256",key).update(check).digest("hex"));
  return params.toString();
}
function req(body,method="POST",ct="application/json"){
 return new Request("https://staging.example/api/mini-app/order",{
   method,headers:{"content-type":ct},
   body:method==="POST"?JSON.stringify(body):undefined
 });
}
function payload(overrides={}) {
 return {initData:signedData(),facets:{...valid},idempotencyKey:ID,...overrides};
}
const enabled={BOT_TOKEN:TOKEN,MINI_APP_ORDER_ENABLED:"true"};
const good=()=>({enqueueExistingOrder:async()=>({status:"created",orderId:65})});

test("normalize facets matches the production menu payload and preserves alternatives",()=>{
 assert.equal(ORDER_PATH,"/api/mini-app/order");
 assert.deepEqual(normalizeMiniAppFacets(valid),valid);
 assert.deepEqual(normalizeMiniAppFacets({...valid,sectors:["social","social","recovery"]}).sectors,["social","recovery"]);
 assert.deepEqual(normalizeMiniAppFacets({...valid,sectors:["social","all"],custom_sector:"Дослідження"}).sectors,["all"]);
});
test("rejects unknown fields, invalid regions, malicious contact and incorrect type",()=>{
 const patches=[
  {user_id:42},{audience:"evil"},{geo:"region",region:"fake"},
  {geo:"ukraine",region:"kharkiv"},{sectors:["unknown"]},{sectors:[]},
  {detail:"https://example.com"},{detail:1},{custom_sector:"@private"},
  {applicant_role:"owner"},{funding_format:"coin"}
 ];
 for(const patch of patches){
   assert.throws(()=>normalizeMiniAppFacets({...valid,...patch}));
 }
});
test("no queues ever called when disabled, unsigned or missing existing queue adapter",async()=>{
 let calls=0;
 const spy={enqueueExistingOrder:async()=>{calls++;return {status:"created",orderId:1};}};
 assert.equal((await handleMiniAppOrder(req(payload()),{BOT_TOKEN:TOKEN,MINI_APP_ORDER_ENABLED:"false"},spy)).status,503);
 assert.equal((await handleMiniAppOrder(req(payload()),enabled,{})).status,503);
 assert.equal((await handleMiniAppOrder(req(payload({initData:"fake"})),enabled,spy)).status,401);
 assert.equal(calls,0);
});
test("malformed facets and cross-origin submissions are refused before enqueue",async()=>{
 let calls=0;
 const deps={enqueueExistingOrder:async()=>{calls++;return {status:"created",orderId:1};}};
 const bad=await handleMiniAppOrder(req(payload({facets:{...valid,geo:"other"}})),enabled,deps);
 assert.equal(bad.status,400);
 const cross=req(payload());
 cross.headers.set("origin","https://evil.example");
 assert.equal((await handleMiniAppOrder(cross,enabled,deps)).status,403);
 assert.equal(calls,0);
});
test("only server-verified Telegram identity reaches existing queue callback",async()=>{
 const calls=[];
 const deps={enqueueExistingOrder:async value=>{
   calls.push(value);return {status:"created",orderId:123};
 }};
 const response=await handleMiniAppOrder(req(payload()),enabled,deps);
 assert.equal(response.status,201);
 assert.deepEqual(await response.json(),{ok:true,order_id:123,status:"created"});
 assert.deepEqual(calls,[{userId:12345678,facets:valid,idempotencyKey:ID}]);
});
test("same idempotency key returning existing queue record is not a duplicate",async()=>{
 const response=await handleMiniAppOrder(req(payload()),enabled,{
   enqueueExistingOrder:async()=>({status:"existing",orderId:123})
 });
 assert.equal(response.status,200);
 assert.equal((await response.json()).order_id,123);
});
test("never claims success unless durable existing-queue adapter confirms ID",async()=>{
 for(const response of [null,{}, {status:"created"}, {status:"created",orderId:-1}]){
   const result=await handleMiniAppOrder(req(payload()),enabled,{
     enqueueExistingOrder:async()=>response
   });
   assert.equal(result.status,503);
   assert.equal((await result.json()).ok,false);
 }
});
test("preserves live server denials, without exposing sensitive stack or token",async()=>{
 for(const [code,status] of [
   ["NOT_SUBSCRIBED",403],["DAILY_LIMIT",429],["CONFLICT",409]
 ]){
  const response=await handleMiniAppOrder(req(payload()),enabled,{
   enqueueExistingOrder:async()=>{const e=Error("PRIVATE:"+TOKEN);e.code=code;throw e;}
  });
  assert.equal(response.status,status);
  assert.doesNotMatch(await response.text(),/PRIVATE|OFFLINE-SIGNATURE/);
 }
});
test("rejects oversized payload and unsupported methods before enqueue",async()=>{
 const response=await handleMiniAppOrder(req(payload(),"GET"),enabled,good());
 assert.equal(response.status,405);
 const huge=req(payload({extra:"X".repeat(20000)}));
 assert.equal((await handleMiniAppOrder(huge,enabled,good())).status,413);
 assert.equal((await handleMiniAppOrder(req(payload(),"POST","text/plain"),enabled,good())).status,415);
});
test("rejects request body fields attempting client identity spoofing",async()=>{
 for(const spoof of [{userId:42},{chat_id:42},{id:11}]){
  const result=await handleMiniAppOrder(req(payload(spoof)),enabled,good());
  assert.equal(result.status,400);
 }
});
