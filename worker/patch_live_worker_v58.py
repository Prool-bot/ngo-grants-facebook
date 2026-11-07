"""Patch the *currently deployed* NGO Grants Cloudflare Worker in memory.

Never commits production Worker source into Git. All changes are asserted against
source anchors, and are validated by CI before uploading a dormant Worker version.
"""
from __future__ import annotations

import re
import sys


def patch_worker(source: str) -> str:
    s = source
    if 'menu_version:\'5.8\'' in s or 'guided Telegram menu v5.8' in s:
        raise RuntimeError('Already patched, refusing to patch twice')
    if 'guided Telegram menu v5.2' not in s or 'ngo_grants' not in s:
        raise RuntimeError('Unexpected original Worker version, refusing to change code')

    def put_once(old: str, new: str, name: str):
        nonlocal s
        found = s.count(old)
        if found != 1:
            raise RuntimeError(f'Anchor mismatch [{name}]: found {found}, expected 1')
        s = s.replace(old, new, 1)

    put_once('guided Telegram menu v5.2', 'guided Telegram menu v5.8', 'version comment')
    put_once("menu_version:'5.2'", "menu_version:'5.8'", 'health version')

    put_once("['individual','👤 Фізична особа'],['all','🌐 Усі категорії']",
             "['individual','👤 Фізична особа'],['municipal','🏙 Місцева рада / громада'],"
             "['institution','🏫 Заклад освіти / науки'],['all','🌐 Усі категорії']",
             'new applicant types')
    put_once(
        "function defaultDraft(){return {session:crypto.randomUUID().replace(/-/g,'').slice(0,12),stage:'audience',audience:'',sectors:[],custom_sector:'',geo:'',region:'',detail:'',at:Date.now()};}",
        "function defaultDraft(){return {session:crypto.randomUUID().replace(/-/g,'').slice(0,12),stage:'audience',audience:'',sectors:[],custom_sector:'',geo:'',region:'',detail:'',applicant_role:'lead',funding_format:'grant_only',ai_used:false,clarify_kind:'',ai_question:'',at:Date.now()};}",
        'durable new draft fields')
    put_once(
        "`✍️ <b>Уточнення:</b> ${esc(d.detail||'Усі можливості за обраними критеріями')}`;}",
        "`✍️ <b>Уточнення:</b> ${esc(d.detail||'Усі можливості за обраними критеріями')}\\n`+"
        "`🤝 <b>Роль:</b> ${esc(({lead:'Основний заявник',partner:'Партнер',either:'Основний заявник або партнер'})[d.applicant_role||'lead'])}\\n`+"
        "`💶 <b>Форма:</b> ${d.funding_format==='any'?'Усі види підтримки':'Лише проєктне фінансування / гранти'}`;}",
        'preview summary')

    # Do not infer a municipality is a non-profit, or an individual is a FOP.
    put_once(
        "d.audience==='individual'?'фізичних осіб':'усіх заявників';",
        "d.audience==='individual'?'фізичних осіб':d.audience==='municipal'?'органів місцевого самоврядування':"
        "d.audience==='institution'?'закладів освіти та науки':'усіх заявників';",
        'queue topic applicant')

    put_once(
        "typeof d.detail==='string'&&d.detail.length<=180);}",
        "typeof d.detail==='string'&&d.detail.length<=180&&"
        "['lead','partner','either'].includes(d.applicant_role||'lead')&&"
        "['grant_only','any'].includes(d.funding_format||'any'));}",
        'validate refinements')

    put_once(
        "v.geo,v.geo==='region'?(v.region||''):'',normalizeText(v.detail||'').toLowerCase()]);",
        "v.geo,v.geo==='region'?(v.region||''):'',normalizeText(v.detail||'').toLowerCase(),"
        "v.applicant_role||'lead',v.funding_format||'any']);",
        'duplicate signature includes refinements')

    put_once(
        "custom_sector:d.custom_sector||'',geo:d.geo,region:d.geo==='region'?d.region:'',detail:d.detail||''};",
        "custom_sector:d.custom_sector||'',geo:d.geo,region:d.geo==='region'?d.region:'',detail:d.detail||'',"
        "applicant_role:d.applicant_role||'lead',funding_format:d.funding_format||'grant_only'};",
        'stored submitted facets')

    # The AI is offered only once for a single clean *topic*, never for user data.
    helpers = '''
// v5.8: Non-destructive clarification. No messages or D1 rows are created
// merely by selecting options. AI is advisory, never rewrites the user query.
function knownClarification(d){
 const t=normalizeText(d.detail||'').toLowerCase(), ss=d.sectors||[];
 if(d.audience==='nonprofit'&&/(територіальн.{0,12}громад|для громад|муніципал)/u.test(t))return 'municipal';
 if(d.audience==='individual'&&ss.some(x=>x==='business'||x==='agriculture'))return 'fop';
 if(/(жіноч|жін|women)/u.test(t)&&/(бізнес|підприєм|стартап|business|entrepreneur)/u.test(t))return 'women';
 if(ss.length>=3&&!t)return 'focus';
 return '';
}
function needsAiClarify(d){
 const t=normalizeText(d.detail||'').toLowerCase();
 if(t.length<7||d.ai_used||invalidInfo(t))return false;
 return /(?:розвиток|проєкти|ініціативи|підтримка|інноваці|соціальн|освітн|міжнародн|відновлен)/u.test(t);
}
async function aiMenuQuestion(env,d){
 if(!env.AI||!needsAiClarify(d))return '';
 d.ai_used=true;
 // Never include Telegram identities, hashes or contact details in prompts.
 const topic=normalizeText(d.detail).slice(0,180);
 const prompt='Ви аналізуєте короткий запит користувача на грантовий каталог. '+
  'Визначте, чи не вистачає суттєвої інформації про фінансовану діяльність. '+
  'Не припускайте, що ГО, бізнес, ФОП і фізособа — те саме. '+
  'Якщо тема достатньо точна, поверніть {"ask":false,"question":""}. '+
  'Якщо уточнення суттєво поліпшить пошук, поверніть JSON {"ask":true,"question":"одне коротке питання українською до 110 символів"}. '+
  'Не просіть ПІБ, номер телефону, посилання, гроші або адресу. '+
  'Потрібне тільки валідне JSON, без пояснень. '+
  'Тип заявника: '+d.audience+'; сфери: '+d.sectors.join(',')+'; тема: '+topic;
 try{
   const task=env.AI.run('@cf/meta/llama-3.1-8b-instruct-fp8',{
     messages:[{role:'user',content:prompt}],max_tokens:125,temperature:0.1});
   const timeout=new Promise(resolve=>setTimeout(()=>resolve(null),4000));
   const result=await Promise.race([task,timeout]);
   const raw=String(result?.response||'');
   const match=raw.match(/\\{[\\s\\S]{0,650}\\}/u);
   if(!match)return '';
   const obj=JSON.parse(match[0]),q=normalizeText(obj.question||'');
   if(obj.ask!==true||q.length<12||q.length>110||invalidInfo(q))return '';
   return q;
 }catch{return '';}
}
async function advanceAfterDetail(env,d){
 d.clarify_kind=knownClarification(d);
 if(d.clarify_kind){d.stage='clarify';return;}
 const q=await aiMenuQuestion(env,d);
 d.ai_question=q;
 d.stage=q?'ai_clarify':'role';
}
'''
    put_once('function defaultDraft(){', helpers+'\nfunction defaultDraft(){', 'add clarifier')

    put_once("'🔎 <b>Крок 1/4. Хто шукає фінансування?</b>",
             "'🔎 <b>Крок 1/6. Хто шукає фінансування?</b>", 'step audience')
    put_once("'📚 <b>Крок 2/4. Сфера діяльності</b>",
             "'📚 <b>Крок 2/6. Сфера діяльності</b>", 'step sector')
    put_once("'🌍 <b>Крок 3/4. Географія</b>",
             "'🌍 <b>Крок 3/6. Географія</b>", 'step geography')
    put_once("'📍 <b>Крок 3/4. Конкретна область</b>",
             "'📍 <b>Крок 3/6. Конкретна область</b>", 'step region')
    put_once("'✍️ <b>Крок 4/4. Уточнення запиту</b>",
             "'✍️ <b>Крок 4/6. Уточнення запиту</b>", 'step detail')
    put_once("'✅ <b>Крок 4/4. Підтвердження замовлення</b>",
             "'✅ <b>Крок 6/6. Підтвердження замовлення</b>", 'step confirmation')

    render_insert = '''  }else if(d.stage==='clarify'){
   if(d.clarify_kind==='municipal'){
     text='🧭 <b>Уточнення заявника</b>\\n\\nЗаявку подає сама рада / територіальна громада чи громадська організація, що працює в громаді?';
     buttons=[[['🏛 ГО / БФ','cl:ngo']],[['🏙 Рада / громада','cl:muni']],back];
   }else if(d.clarify_kind==='fop'){
     text='🧭 <b>Уточнення заявника</b>\\n\\nВи шукаєте підтримку для фізичної особи без підприємницької реєстрації чи для ФОП?';
     buttons=[[['👤 Фізична особа (без ФОП)','cl:person']],[['🏢 Зареєстрований ФОП','cl:fop']],back];
   }else if(d.clarify_kind==='women'){
     text='🧭 <b>Уточнення бізнес-програми</b>\\n\\nШукаємо тільки спеціальні програми для жіночого бізнесу чи також загальні бізнес-гранти?';
     buttons=[[['👩 Лише програми для жінок','cl:women']],[['🌐 Усі бізнес-гранти','cl:business']],back];
   }else{
     text='🧭 <b>Уточнення напрямів</b>\\n\\nВи обрали кілька сфер. Шукатимемо їх <b>окремо</b> (будь-який напрям, не обов’язково всі одночасно). Можна додати конкретну діяльність.';
     buttons=[[['✏️ Уточнити діяльність','cl:focus']],[['✅ Кожен напрям окремо','cl:skip']],back];
   }
  }else if(d.stage==='ai_clarify'){
   text='🤖 <b>Питання від ШІ</b>\\n\\n'+esc(d.ai_question||'Уточніть діяльність')+
    '\\n\\nЦе рекомендація. Ви можете відповісти текстом або продовжити без змін. ШІ нічого не додає до запиту без вашого вибору.';
   buttons=[[['✏️ Додати уточнення','ai:edit']],[['➡️ Без уточнення','ai:skip']],back];
  }else if(d.stage==='role'){
   text='🤝 <b>Крок 5/6. Роль заявника</b>\\n\\nМожливість має підходити для самостійної заявки, партнерства чи обох варіантів?';
   buttons=[[['✅ Основний заявник','role:lead']],[['🤝 Партнер у проєкті','role:partner']],
            [['🌐 Обидва варіанти','role:either']],back];
  }else if(d.stage==='funding'){
   text='💶 <b>Крок 5/6. Вид підтримки</b>\\n\\nВиберіть, що включати до каталогу. Стипендії, премії та навчання без проєктного гранту можуть не підходити для заявок ГО.';
   buttons=[[['💶 Гранти / проєктне фінансування','fund:grant_only']],
            [['🌐 Усі види підтримки','fund:any']],back];
'''
    put_once("}else if(d.stage==='confirm'){", render_insert+"}else if(d.stage==='confirm'){", 'new screens')

    put_once(
        "region:'geo',detail:'geo',write:'detail',confirm:'detail'};",
        "region:'geo',detail:'geo',write:'detail',clarify:'detail',ai_clarify:'detail',"
        "role:'detail',funding:'role',confirm:'funding'};",
        'back navigation')

    handlers = '''  }else if(data.startsWith('cl:')&&d.stage==='clarify'){
   const v=data.slice(3);
   if(d.clarify_kind==='municipal'&&['ngo','muni'].includes(v))d.audience=v==='muni'?'municipal':'nonprofit';
   else if(d.clarify_kind==='fop'&&['person','fop'].includes(v))d.audience=v==='fop'?'commercial':'individual';
   else if(d.clarify_kind==='women'&&['women','business'].includes(v)){
     if(v==='business')d.detail='Підприємництво та бізнес';
   }else if(d.clarify_kind==='focus'&&v==='focus'){
     d.stage='write';d.clarify_kind='';d.ai_used=true;
     await saveDraft(env,hash,d);return render(env,chat,d,editId);
   }else if(d.clarify_kind!=='focus'||v!=='skip')return render(env,chat,d,editId);
   d.clarify_kind='';d.stage='role';
  }else if(data.startsWith('ai:')&&d.stage==='ai_clarify'){
   const v=data.slice(3);if(!['edit','skip'].includes(v))return;
   d.stage=v==='edit'?'write':'role';d.ai_question='';d.ai_used=true;
  }else if(data.startsWith('role:')&&d.stage==='role'){
   const v=data.slice(5);if(!['lead','partner','either'].includes(v))return;
   d.applicant_role=v;d.stage='funding';
  }else if(data.startsWith('fund:')&&d.stage==='funding'){
   const v=data.slice(5);if(!['grant_only','any'].includes(v))return;
   d.funding_format=v;d.stage='confirm';
'''
    put_once("}else if(data==='edit'&&d.stage==='confirm'){",
             handlers+"}else if(data==='edit'&&d.stage==='confirm'){",
             'new actions')
    put_once("d.detail='';d.stage='confirm';", "d.detail='';await advanceAfterDetail(env,d);", 'no detail path')
    put_once("d.detail=value;d.stage='confirm';", "d.detail=value;await advanceAfterDetail(env,d);", 'text detail path')

    # After updating the Worker, old drafts remain valid: missing fields use
    # defaults. No migrations, new D1 tables or webhook resets.
    if 'env.AI.run(' not in s or 'funding_format:d.funding_format' not in s:
        raise RuntimeError('Failed worker patch final validation')
    return s


if __name__ == '__main__':
    sys.stdout.write(patch_worker(sys.stdin.read()))