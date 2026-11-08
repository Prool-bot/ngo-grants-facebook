"""Pure offline tests; never call Telegram or GitHub."""
from pathlib import Path
import importlib.util
import sys
from unittest import TestCase
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location(
    "mini_app_pinned_shortcut_v05",ROOT/"scripts"/"mini_app_pinned_shortcut_v05.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PinnedShortcutTests(TestCase):
 def test_one_button_and_one_visible_label_only(self):
    payload=mod.post_markup()
    self.assertEqual(payload["chat_id"],"@ngo_grants")
    self.assertEqual(payload["message_id"],3813)
    self.assertIn(mod.MAIN_LINK,payload["text"])
    self.assertIn(mod.LABEL,payload["text"])
    self.assertNotIn("/start",payload["text"])
    buttons=payload["reply_markup"]["inline_keyboard"]
    self.assertEqual(buttons,[[{"text":"🤖 Знайти гранти","url":mod.MAIN_LINK}]])
    self.assertEqual(mod.LABEL,"🤖 Знайти гранти")
 def test_no_edit_if_main_channel_or_approval_missing(self):
    with patch.dict("os.environ",{
       "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
       "GITHUB_REPOSITORY":"Prool-bot/ngo-grants-facebook"},clear=True),\
       patch.object(mod,"telegram") as api,\
       patch.object(mod,"github_api") as git:
       with self.assertRaises(RuntimeError):mod.main()
       api.assert_not_called()
       git.assert_not_called()
 def test_no_bot_pin_or_unpin_method_called_in_release(self):
    import inspect
    code=inspect.getsource(mod.main)
    self.assertNotIn("pinChatMessage",code)
    self.assertNotIn("unpinChatMessage",code)
    self.assertNotIn("sendMessage",code)
