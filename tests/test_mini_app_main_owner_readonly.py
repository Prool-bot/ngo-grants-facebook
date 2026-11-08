import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
SP=importlib.util.spec_from_file_location(
 "mini_app_main_owner_readonly",ROOT/"scripts"/"mini_app_main_owner_readonly.py")
MOD=importlib.util.module_from_spec(SP);SP.loader.exec_module(MOD)

class OwnershipTests(TestCase):
 def test_owner_account_can_edit_not_necessarily_registered(self):
  entity=SimpleNamespace(bot=True,username="ngogratsAI_bot",
      bot_can_edit=True,bot_has_main_app=False,id=123,phone="private")
  result=MOD.assessment(entity)
  self.assertEqual(result,{
     "session_can_edit_this_bot":True,"main_mini_app_registered":False})
  self.assertNotIn("private",str(result))
  self.assertNotIn("123",str(result))
 def test_nonowner_is_not_claimed_as_owner(self):
  entity=SimpleNamespace(bot=True,username="ngogratsAI_bot",
      bot_can_edit=False,bot_has_main_app=False)
  self.assertFalse(MOD.assessment(entity)["session_can_edit_this_bot"])
 def test_reject_wrong_bot_identity(self):
  with self.assertRaises(RuntimeError):
   MOD.assessment(SimpleNamespace(bot=True,username="wrong_bot"))
  with self.assertRaises(RuntimeError):
   MOD.assessment(SimpleNamespace(bot=False,username="ngogratsAI_bot"))

if __name__=="__main__":main()
