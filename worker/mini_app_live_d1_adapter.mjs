/**
 * NGO Grants AI — direct-link Mini App durable order adapter (not deployed).
 *
 * Reuses the deployed bot's existing createRequest transaction, membership
 * and daily limits. No separate queue, tables or grant-search pipeline.
 * A browser-submitted Telegram ID is never trusted; upstream validates signed
 * Telegram initData. Does not send a bot DM, even when the user has no chat.
 *
 * CRITICAL INTEGRATION CONTRACT:
 *   legacy createRequest(env,chatId,userId,draft,updateId)
 *   legacy defaultDraft()
 *   legacy validatedDraft(draft)
 *   env.DB bound to the existing production D1 database.
 *
 * Actual live Worker integration remains DISABLED until the offline contract
 * and staged canary have verified every branch.
 */

const utf8=new TextEncoder();
const ID_BASE=2**51;             // Separate from normal Telegram update IDs.
const ID_SPACE=2**48;            // Exactly representable in JS and SQLite.
const CHANNEL="@ngo_grants";

export class DirectOrderRefusal extends Error {
  constructor(code){
    super("Direct Mini App order refused");
    this.code=code;
  }
}
const fail=code=>{throw new DirectOrderRefusal(code);};
const isInt=value=>Number.isSafeInteger(value)&&value>0;
const uuidPattern=/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;

export function kyivDate(now=new Date()){
  if(!(now instanceof Date)||!Number.isFinite(now.getTime()))fail("CONFIG");
  // Use the same local *calendar date* independent of runner/user timezone.
  // The legacy Worker currently applies calendar-day limits in Kyiv.
  const parts=new Intl.DateTimeFormat("en-CA",{
    timeZone:"Europe/Kyiv",year:"numeric",month:"2-digit",day:"2-digit"
  }).formatToParts(now);
  const get=key=>parts.find(p=>p.type===key)?.value;
  const date=[get("year"),get("month"),get("day")].join("-");
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date))fail("CONFIG");
  return date;
}

async function importKey(token){
  if(typeof token!=="string"||token.length<10)fail("CONFIG");
  return crypto.subtle.importKey("raw",utf8.encode(token),
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
}
export async function stableUpdateId({userId,day,facets,idempotencyKey,token}){
  if(!isInt(userId)||!/^\d{4}-\d{2}-\d{2}$/.test(day)||
     !uuidPattern.test(idempotencyKey)||!facets||
     typeof facets!=="object"||Array.isArray(facets))fail("CONFIG");
  const key=await importKey(token);
  const signed="ngo-grants-miniapp-v05\n"+String(userId)+"\n"+
    day+"\n"+idempotencyKey.toLowerCase()+"\n"+JSON.stringify(facets);
  const mac=new Uint8Array(await crypto.subtle.sign(
    "HMAC",key,utf8.encode(signed)));
  let value=0;
  for(let i=0;i<6;i++)value=value*256+mac[i];
  const id=ID_BASE+(value%ID_SPACE);
  if(!isInt(id))fail("CONFIG");
  return id;
}

/** Only verified Bot API membership counts; the browser cannot override it. */
export async function checkChannelMembership({userId,token,request=fetch}){
  if(!isInt(userId)||typeof request!=="function")fail("CONFIG");
  // No redirects, no client-controlled chat ID; Telegram Bot API only.
  let response;
  try{
    response=await request("https://api.telegram.org/bot"+
      token+"/getChatMember",{
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({chat_id:CHANNEL,user_id:userId}),
        redirect:"error"
      });
  }catch{fail("UPSTREAM_UNAVAILABLE");}
  if(!response||!response.ok)fail("UPSTREAM_UNAVAILABLE");
  let parsed;
  try{parsed=await response.json();}catch{fail("UPSTREAM_UNAVAILABLE");}
  if(!parsed?.ok||!parsed?.result||typeof parsed.result!=="object")
    fail("UPSTREAM_UNAVAILABLE");
  const member=parsed.result;
  if(member.user&&member.user.id!==userId)fail("UPSTREAM_UNAVAILABLE");
  if(["creator","administrator","member"].includes(member.status)||
     (member.status==="restricted"&&member.is_member===true))
    return true;
  if(["left","kicked"].includes(member.status)||
     (member.status==="restricted"&&member.is_member===false))
    fail("NOT_SUBSCRIBED");
  fail("UPSTREAM_UNAVAILABLE");
}

/** Select only the receipt metadata; never echo a request topic or user hash. */
async function lookupOrder(DB,updateId,day){
  if(!DB||typeof DB.prepare!=="function")fail("CONFIG");
  const row=await DB.prepare(
    "SELECT update_id, day, status FROM requests WHERE update_id = ? LIMIT 1"
  ).bind(updateId).first();
  if(row===null||row===undefined)return null;
  if(row.update_id!==updateId||row.day!==day)fail("CONFLICT");
  if(!["pending","processing","published","no_candidate","done","completed"].includes(row.status))
    fail("CONFLICT");
  return {orderId:updateId};
}

/**
 * Build a secure adapter for handleMiniAppOrder from its verified userId.
 * legacy createRequest may attempt Telegram sendMessage after committing D1;
 * the live Worker *must* support env.__miniAppHttpOrderMode to suppress all
 * such messages. Without this guard the adapter refuses to start.
 */
export function createExistingQueueAdapter({
  env,createRequest,defaultDraft,validatedDraft,
  request=fetch,now=()=>new Date()
}={}){
  if(!env||!env.DB||!env.BOT_TOKEN||
     typeof createRequest!=="function"||
     typeof defaultDraft!=="function"||
     typeof validatedDraft!=="function")fail("CONFIG");
  return async function enqueueExistingOrder({userId,facets,idempotencyKey}){
    if(!isInt(userId)||!uuidPattern.test(idempotencyKey))
      fail("CONFIG");
    if(env.__miniAppDirectSuppressDMAvailable!==true)
      fail("CONFIG"); // Never assume a bot DM will work for Main Mini App.
    const today=kyivDate(now());
    const updateId=await stableUpdateId({
      userId,day:today,facets,idempotencyKey,token:env.BOT_TOKEN
    });
    // Always verify signed user's CURRENT channel membership before returning
    // even an existing order. The existing Worker repeats its own check.
    await checkChannelMembership({userId,token:env.BOT_TOKEN,request});
    const found=await lookupOrder(env.DB,updateId,today);
    if(found)return {status:"existing",orderId:found.orderId};
    const draft={...defaultDraft(),...facets,stage:"confirm",at:Date.now()};
    if(!validatedDraft(draft))fail("CONFIG");
    // A per-request derived env is local; never mutate the global binding.
    const directEnv={...env,__miniAppHttpOrderMode:true};
    try{
      await createRequest(directEnv,userId,userId,draft,updateId);
    }catch(_){
      // A failed Telegram DM or a concurrency race is not proof that the D1
      // transaction failed. Confirm from durable D1 by deterministic ID.
    }
    const saved=await lookupOrder(env.DB,updateId,today);
    if(!saved)fail("DAILY_LIMIT"); // Includes daily/global limit and conflicts.
    return {status:"created",orderId:saved.orderId};
  };
}
