import importlib.util
from pathlib import Path
from types import SimpleNamespace as O
from unittest import TestCase,main
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("nav",ROOT/"scripts"/"mini_app_botfather_nav_readonly.py")
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
class Tests(TestCase):
 def test_only_exact_known_telegram_buttons(self):
  self.assertTrue(mod.is_target("@ngogratsAI_bot"))
  self.assertTrue(mod.is_target("NGO Grants AI"))
  self.assertFalse(mod.is_target("@anotherbot"))
  self.assertTrue(mod.is_settings("⚙️ Bot Settings"))
  self.assertFalse(mod.is_settings("Bot Management"))
  self.assertTrue(mod.is_mini("Configure Mini App"))
  self.assertFalse(mod.is_mini("Menu Button"))
 def test_disregards_older_or_outgoing_messages(self):
  fake=[
    O(id=12,out=True,buttons=[[O(text="Configure Mini App")]]),
    O(id=11,out=False,buttons=[[O(text="Configure Mini App")]]),
    O(id=15,out=False,buttons=[[O(text="Bot Settings")]])
  ]
  got=mod.matching_buttons(fake,mod.is_mini,min_id=12)
  self.assertEqual(got,[])
  got=mod.matching_buttons(fake,mod.is_settings,min_id=12)
  self.assertEqual(len(got),1)
  self.assertEqual(got[0][0].id,15)
if __name__=="__main__":main()
