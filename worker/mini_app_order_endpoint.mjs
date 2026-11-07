/**
 * NGO Grants Mini App — guarded order endpoint for Cloudflare Worker.
 *
 * This is deliberately NOT registered in the production Worker yet.
 * The queue adapter MUST call the current production queue transaction,
 * with the same channel membership, Kyiv-day quota and idempotency rules.
 * It must not accept a client-provided user ID.
 */
import {validateTelegramInitData} from "./mini_app_verify_init_data.mjs";

export const ORDER_PATH="/api/mini-app/order";

export function normalizeMiniAppFacets(input) {
  if (!input || typeof input!=="object" || Array.isArray(input))
    throw new Error("Некоректна анкета");
  const keys=new Set([
    "audience","sectors","geo","region","custom_sector","detail",
    "applicant_role","funding_format"
  ]);
  if(Object.keys(input).some(k=>!keys.has(k)))
    throw new Error("Неприпустимі поля");
  const allowedAudiences=new Set(["nonprofit","commercial","individual","municipal","institution","all"]);
  const allowedGeos=new Set(["ukraine","region","international","all"]);
  const allowedSectors=new Set([
    "education","medical","culture","environment","it","social","recovery",
    "agriculture","media","rights","business","all"
  ]);
  const allowedRegions=new Set([
    "vinnytsia","volyn","dnipro","donetsk","zhytomyr","zakarpattia",
    "zaporizhzhia","ivano","kyiv_obl","kirovohrad","luhansk","lviv",
    "mykolaiv","odesa","poltava","rivne","sumy","ternopil","kharkiv",
    "kherson","khmelnytskyi","cherkasy","chernivtsi","chernihiv",
    "kyiv_city","crimea"
  ]);
  if(!allowedAudiences.has(input.audience))throw new Error("Оберіть тип заявника");
  if(!allowedGeos.has(input.geo))throw new Error("Оберіть географію");
  if(!Array.isArray(input.sectors)||input.sectors.length>12||
     input.sectors.some(s=>typeof s!=="string"||!allowedSectors.has(s)))
    throw new Error("Некоректні напрями");
  let sectors=[...new Set(input.sectors)];
  if(sectors.includes("all"))sectors=["all"];
  for(const key of ["custom_sector","detail"]){
    if(input[key]!==undefined && typeof input[key]!=="string")
      throw new Error("Некоректне текстове поле");
  }
  const clean=(value,max)=>{
    const raw=value||"";
    const text=raw.trim().replace(/\s+/g," ");
    if(text.length>max)throw new Error("Завеликий текст запиту");
    if(/https?:\/\/|(?:^|\s)@[\w]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}/i.test(text))
      throw new Error("Не додавайте контактних даних");
    return text;
  };
  const custom=sectors.includes("all")?"":clean(input.custom_sector,60);
  if(!sectors.length&&!custom)throw new Error("Оберіть тематичний напрям");
  if(input.geo==="region"&&!allowedRegions.has(input.region))
    throw new Error("Оберіть область");
  if(input.geo!=="region"&&input.region && input.region!=="")
    throw new Error("Регіон не відповідає географії");
  const role=input.applicant_role===undefined?"lead":input.applicant_role;
  const format=input.funding_format===undefined?"any":input.funding_format;
  if(!["lead","partner","either"].includes(role)||
     !["grant_only","any"].includes(format))
    throw new Error("Некоректна роль або форма підтримки");
  return {
    audience:input.audience,sectors,custom_sector:custom,
    geo:input.geo,region:input.geo==="region"?input.region:"",
    detail:clean(input.detail,180),
    applicant_role:role,funding_format:format
  };
}

function json(status,obj,extraHeaders={}){
  return new Response(JSON.stringify(obj),{
    status,headers:{"content-type":"application/json; charset=utf-8",
      "cache-control":"no-store","x-content-type-options":"nosniff",
      ...extraHeaders}
  });
}

/**
 * `deps.enqueueExistingOrder` MUST be a real, atomic, durable adapter of
 * the live Worker workflow. It must validate membership and daily quota.
 * Signature: ({userId,facets,idempotencyKey}) =>
 *  {status:"created"|"existing",orderId:number}
 * This function never creates local/fake orders.
 */
export async function handleMiniAppOrder(request,env,deps={}){
  if(request.method!=="POST")return json(405,{ok:false,error:"Method not allowed"},{allow:"POST"});
  if(!env || typeof env.BOT_TOKEN!=="string" || !env.BOT_TOKEN)
    return json(503,{ok:false,error:"Тимчасово недоступно"});
  if(env.MINI_APP_ORDER_ENABLED!=="true")
    return json(503,{ok:false,error:"Замовлення через Mini App ще не ввімкнені"});
  if(typeof deps.enqueueExistingOrder!=="function")
    return json(503,{ok:false,error:"Серверна черга не підключена"});
  const ct=request.headers.get("content-type")||"";
  if(!/^application\/json(?:\s*;|\s*$)/i.test(ct))
    return json(415,{ok:false,error:"Очікується JSON"});
  const size=Number(request.headers.get("content-length")||"0");
  if(size>16384)return json(413,{ok:false,error:"Запит завеликий"});
  let data;
  try{
    const raw=await request.text();
    if(raw.length>16384)throw Error("size");
    data=JSON.parse(raw);
  }catch{
    return json(400,{ok:false,error:"Некоректний JSON"});
  }
  if(!data||typeof data!=="object"||Array.isArray(data)||
     Object.keys(data).some(key=>!["initData","facets","idempotencyKey"].includes(key)))
    return json(400,{ok:false,error:"Некоректні поля"});
  if(typeof data.idempotencyKey!=="string" ||
     !/^[a-f0-9]{8}-[a-f0-9]{4}-[4][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(data.idempotencyKey))
    return json(400,{ok:false,error:"Некоректний ключ підтвердження"});

  let identity,facets;
  try{
    identity=await validateTelegramInitData(data.initData,env.BOT_TOKEN,{
      maxAgeSeconds:3600});
    facets=normalizeMiniAppFacets(data.facets);
  }catch{
    return json(401,{ok:false,error:"Не вдалося перевірити дані Telegram або анкету"});
  }
  try{
    // No partial success, no queue acknowledgement before confirmed commit.
    const result=await deps.enqueueExistingOrder({
      userId:identity.userId,facets,idempotencyKey:data.idempotencyKey});
    if(!result || !["created","existing"].includes(result.status) ||
       !Number.isSafeInteger(result.orderId)||result.orderId<=0)
      throw Error("Queue adapter did not confirm commit");
    return json(result.status==="created"?201:200,{
      ok:true,order_id:result.orderId,status:result.status
    });
  }catch(err){
    // The actual queue adapter must return explicit safe refusal codes.
    const code=err && err.code;
    if(code==="NOT_SUBSCRIBED")
      return json(403,{ok:false,error:"Спочатку підпишіться на канал"});
    if(code==="DAILY_LIMIT")
      return json(429,{ok:false,error:"На сьогодні ліміт запитів вичерпано"});
    if(code==="CONFLICT")
      return json(409,{ok:false,error:"Замовлення вже існує"});
    return json(503,{ok:false,error:"Не вдалося підтвердити замовлення. Спробуйте перевірити стан черги у боті."});
  }
}
