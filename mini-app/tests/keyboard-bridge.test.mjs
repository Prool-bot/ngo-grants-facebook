import test from "node:test";
import assert from "node:assert/strict";
import {
 MINI_APP_MARKER,parseMiniAppServiceMessage,processMiniAppUpdate,
 validateKeyboardFacets,miniAppKeyboard,miniAppDraft
} from "../../worker/mini_app_keyboard_bridge.mjs";

const facets={
 audience:"nonprofit",sectors:["social","recovery"],custom_sector:"",
 geo:"region",region:"kharkiv",detail:"Соціальний транспорт",
 applicant_role:"lead",funding_format:"grant_only"
};
function update(overrides={}){
 return {
  update_id:501,
  message:{
   message_id:20,chat:{id:212121,type:"private"},
   from:{id:212121,first_name:"Test"},
   web_app_data:{data:JSON.stringify({type:MINI_APP_MARKER,facets})},
   ...(overrides.message||{})
  },
  ...Object.fromEntries(Object.entries(overrides).filter(([k])=>k!=="message"))
 };
}
test("valid Telegram service message gets identity from signed webhook context",()=>{
 const out=parseMiniAppServiceMessage(update());
 assert.deepEqual(out,{userId:212121,chatId:212121,updateId:501,facets});
});
test("does not intercept ordinary messages",()=>{
 assert.equal(parseMiniAppServiceMessage({update_id:1,message:{text:"hello"}}),null);
});
test("strictly rejects forged chat, user ID and malformed application data",()=>{
 const attacks=[
   update({message:{from:{id:222}}}),
   update({message:{chat:{id:212121,type:"group"}}}),
   update({update_id:null}),
   update({message:{web_app_data:{data:"not json"}}}),
   update({message:{web_app_data:{data:JSON.stringify({type:MINI_APP_MARKER,facets,user_id:222})}}}),
   update({message:{web_app_data:{data:JSON.stringify({type:"unknown",facets})}}}),
   update({message:{web_app_data:{data:"x".repeat(4100)}}})
 ];
 for(const x of attacks)assert.throws(()=>parseMiniAppServiceMessage(x));
});
test("validates exact legacy facets and independent sector selection",()=>{
 assert.deepEqual(validateKeyboardFacets({...facets,sectors:["social","social","recovery"]}).sectors,
  ["social","recovery"]);
 const wrong=[
   {...facets,audience:"invalid"},
   {...facets,sectors:[]},
   {...facets,sectors:["rogue"]},
   {...facets,geo:"region",region:"fake"},
   {...facets,detail:"https://attacker.example"},
   {...facets,chat_id:123}
 ];
 for(const x of wrong)assert.throws(()=>validateKeyboardFacets(x));
});
test("uses original draft factory, no parallel queue or bypass",async()=>{
 const calls=[];
 const originalFactory=()=>({session:"abc123",stage:"audience",at:1});
 const result=await processMiniAppUpdate(update(),{DB:"production-existing"},{
   defaultDraft:originalFactory,
   validatedDraft:()=>true,
   createRequest:async (...args)=>{
     calls.push(args);return {accepted:true};
   }
 });
 assert.equal(result.accepted,true);
 assert.equal(calls.length,1);
 assert.equal(calls[0][1],212121);
 assert.equal(calls[0][2],212121);
 assert.equal(calls[0][3].stage,"confirm");
 assert.equal(calls[0][3].session,"abc123");
 assert.equal(calls[0][4],501);
});
test("fails closed when live worker draft validation declines",async()=>{
 let enqueueCount=0;
 await assert.rejects(()=>processMiniAppUpdate(update(),{},{
  defaultDraft:()=>({session:"s",stage:"audience"}),
  validatedDraft:()=>false,
  createRequest:async()=>{enqueueCount++;}
 }));
 assert.equal(enqueueCount,0);
});
test("Telegram keyboard launches HTTPS app in same origin",()=>{
 const keyboard=miniAppKeyboard("https://example.workers.dev/webhook");
 const first=keyboard.keyboard[0][0];
 assert.equal(first.web_app.url,"https://example.workers.dev/mini-app");
 assert.throws(()=>miniAppKeyboard("http://localhost:8787"));
});
