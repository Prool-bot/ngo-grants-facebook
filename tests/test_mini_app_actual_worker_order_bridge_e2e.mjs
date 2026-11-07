// Offline integration of the ACTUAL deployed Worker, but createRequest is stubbed
// before the module is loaded. No real D1/Telegram; no order or quota use.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const p=process.argv[2];
if(!p)throw Error("Expected Worker script path in isolated runner temp");
let source=readFileSync(p,"utf-8");
assert.match(source,/NGO_GRANTS_NATIVE_MINI_APP_V01/);
assert.match(source,/NGO_MINI_APP_NAV_FIX_V02/);
assert.match(source,/menu_version:'5\.8'/);

const createAnchor=/(async\s+function\s+createRequest\s*\(\s*env\s*,\s*chat\s*,\s*userId\s*,\s*d\s*,\s*updateId\s*\)\s*\{)/g;
const matches=[...source.matchAll(createAnchor)];
assert.equal(matches.length,1,"Must hook exactly ONE production createRequest call");
source=source.replace(createAnchor,`$1
    // E2E simulation: stop BEFORE any real D1/Telegram publication.
    globalThis.__ngoCapturedOrderCalls.push({chat,userId,d,updateId});
    return {accepted:true,simulated:true};
`);
source+="\nexport {handleTelegram,validatedDraft,defaultDraft};\n";
globalThis.__ngoCapturedOrderCalls=[];
const telegramMessages=[];
const originalFetch=globalThis.fetch;
globalThis.fetch=async (uri,opts)=>{
  const url=String(uri);
  assert.match(url,/^https:\/\/api\.telegram\.org\/botFAKE_E2E_NO_REAL_REQUEST\/sendMessage$/);
  telegramMessages.push(JSON.parse(opts.body));
  return new Response(JSON.stringify({ok:true,result:{message_id:55}}),{
    status:200,headers:{"content-type":"application/json"}
  });
};
const worker=await import("data:text/javascript;base64,"+
  Buffer.from(source).toString("base64"));
const valid={
  audience:"nonprofit",sectors:["social","recovery"],custom_sector:"",
  geo:"region",region:"kharkiv",detail:"Соціальний транспорт",
  applicant_role:"lead",funding_format:"grant_only"
};
function serviceData(facets,overrides={}){
  return {update_id:793311,message:{
    message_id:291,chat:{type:"private",id:155005500},
    from:{id:155005500,first_name:"Test"},
    web_app_data:{data:JSON.stringify({type:"ngo-grants-miniapp-v1",facets})},
    ...overrides
  }};
}
async function exercise(){
 const environment={BOT_TOKEN:"FAKE_E2E_NO_REAL_REQUEST"};
 const first=await worker.handleTelegram(environment,serviceData(valid));
 assert.equal(globalThis.__ngoCapturedOrderCalls.length,1,
   "Telegram web_app_data must reach the production createRequest exactly once");
 const c=globalThis.__ngoCapturedOrderCalls[0];
 assert.equal(c.chat,155005500);
 assert.equal(c.userId,155005500);
 assert.equal(c.updateId,793311);
 assert.equal(c.d.stage,"confirm");
 assert.equal(c.d.applicant_role,"lead");
 assert.equal(c.d.funding_format,"grant_only");
 assert.deepEqual(c.d.sectors,["social","recovery"]);
 assert.equal(worker.validatedDraft(c.d),true,
   "Production catalog validation must accept the actual Mini App fields");
 assert.equal(telegramMessages.length,0,
   "Simulated success does not contact even mocked Telegram");

 // This is a real entry-path check: the production handler must reject
 // spoofed identities BEFORE createRequest and answer with a safe message.
 await worker.handleTelegram(environment,serviceData(valid,{from:{id:155005501}}));
 assert.equal(globalThis.__ngoCapturedOrderCalls.length,1,"Forged identity must not enqueue");
 assert.equal(telegramMessages.length,1,"Invalid form should get a safe rejection");
 assert.doesNotMatch(telegramMessages[0].text,/BOT_TOKEN|private|stack|sql/i);

 // Invalid sectors never reach the actual createRequest.
 await worker.handleTelegram(environment,serviceData({...valid,sectors:["unapproved"]}));
 assert.equal(globalThis.__ngoCapturedOrderCalls.length,1);
 assert.equal(telegramMessages.length,2);

 // Normal bot messages are not falsely interpreted as orders.
 await worker.handleTelegram(environment,{
  update_id:793312,message:{
   message_id:292,chat:{type:"private",id:155005500},
   from:{id:155005500},text:"/assistant"
  }
 });
 assert.equal(globalThis.__ngoCapturedOrderCalls.length,1);
 assert.equal(telegramMessages.length,3);
 assert.ok(telegramMessages[2].reply_markup.keyboard[0][0].web_app);
 console.log("ACTUAL_WORKER_MINI_APP_ORDER_BRIDGE_E2E_SIMULATED_PASS");
 console.log("VALID_FORM_TO_PRODUCTION_CREATE_REQUEST=1");
 console.log("FORGED_USER_REJECTED=1;INVALID_FACET_REJECTED=1;LEGACY_MENU_WORKS=1");
 console.log("REAL_D1_WRITES=0;REAL_TELEGRAM_MESSAGES=0;REAL_CATALOG_ORDERS=0");
}
try{await exercise();}
finally{globalThis.fetch=originalFetch;delete globalThis.__ngoCapturedOrderCalls;}
