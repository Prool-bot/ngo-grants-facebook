/**
 * Actual candidate Worker integration smoke with Telegram fetch mocked.
 * Requires a runner-local private Worker JS candidate. No real Telegram,
 * no D1 writes and no catalog submission.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const f=process.argv[2];
if(!f)throw Error("Missing candidate Worker file");
let source=readFileSync(f,"utf8");
assert.match(source,/NGO_MINI_APP_DIRECT_START_V03/);
assert.match(source,/menu_version:'5\.8'/);
source+="\nexport {handleTelegram};";
let worker;
try{
  worker=await import("data:text/javascript;base64,"+
    Buffer.from(source).toString("base64"));
}catch(_){
  throw Error("Private Worker source validation failed (source suppressed)");
}
const prev=globalThis.fetch;
const telegram=[];
globalThis.fetch=async(resource,opts)=>{
  assert.equal(String(resource),"https://api.telegram.org/botFAKE_START_TEST/sendMessage");
  telegram.push(JSON.parse(opts.body));
  return new Response(JSON.stringify({ok:true,result:{message_id:5}}),{
    status:200,headers:{"content-type":"application/json"}
  });
};
try{
 const env={BOT_TOKEN:"FAKE_START_TEST"};
 const makeUpdate=(text,id=111222)=>({
   update_id:1001,message:{
    message_id:444,chat:{id,type:"private"},
    from:{id},text
   }
 });
 await worker.handleTelegram(env,makeUpdate("/start"));
 assert.equal(telegram.length,1,"Start must send exactly one message");
 assert.equal(telegram[0].chat_id,111222);
 assert.match(telegram[0].text,/Відкрити грантового помічника/);
 const keyboard=telegram[0].reply_markup?.keyboard;
 assert.ok(keyboard&&keyboard.length>=3);
 assert.equal(keyboard[0][0].web_app.url,
   "https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/mini-app");
 assert.deepEqual(keyboard[1].map(x=>x.text),["/request","/catalogs"]);
 assert.deepEqual(keyboard[2].map(x=>x.text),["/help","/status"]);

 // Deep links must work exactly like pressing Start.
 telegram.length=0;
 await worker.handleTelegram(env,makeUpdate("/start referral2026"));
 assert.equal(telegram.length,1);
 assert.equal(telegram[0].reply_markup.keyboard[0][0].text,
   "🤖 Відкрити грантового помічника");

 // /assistant is retained for users of the original public post/command.
 telegram.length=0;
 await worker.handleTelegram(env,makeUpdate("/assistant"));
 assert.equal(telegram.length,1);
 assert.ok(telegram[0].reply_markup.keyboard[0][0].web_app.url);

 console.log("LIVE_WORKER_START_DIRECT_MINI_APP_MOCK_PASS");
 console.log("START_SINGLE_REPLY=1;DEEP_LINK_START_OK=1;LEGACY_ASSISTANT_OK=1");
 console.log("REAL_TELEGRAM_MESSAGES=0;REAL_D1_WRITES=0;CATALOG_ORDERS=0");
}finally{globalThis.fetch=prev;}
