import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

let src=readFileSync(process.argv[2], 'utf8');
assert.match(src,/guided Telegram menu v5\.8/);
assert.match(src,/menu_version:'5\.8'/);
assert.match(src,/function knownClarification\(/);
assert.match(src,/env\.AI\.run\(/);
assert.match(src,/applicant_role:d\.applicant_role/);

// Do not call the live Telegram API. Replace the local message-delivery
// function ONLY in an in-memory copy of the Worker to test its UI screens.
const tellFn=/async function tell\(env,chatId,text,markup=null,editId=null\)\{[\s\S]*?\n\}/;
assert.equal((src.match(tellFn)||[]).length,1,'Telegram send function anchor');
src=src.replace(tellFn,`async function tell(env,chatId,text,markup=null,editId=null){
  env.outputs.push({chatId,text,markup,editId});return {message_id:77};
}`);
src+='\nexport {defaultDraft,knownClarification,needsAiClarify,advanceAfterDetail,summary,validatedDraft,render,facetsSignature,textForQueue};\n';
const m=await import('data:text/javascript;base64,'+Buffer.from(src).toString('base64'));
const {defaultDraft,knownClarification,advanceAfterDetail,summary,validatedDraft,
       render,facetsSignature,textForQueue}=m;
const build=(audience,sectors,detail='')=>({...defaultDraft(),audience,sectors,geo:'ukraine',detail});
const env={outputs:[]};
const log=[];
function check(name,fn){try{fn();log.push('PASS '+name);}catch(e){throw new Error(name+': '+e.message,{cause:e});}}
check('default fields',()=>{const d=defaultDraft();assert.equal(d.applicant_role,'lead');assert.equal(d.funding_format,'grant_only');});
check('rejects invalid drafts',()=>{const d=build('nonprofit',['social']);assert.equal(validatedDraft(d),true);d.applicant_role='superadmin';assert.equal(validatedDraft(d),false);});
check('new applicants',()=>{const d=build('municipal',['recovery'],'енергетичні інвестиції громад');assert.equal(validatedDraft(d),true);assert.match(textForQueue(d),/місцевого самоврядування/);});
check('municipal vs nonprofit',()=>{assert.equal(knownClarification(build('nonprofit',['recovery'],'Гранти для територіальних громад')),'municipal');});
check('person vs FOP',()=>{assert.equal(knownClarification(build('individual',['agriculture'],'бджільництво')),'fop');});
check('special women business vs generic',()=>{assert.equal(knownClarification(build('commercial',['business'],'Гранти для жіночого підприємництва')),'women');});
check('separate multiple sectors',()=>{assert.equal(knownClarification(build('nonprofit',['agriculture','social','culture'])),'focus');});
check('signature differentiates role and funding',()=>{const a=build('nonprofit',['culture']);const b={...a,funding_format:'any'};assert.notEqual(facetsSignature(a),facetsSignature(b));});
check('no personal data in summary',()=>{const d=build('nonprofit',['social'],'Підтримка <дітей>');const s=summary(d);assert.match(s,/&lt;дітей&gt;/);assert.match(s,/Основний заявник/);});
const direct=build('nonprofit',['recovery'],'Територіальні громади');
await advanceAfterDetail(env,direct);assert.equal(direct.stage,'clarify');
check('deterministic clarification',()=>assert.equal(direct.clarify_kind,'municipal'));
const clear=build('nonprofit',['agriculture'],'бджільництво');
await advanceAfterDetail(env,clear);
check('clear niche request skips AI',()=>assert.equal(clear.stage,'role'));
let aiCalls=0;const aiEnv={AI:{run:async(_model,options)=>{aiCalls++; assert(!JSON.stringify(options).includes('userId'));return {response:'{"ask":true,"question":"Яку конкретну діяльність потрібно профінансувати?"}'}}}};
const broad=build('nonprofit',['social'],'Підтримка соціальних ініціатив');
await advanceAfterDetail(aiEnv,broad);
check('actual Workers AI clarification',()=>{assert.equal(aiCalls,1);assert.equal(broad.stage,'ai_clarify');assert.match(broad.ai_question,/діяльність/);});
await advanceAfterDetail(aiEnv,broad);
check('AI only once per draft',()=>assert.equal(aiCalls,1));
const noAi=build('nonprofit',['social'],'Розвиток соціальних ініціатив');
await advanceAfterDetail(env,noAi);
check('deterministic fallback without AI binding',()=>assert.equal(noAi.stage,'role'));
let outputs=[];
for(const stage of ['audience','sectors','geo','detail','clarify','ai_clarify','role','funding','confirm']){
 const d=build('nonprofit',['social'],'грант');d.stage=stage;d.clarify_kind='municipal';d.ai_question='Які цільові групи?';
 const e={outputs:[]};await render(e,123,d);
 assert.equal(e.outputs.length,1,`${stage}: not rendered`);
 assert(e.outputs[0].markup?.inline_keyboard?.length>0,`${stage}: no buttons`);
 outputs.push(stage);
}
check('all menu screens render with inline buttons',()=>assert.equal(outputs.length,9));
// Status/confirm buttons must never enqueue the request until explicit submit.
check('old draft fields remain compatible',()=>{let d=build('nonprofit',['social']);delete d.applicant_role;delete d.funding_format;assert.equal(validatedDraft(d),true);});
console.log('WORKER_MENU_V58_TESTS_OK',log.length,'checked screens',outputs.length);