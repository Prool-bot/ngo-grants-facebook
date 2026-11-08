import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace as O
from unittest import TestCase,main
from unittest.mock import AsyncMock,patch
import os,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("enable_main",
  ROOT/"scripts"/"mini_app_enable_main_botfather_once.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Tests(TestCase):
 def test_only_exact_existing_bot_and_url_authorized(self):
    self.assertEqual(mod.URL,
      "https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/mini-app/direct")
    with patch.dict(os.environ,{},clear=True):
      with self.assertRaisesRegex(RuntimeError,"setup gate missing"):
        mod.confirm_environment()
 def test_existing_lock_blocks_duplicate_configuration(self):
    with patch.object(mod,"github_api",return_value=(200,{"sha":"already"})) as github:
      with self.assertRaisesRegex(RuntimeError,"already attempted"):mod.lock_action()
      self.assertEqual(github.call_count,1)
      self.assertEqual(github.call_args.args[0],"GET")
 def test_one_shot_lock_is_created_before_changes(self):
    calls=[]
    def api(method,path,payload=None):
      calls.append((method,path))
      if method=="GET":return 404,{}
      if method=="PUT":return 201,{"content":{"sha":"fake-lock-sha"}}
      raise AssertionError("Unexpected request")
    with patch.object(mod,"github_api",side_effect=api):
      rec,sha=mod.lock_action()
    self.assertEqual(rec["status"],"attempted")
    self.assertEqual(sha,"fake-lock-sha")
    self.assertEqual([m for m,_ in calls],["GET","PUT"])
 def test_prompt_must_be_from_new_botfather_message(self):
    class FakeClient:
      def __init__(self,new):self.new=new
      async def get_messages(self,father,limit):
        return [O(id=11 if self.new else 10,out=False,
                  raw_text="Please send me your Main Mini App URL")]
    async def check():
      with patch.object(mod.asyncio,"sleep",new_callable=AsyncMock):
        await mod.wait_url_prompt(FakeClient(True),"BotFather",10)
        with self.assertRaisesRegex(RuntimeError,"did not explicitly request"):
          await mod.wait_url_prompt(FakeClient(False),"BotFather",10)
    asyncio.run(check())
 def test_old_help_text_or_unrequested_url_cannot_trigger_send(self):
    class Fake:
      async def get_messages(self,*args,**kwargs):
        return [O(id=25,out=False,raw_text="Configure your web app at https://example.org")]
    async def check():
      with patch.object(mod.asyncio,"sleep",new_callable=AsyncMock):
        with self.assertRaises(RuntimeError):
          await mod.wait_url_prompt(Fake(),"BotFather",20)
    asyncio.run(check())
if __name__=="__main__":main()
