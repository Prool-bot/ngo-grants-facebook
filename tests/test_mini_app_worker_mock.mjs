/**
 * Offline smoke for patched deployed Worker. No Telegram token, no D1 writes.
 *
 * Usage: node tests/test_mini_app_worker_mock.mjs /tmp/patched-worker.mjs
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const file=process.argv[2];
if(!file)throw Error("Missing patched Worker module");
let source=readFileSync(file,"utf-8");
assert.match(source,/NGO_GRANTS_NATIVE_MINI_APP_V01/);
assert.match(source,/menu_version:'5\.8'/);
assert.match(source,/async function handleTelegram\(env,update\)/);
source+="\nexport {handleTelegram};\n";
const worker=await import("data:text/javascript;base64,"+
 Buffer.from(source).toString("base64"));

const url="https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/mini-app";
const page=await worker.default.fetch(new Request(url,{method:"GET"}),{});
assert.equal(page.status,200);
assert.match(page.headers.get("content-type"),/text\/html/);
const html=await page.text();
assert.match(html,/data-native-send="true"/);
assert.match(html,/telegram-web-app\.js/);
assert.match(html,/ngo-grants-miniapp-v1/);
assert.match(html,/NGO Grants AI/);
assert.doesNotMatch(html,/BOT_TOKEN|SYNC_SECRET|WEBHOOK_SECRET/);
const blocked=await worker.default.fetch(new Request(url,{method:"POST"}),{});
assert.equal(blocked.status,405);

// Telegram sendMessage is mocked; only a keyboard is constructed.
const actualFetch=globalThis.fetch;
const deliveries=[];
try{
 globalThis.fetch=async(resource,options)=>{
   const text=String(resource);
   assert.match(text,/^https:\/\/api\.telegram\.org\/botFAKE_OFFLINE_TOKEN\/sendMessage$/);
   assert.equal(options.method,"POST");
   const data=JSON.parse(options.body);
   deliveries.push(data);
   return new Response(JSON.stringify({ok:true,result:{message_id:1}}),
     {status:200,headers:{"content-type":"application/json"}});
 };
 await worker.handleTelegram(
   {BOT_TOKEN:"FAKE_OFFLINE_TOKEN"},
   {update_id:1234,message:{message_id:8,
      chat:{id:121212,type:"private"},
      from:{id:121212},text:"/assistant"}}
 );
 assert.equal(deliveries.length,1);
 assert.equal(deliveries[0].chat_id,121212);
 const keyboard=deliveries[0].reply_markup;
 assert.equal(keyboard.keyboard[0][0].web_app.url,url);
 assert.equal(keyboard.keyboard[1][0].text,"/start");
}finally{
 globalThis.fetch=actualFetch;
}
console.log("MINI_APP_WORKER_MOCK_PASS: safe static HTML, POST denied, Telegram reply keyboard mocked");
