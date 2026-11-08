/* NGO Grants AI — direct-link Mini App client transport (dormant, v0.1).
 *
 * NOT loaded in production Mini App. Do NOT enable without a real Worker
 * endpoint and queue adapter. No credentials, Telegram IDs or secrets stored.
 */
(function(root,factory){
  'use strict';
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.NgoGrantsDirectClient=api;
})(typeof globalThis==='object'?globalThis:null,function(){
 'use strict';
 const ENDPOINT='/api/mini-app/order';
 const ERRORS={
  400:'Перевірте параметри анкети.',
  401:'Не вдалося підтвердити Telegram-сеанс. Відкрийте застосунок повторно.',
  403:'Для замовлення потрібна підписка на @ngo_grants.',
  409:'Замовлення вже існує.',
  413:'Запит завеликий. Скоротіть уточнення.',
  415:'Непідтримуваний формат запиту.',
  429:'Денний ліміт замовлень вичерпано.',
  503:'Сервіс оформлення тимчасово недоступний.'
 };
 function jsonError(response){
   return new Error(ERRORS[response?.status]||'Не вдалося підтвердити замовлення.');
 }
 function verifyReceipt(response,body){
   if(!response||![200,201].includes(response.status)||
      !body||body.ok!==true||!Number.isSafeInteger(body.order_id)||
      body.order_id<=0||!['created','existing'].includes(body.status))
      throw new Error('Сервер не підтвердив збереження замовлення.');
   return Object.freeze({orderId:body.order_id,status:body.status});
 }
 function createController({enabled=false,webApp,schema,post,randomUUID,origin}={}){
   // Explicit opt-in; no REST calls from keyboard mode or offline previews.
   if(typeof post!=='function')throw new TypeError('post transport unavailable');
   if(typeof randomUUID!=='function')throw new TypeError('UUID transport unavailable');
   if(!schema||typeof schema.normalize!=='function')
      throw new TypeError('Canonical facet schema unavailable');
   if(!origin||!/^https:\/\//.test(origin))throw new TypeError('HTTPS origin required');
   let key=null,previousDraft=null,busy=false,receipt=null;
   function update(facets){
     const normalized=schema.normalize(facets);
     const serialized=JSON.stringify(normalized);
     if(serialized!==previousDraft){key=null;receipt=null;previousDraft=serialized;}
     return normalized;
   }
   async function submit(facets){
     if(!enabled)throw new Error('Пряме замовлення ще не активовано.');
     if(!webApp||typeof webApp.initData!=='string'||
       !webApp.initData.length||webApp.initData.length>8192)
       throw new Error('Потрібно відкрити застосунок із Telegram.');
     if(busy)throw new Error('Замовлення вже передається.');
     const normalized=update(facets);
     if(receipt)return receipt;
     if(!key){
       key=randomUUID();
       if(typeof key!=='string'||
          !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(key))
         throw new Error('Не вдалося створити ключ замовлення.');
     }
     busy=true;
     try{
       const response=await post(new URL(ENDPOINT,origin).href,{
         method:'POST',credentials:'omit',cache:'no-store',
         headers:{'content-type':'application/json'},
         body:JSON.stringify({
           initData:webApp.initData,
           facets:normalized,
           idempotencyKey:key
         })
       });
       if(!response||typeof response.json!=='function'||![200,201].includes(response.status))
         throw jsonError(response);
       let body;
       try{body=await response.json();}
       catch(_){throw new Error('Сервер повернув некоректну відповідь.');}
       receipt=verifyReceipt(response,body);
       return receipt;
     }catch(error){
       // Keep the same UUID for a retry. Do not claim order creation.
       if(error instanceof Error)throw error;
       throw new Error('Помилка мережі. Перевірте з’єднання та стан замовлення.');
     }finally{busy=false;}
   }
   return Object.freeze({
     submit,
     // reset is intended only after applicant explicitly changes a field.
     reset:()=>{key=null;receipt=null;previousDraft=null;},
     isEnabled:()=>enabled
   });
 }
 return Object.freeze({ENDPOINT,ERRORS,verifyReceipt,createController});
});
