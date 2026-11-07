/** Secure Telegram Mini App initData validator for Cloudflare Workers.
 * No routes or database writes. Import only in a future guarded integration.
 * Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
const encoder=new TextEncoder();

function fail(){
  // Never include raw Telegram initData, a bot token, or a user ID in logs.
  throw new Error("Telegram Mini App authentication failed");
}
async function hmacKey(bytes){
  return crypto.subtle.importKey("raw",bytes,{name:"HMAC",hash:"SHA-256"},false,["sign","verify"]);
}
export async function validateTelegramInitData(raw,botToken,{
  now=Math.floor(Date.now()/1000),maxAgeSeconds=3600
}={}){
  if(typeof raw!=="string"||raw.length===0||raw.length>8192||
     typeof botToken!=="string"||botToken.length<10)fail();
  if(!Number.isSafeInteger(now)||!Number.isSafeInteger(maxAgeSeconds)||
      maxAgeSeconds<60||maxAgeSeconds>86400)fail();
  const fields=new URLSearchParams(raw);
  const seen=new Set();
  for(const [k] of fields){
    if(!k||seen.has(k))fail();
    seen.add(k);
  }
  const hash=fields.get("hash");
  const authDateRaw=fields.get("auth_date");
  const userRaw=fields.get("user");
  if(!hash||!/^[0-9a-f]{64}$/i.test(hash)||
     !authDateRaw||!/^[0-9]{10,11}$/.test(authDateRaw)||!userRaw)fail();
  const date=Number(authDateRaw);
  if(!Number.isSafeInteger(date)||date>now+30||now-date>maxAgeSeconds)fail();

  // As Telegram specifies for the bot-token HMAC flow, exclude 'hash';
  // every other received key-value pair is part of the signed data string.
  const signed=[...fields].filter(([key])=>key!=="hash")
    .sort(([a],[b])=>a<b?-1:a>b?1:0)
    .map(([key,value])=>key+"="+value).join("\n");
  const secretKey=await hmacKey(encoder.encode("WebAppData"));
  const secret=new Uint8Array(await crypto.subtle.sign("HMAC",secretKey,encoder.encode(botToken)));
  const key=await hmacKey(secret);
  const bytes=Uint8Array.from(hash.match(/.{2}/g),part=>parseInt(part,16));
  // WebCrypto's HMAC verify handles constant-time MAC comparison.
  if(!await crypto.subtle.verify("HMAC",key,bytes,encoder.encode(signed)))fail();

  let user;
  try{user=JSON.parse(userRaw);}catch(_){fail();}
  if(!user||typeof user!=="object"||Array.isArray(user)||
     !Number.isSafeInteger(user.id)||user.id<=0||user.is_bot===true)fail();
  return Object.freeze({userId:user.id,authDate:date});
}
