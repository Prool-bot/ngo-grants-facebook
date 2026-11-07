import importlib.util
import io,json,os,sys
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location(
    "mini_app_start_v03_edit_post",ROOT/"scripts"/"mini_app_start_v03_edit_post.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeResponse:
 def __init__(self,payload):
    self.payload=payload
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n=-1):
    return json.dumps(self.payload,ensure_ascii=False).encode("utf-8")

class Tests(TestCase):
 def test_announce_uses_start_not_assistant_and_existing_bot(self):
    message=mod.updated_post("ngogratsAI_bot")
    self.assertIn("@ngogratsAI_bot",message)
    self.assertIn("2️⃣ Натисніть «Розпочати» (Start)",message)
    self.assertNotIn("/assistant",message)
    self.assertLess(len(message),4096)
 def test_only_editing_existing_post_not_duplicate_send(self):
    post=mod.updated_post("ngogratsAI_bot")
    captured=[]
    def fake_post(req,timeout):
      captured.append(req)
      response={"ok":True,"result":{"message_id":3813,
               "chat":{"username":"ngo_grants"},
               "text":"2️⃣ Натисніть «Розпочати» (Start) — кнопка помічника з’явиться одразу."}}
      return FakeResponse(response)
    with patch.object(mod.urllib.request,"urlopen",side_effect=fake_post):
       result=mod.edit_existing("FAKE_ONLY_TEST_TOKEN",3813,post,"ngogratsAI_bot")
    self.assertEqual(result["message_id"],3813)
    self.assertEqual(len(captured),1)
    self.assertIn("/editMessageText",captured[0].full_url)
    self.assertNotIn("/sendMessage",captured[0].full_url)
    payload=json.loads(captured[0].data)
    self.assertEqual(payload["chat_id"],"@ngo_grants")
    self.assertEqual(payload["message_id"],3813)
    self.assertEqual(payload["reply_markup"]["inline_keyboard"][0][0]["url"],
                     "https://t.me/ngogratsAI_bot")
 def test_main_cannot_edit_without_release_gate(self):
    with patch.dict(os.environ,{},clear=True),\
         patch.object(mod,"telegram") as no_read,\
         patch.object(mod,"edit_existing") as no_write:
      with self.assertRaisesRegex(RuntimeError,"explicit main-branch gate"):
          mod.main()
    no_read.assert_not_called()
    no_write.assert_not_called()

if __name__=="__main__":main()
