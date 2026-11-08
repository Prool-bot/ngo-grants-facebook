"""No Telegram calls. Validate exact single-public-result edit contract."""
from datetime import date
from pathlib import Path
import importlib.util
import sys
from unittest import TestCase
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location(
 "mini_app_repair_result_3815",ROOT/"scripts"/"mini_app_repair_result_3815.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class ResultRepairTests(TestCase):
 def test_exact_target_and_unrelated_records_untouched(self):
    item={"status":"published","reason":"no_candidate",
          "checked_on":"2026-11-08","channel_url":mod.TARGET,
          "topic":"Відпочинок, кав’ярня-кондитерська"}
    self.assertIs(mod.find_target({"no_results":[item,{"channel_url":"https://t.me/ngo_grants/9"}]}),item)
    with self.assertRaises(RuntimeError):
        mod.find_target({"no_results":[]})
 def test_reconstructed_old_message_only_differs_in_cta(self):
    item={"topic":"Кав’ярня-кондитерська","checked_on":"2026-11-08"}
    with patch.object(mod.app,"VERIFIED_BOT_USERNAME","ngogratsAI_bot"),\
         patch.object(mod.app,"VERIFIED_MAIN_MINI_APP",True):
        newer,older=mod.current_and_legacy_text(item)
    self.assertIn(mod.NEW_LINK,newer)
    self.assertIn(mod.OLD_LINK,older)
    self.assertNotIn("?startapp",older)
    self.assertEqual(newer.replace("🤖 Знайти гранти: "+mod.NEW_LINK,
                   "🤖 Замовити добірку: "+mod.OLD_LINK),older)
    self.assertIn("РЕЗУЛЬТАТ ПОШУКУ",mod.visible_text(older))
 def test_no_action_without_explicit_live_approval(self):
    import os
    with patch.dict(os.environ,{"GITHUB_ACTIONS":"true",
             "GITHUB_REF":"refs/heads/main",
             "GITHUB_REPOSITORY":"Prool-bot/ngo-grants-facebook"},clear=True),\
         patch.object(mod,"telegram") as api,\
         patch.object(mod,"github_api") as gh:
        import asyncio
        with self.assertRaises(RuntimeError):asyncio.run(mod.main())
        api.assert_not_called()
        gh.assert_not_called()
