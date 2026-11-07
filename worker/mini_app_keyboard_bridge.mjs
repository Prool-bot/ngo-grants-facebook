/**
 * Native Telegram keyboard Mini App transport.
 *
 * The Telegram client sends web_app_data as an authenticated bot update.
 * This is simpler than a second browser->D1 order API and keeps all membership,
 * daily quota, deduplication and order confirmation in existing createRequest().
 *
 * This module is not in the deployed Worker until a separately tested patch.
 */
export const MINI_APP_MARKER="ngo-grants-miniapp-v1";
export const MINI_APP_PATH="/mini-app";

const CHOICES={
  audience:new Set(["nonprofit","commercial","individual","municipal","institution","all"]),
  sector:new Set(["education","medical","culture","environment","it","social",
    "recovery","agriculture","media","rights","business","all"]),
  geo:new Set(["ukraine","region","international","all"]),
  region:new Set(["vinnytsia","volyn","dnipro","donetsk","zhytomyr","zakarpattia",
    "zaporizhzhia","ivano","kyiv_obl","kirovohrad","luhansk","lviv","mykolaiv",
    "odesa","poltava","rivne","sumy","ternopil","kharkiv","kherson","khmelnytskyi",
    "cherkasy","chernivtsi","chernihiv","kyiv_city","crimea"]),
  role:new Set(["lead","partner","either"]),
  funding:new Set(["grant_only","any"]),
};
const KEYS=new Set(["audience","sectors","custom_sector","geo","region",
 "detail","applicant_role","funding_format"]);

function validateString(value,max){
  if(typeof value!=="string"||value.length>max)throw Error("invalid text");
  const normalized=value.trim().replace(/\s+/g," ");
  if(/https?:\/\/|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:^|\s)@[a-z\d_]{4,}/i.test(normalized))
    throw Error("personal contact/URL");
  return normalized;
}
export function validateKeyboardFacets(f) {
  if(!f||typeof f!=="object"||Array.isArray(f) ||
      Object.keys(f).some(k=>!KEYS.has(k)))throw Error("unknown fields");
  if(!CHOICES.audience.has(f.audience)||!CHOICES.geo.has(f.geo))throw Error("invalid audience/geo");
  if(!Array.isArray(f.sectors)||f.sectors.length>12||
      f.sectors.some(x=>!CHOICES.sector.has(x)))throw Error("invalid sectors");
  let sectors=[...new Set(f.sectors)];
  if(sectors.includes("all"))sectors=["all"];
  const custom=sectors.includes("all")?"":validateString(f.custom_sector??"",60);
  if(!sectors.length&&!custom)throw Error("no sectors");
  if(f.geo==="region"&&!CHOICES.region.has(f.region))throw Error("invalid region");
  if(f.geo!=="region"&&f.region)throw Error("unexpected region");
  const role=f.applicant_role??"lead";
  const funding=f.funding_format??"any";
  if(!CHOICES.role.has(role)||!CHOICES.funding.has(funding))throw Error("role/funding");
  return {
    audience:f.audience,sectors,custom_sector:custom,geo:f.geo,
    region:f.geo==="region"?f.region:"",
    detail:validateString(f.detail??"",180),
    applicant_role:role,funding_format:funding,
  };
}

/** Strictly trust Telegram webhook update, never an arbitrary POST body. */
export function parseMiniAppServiceMessage(update){
  const message=update?.message;
  if(!message?.web_app_data)return null;
  if(!Number.isSafeInteger(update.update_id)||update.update_id<0||
      message.chat?.type!=="private"||
      !Number.isSafeInteger(message.chat?.id)||message.chat.id<=0||
      message.from?.id!==message.chat.id ||
      typeof message.web_app_data.data!=="string"||
      message.web_app_data.data.length>4096)
    throw Error("Invalid Telegram web_app_data context");
  let payload;
  try{payload=JSON.parse(message.web_app_data.data);}catch{throw Error("Invalid Mini App JSON");}
  if(!payload||typeof payload!=="object"||Array.isArray(payload)||
     payload.type!==MINI_APP_MARKER ||
     Object.keys(payload).some(k=>!["type","facets"].includes(k)))
    throw Error("Invalid Mini App schema");
  const facets=validateKeyboardFacets(payload.facets);
  return {userId:message.from.id,chatId:message.chat.id,
          updateId:update.update_id,facets};
}

export function miniAppKeyboard(baseUrl){
  const url=new URL(MINI_APP_PATH,new URL(baseUrl).origin);
  if(url.protocol!=="https:")throw Error("HTTPS required");
  return {
    keyboard:[
      [{text:"🤖 Відкрити грантового помічника",web_app:{url:url.href}}],
      [{text:"/start"}]
    ],
    resize_keyboard:true,
    is_persistent:true
  };
}

/** Build the exact existing draft shape, not another search service. */
export function miniAppDraft(facets,createDefaultDraft){
  if(typeof createDefaultDraft!=="function")throw Error("Missing live draft factory");
  const validated=validateKeyboardFacets(facets);
  const draft=createDefaultDraft();
  if(!draft||typeof draft!=="object")throw Error("Invalid live draft factory");
  return {...draft,...validated,stage:"confirm",at:Date.now()};
}

/** Reuse existing createRequest(env, chat, userId, draft, updateId). */
export async function processMiniAppUpdate(update,env,deps){
  const parsed=parseMiniAppServiceMessage(update);
  if(!parsed)return null;
  if(!deps||typeof deps.defaultDraft!=="function"||
      typeof deps.validatedDraft!=="function"||
      typeof deps.createRequest!=="function")
    throw Error("Missing production queue adapter");
  const draft=miniAppDraft(parsed.facets,deps.defaultDraft);
  if(!deps.validatedDraft(draft))throw Error("Rejected by live bot schema");
  return await deps.createRequest(env,parsed.chatId,parsed.userId,draft,parsed.updateId);
}
