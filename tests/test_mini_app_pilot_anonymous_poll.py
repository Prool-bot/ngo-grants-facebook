import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
import json

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location(
  "mini_app_pilot_anonymous_poll",ROOT/"scripts"/"mini_app_pilot_anonymous_poll.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class MockResponse:
 def __init__(self,payload):self.payload=payload
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self,n):return json.dumps(self.payload).encode()

class Tests(TestCase):
 def test_link_existing_announcement_to_poll_without_assistant_step(self):
  text=mod.markup_text(3820,"ngogratsAI_bot")
  self.assertIn("https://t.me/ngo_grants/3820",text)
  self.assertIn("Коментарі до допису поки недоступні",text)
  self.assertNotIn("залиште коментар",text)
  self.assertNotIn("/assistant",text)
  self.assertLess(len(text),4096)
 def test_poll_is_anonymous_and_there_is_no_respondent_collection(self):
  self.assertEqual(len(mod.OPTIONS),6)
  self.assertTrue(all(len(x)<100 for x in mod.OPTIONS))
  self.assertLess(len(mod.QUESTION),300)
  calls=[]
  def fake(req,timeout):
    calls.append(req)
    return MockResponse({"ok":True,"result":{
      "message_id":3820,"chat":{"username":"ngo_grants"}}})
  with patch.object(mod.urllib.request,"urlopen",side_effect=fake):
    result=mod.send("sendPoll",{
      "chat_id":"@ngo_grants","question":mod.QUESTION,
      "options":mod.OPTIONS,"is_anonymous":True,
      "allows_multiple_answers":False
    },"FAKE_TEST_TOKEN_ONLY")
  self.assertEqual(result["message_id"],3820)
  self.assertEqual(len(calls),1)
  self.assertIn("/sendPoll",calls[0].full_url)
  self.assertNotIn("/sendMessage",calls[0].full_url)
  fields=json.loads(calls[0].data)
  self.assertTrue(fields["is_anonymous"])
  self.assertEqual(fields["chat_id"],"@ngo_grants")
 def test_fail_closed_if_broken_link_or_unexpected_write(self):
  for wrong in (0,-1,"wrong"):
    with self.assertRaises(ValueError):
      mod.markup_text(wrong,"ngogratsAI_bot")
  with self.assertRaises(ValueError):
    mod.send("sendMessage",{},"FAKE")

if __name__=="__main__":main()
