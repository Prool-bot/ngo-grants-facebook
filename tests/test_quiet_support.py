from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
from patch_quiet_support import add_link, patch, HELPER, DIRECT, NATIVE, TELL, NATIVE_TELL, URL, LABEL

class QuietSupportTests(unittest.TestCase):
    def test_html_only_opt_in(self):
        html='<html><body><main><button>Далі</button></main></body></html>'
        result=add_link(html)
        self.assertEqual(result.count(URL),1)
        self.assertIn('id="ngoQuietSupportLink"',result)
        self.assertIn('<button>Далі</button>',result)
        self.assertIn("w.openLink(a.href)",result)
        with self.assertRaises(RuntimeError):
            add_link(result)

    def test_worker_patch_guards_exact_live_html(self):
        html='<html><body><main>NGO Grants AI</main></body></html>'
        src=('// NGO_MINI_APP_DIRECT_API_DORMANT_V05\n// NGO_GRANTS_NATIVE_MINI_APP_V01\n'
             +DIRECT+json.dumps(html)+';\n'+NATIVE+json.dumps(html)+';\n'
             +TELL+' return {text,markup}; }\n'
             +NATIVE_TELL+' return {text,keyboard}; }\n'
             +'async function handleTelegram(env,update){ return null; }\n'
             +'export default {async fetch(request,env){return new Response("ok");}};')
        result=patch(src,html,html)
        self.assertIn('return {text,markup};',result)
        self.assertIn('return null;',result)
        self.assertEqual(result.count('NGO_QUIET_SUPPORT_V01'),1)
        with self.assertRaises(RuntimeError):
            patch(src,html+'drift',html)
        with self.assertRaises(RuntimeError):
            patch(result,html,html)
        if shutil.which('node'):
            with tempfile.TemporaryDirectory() as tmp:
                file=Path(tmp)/'worker.mjs'
                file.write_text(result,encoding='utf-8')
                subprocess.run(['node','--check',str(file)],check=True,capture_output=True,text=True)

    @unittest.skipUnless(shutil.which("node"),"Node.js required")
    def test_menu_ready_and_no_extra_messages(self):
        script=HELPER+'''
const assert=require("node:assert/strict");
const url="https://donatello.to/NGO_Grants";
const menu={inline_keyboard:[[{text:"🔎 Замовити каталог",callback_data:"order"}],[{text:"📚 Готові каталоги",callback_data:"catalogs"}]]};
const start=__ngoQuietSupportDecorate(123,"Оберіть дію",menu);
assert.equal(start.text,"Оберіть дію");
assert.deepEqual(start.markup.inline_keyboard.slice(0,2),menu.inline_keyboard);
assert.equal(start.markup.inline_keyboard[2][0].url,url);
assert.equal(menu.inline_keyboard.length,2);
assert.deepEqual(__ngoQuietSupportDecorate(123,start.text,start.markup),start);
const native={keyboard:[[{text:"Відкрити грантового помічника",web_app:{url:"https://example.org"}}],[{text:"/start"}]]};
assert.equal(__ngoQuietSupportDecorate(123,"Відкрийте",native).markup.keyboard[2][0].text,"❤️ Підтримати проєкт");
const ready={inline_keyboard:[[{text:"Відкрити PDF",url:"https://t.me/ngo_grants/42"}]]};
const positive=__ngoQuietSupportDecorate(123,"Ваш каталог готовий!",ready);
assert.match(positive.text,/За бажанням/);
assert.deepEqual(positive.markup.inline_keyboard[0],ready.inline_keyboard[0]);
assert.equal(positive.markup.inline_keyboard[1][0].url,url);
for(const [chat,text,markup] of [[-100123,"Ваш каталог готовий!",ready],[123,"Ваш каталог ще не готовий",ready],[123,"Заявку прийнято",ready],[123,"Каталог готовий!",null],[123,"Наступний крок",{inline_keyboard:[[{text:"Далі",callback_data:"next"}]]}]]){
  assert.deepEqual(__ngoQuietSupportDecorate(chat,text,markup),{text,markup});
}
'''
        subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)

    def test_pdf_support_link_is_only_on_last_page(self):
        from ngo_grants_ai import pdf_catalog
        from pypdf import PdfReader
        rows=[{"id":n,"_title":"Тестова можливість","text":"Тестова грантова можливість.","_v41_card_fields":{
              "summary":"Тестова можливість.","funding":"1000 євро.","eligibility":"Громадські організації.",
              "geography":"Україна.","warning":"Перевірте умови."}} for n in (1,2,3)]
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"test.pdf"
            pdf_catalog(out,"Тестовий каталог","Тест",rows,date(2026,11,28))
            pdf=PdfReader(out)
            self.assertGreaterEqual(len(pdf.pages),3)
            links=[]
            for p in pdf.pages:
                links.append([str(ref.get_object().get("/A",{}).get("/URI","")) for ref in p.get("/Annots",[])])
            self.assertEqual(sum(x.count(URL) for x in links),1)
            self.assertIn(URL,links[-1])
            self.assertTrue(all(URL not in x for x in links[:-1]))
            self.assertIn("https://t.me/ngo_grants/3",links[-1])

if __name__=="__main__":
    unittest.main()
