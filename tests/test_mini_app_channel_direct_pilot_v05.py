from pathlib import Path
import importlib.util
from unittest import TestCase
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location(
    "mini_app_channel_direct_pilot_v05",
    ROOT/"scripts"/"mini_app_channel_direct_pilot_v05.py"
)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class PilotLinkTests(TestCase):
 def test_corrects_old_bot_chat_cta_and_keeps_fallback(self):
  text=mod.proposed_text()
  self.assertIn("1️⃣ Натисніть кнопку «🤖 Знайти гранти»",text)
  self.assertNotIn("1️⃣ Відкрийте бота @ngogratsAI_bot",text)
  self.assertNotIn("/assistant",text)
  self.assertIn("↩️ Резервний вхід через бота",text)
  self.assertLessEqual(len(text),3900)
  self.assertEqual(mod.MAIN_LINK,"https://t.me/ngogratsAI_bot?startapp=ngo_grants")
  self.assertNotEqual(mod.MAIN_LINK,mod.FALLBACK_LINK)
 def test_guard_fails_before_any_public_edit(self):
  with patch.dict("os.environ",{"GITHUB_ACTIONS":"true",
    "GITHUB_REF":"refs/heads/main",
    "GITHUB_REPOSITORY":"Prool-bot/ngo-grants-facebook"},clear=True),\
    patch.object(mod,"telegram") as telegram,\
    patch.object(mod,"github_api") as github:
   with self.assertRaises(RuntimeError):mod.main()
   telegram.assert_not_called()
   github.assert_not_called()
 def test_only_post_3813_is_a_target(self):
  self.assertEqual(mod.POST_ID,3813)
  self.assertEqual(mod.CHANNEL,"@ngo_grants")
  self.assertEqual(mod.MARKER,
    "launches/mini_app_channel_direct_pilot_v05_2026-11-08.json")
