'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const direct=require('../direct-client.js');
const schema=require('../schema.js');
const uuid='123e4567-e89b-42d3-a456-426614174000';
const valid={
 audience:'nonprofit',sectors:['social','recovery'],custom_sector:'',
 geo:'ukraine',region:'',detail:'Соціальний транспорт',
 applicant_role:'lead',funding_format:'grant_only'
};
function response(status,body){return {status,json:async()=>body};}
const props={origin:'https://example.workers.dev',
  schema,webApp:{initData:'auth_date=1794140000&user=%7B%22id%22%3A123%7D&hash=server-validated'},
  randomUUID:()=>uuid};
test('direct submission is disabled until backend adapter and BotFather app are ready',async()=>{
 let calls=0;
 const controller=direct.createController({...props,post:async()=>{calls++;}});
 await assert.rejects(controller.submit(valid),/ще не активовано/);
 assert.equal(calls,0);
});
test('no Telegram initData means no backend write; initDataUnsafe is insufficient',async()=>{
 let calls=0;
 const c=direct.createController({...props,enabled:true,webApp:{initDataUnsafe:{user:{id:42}}},
   post:async()=>{calls++;return response(201,{ok:true,status:'created',order_id:1});}});
 await assert.rejects(c.submit(valid),/Потрібно відкрити/);
 assert.equal(calls,0);
});
test('client sends only signed initData and canonical facets, never unverified user_id',async()=>{
 const requests=[];
 const c=direct.createController({...props,enabled:true,post:async(url,options)=>{
   requests.push({url,options});
   return response(201,{ok:true,status:'created',order_id:3456});
 }});
 const receipt=await c.submit(valid);
 assert.deepEqual(receipt,{orderId:3456,status:'created'});
 assert.equal(requests.length,1);
 assert.equal(requests[0].url,props.origin+'/api/mini-app/order');
 assert.equal(requests[0].options.method,'POST');
 assert.equal(requests[0].options.credentials,'omit');
 const data=JSON.parse(requests[0].options.body);
 assert.deepEqual(Object.keys(data).sort(),['facets','idempotencyKey','initData']);
 assert.equal(data.idempotencyKey,uuid);
 assert.deepEqual(data.facets,schema.normalize(valid));
});
test('retry preserves UUID on 503 and creates new UUID only if facets change',async()=>{
 const keys=[];let tries=0;
 const c=direct.createController({...props,enabled:true,post:async(_url,options)=>{
   const data=JSON.parse(options.body);keys.push(data.idempotencyKey);
   tries++;
   if(tries===1)return response(503,{ok:false});
   return response(201,{ok:true,status:'created',order_id:88});
 }});
 await assert.rejects(c.submit(valid),/тимчасово недоступний/);
 assert.equal((await c.submit(valid)).orderId,88);
 assert.deepEqual(keys,[uuid,uuid]);
});
test('HTTP success without durable confirmed order ID cannot claim success',async()=>{
 for(const body of [{ok:true,status:'created'}, {ok:true,status:'created',order_id:-1},
                   {ok:false,status:'created',order_id:12}]){
   const c=direct.createController({...props,enabled:true,
     post:async()=>response(201,body)});
   await assert.rejects(c.submit(valid),/не підтвердив збереження/);
 }
});
test('server refusal messages use safe local copy, not untrusted HTML from response',async()=>{
 const c=direct.createController({...props,enabled:true,
    post:async()=>response(429,{ok:false,error:'<script>private token</script>'})});
 await assert.rejects(c.submit(valid),error=>{
   assert.match(error.message,/ліміт/);
   assert.doesNotMatch(error.message,/private|script/);
   return true;
 });
});
test('idempotent existing order receipt is accepted without duplicate success',async()=>{
 const c=direct.createController({...props,enabled:true,
    post:async()=>response(200,{ok:true,status:'existing',order_id:123})});
 assert.deepEqual(await c.submit(valid),{orderId:123,status:'existing'});
});
