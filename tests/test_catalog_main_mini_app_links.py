"""Catalog result links must launch the registered Main Mini App, never bot DM."""
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
import ngo_grants_ai as app

VALID="https://t.me/ngogratsAI_bot?startapp=ngo_grants"
OLD="https://t.me/ngogratsAI_bot"

class MainMiniAppResultLinkTests(TestCase):
 def test_identity_activates_direct_link_only_for_verified_registered_bot(self):
  for username, enabled, expected in [
      ("ngogratsAI_bot", True, VALID),
      ("ngogratsAI_bot", False, None),
      ("differentAI_bot", True, None),
  ]:
   with self.subTest(username=username,enabled=enabled), patch.object(
        app, "tg", return_value={"result":{"is_bot":True,"username":username,
                                         "has_main_web_app":enabled}}):
    app.refresh_bot_identity()
    self.assertEqual(app.verified_order_url(),expected)
    self.assertNotEqual(app.verified_order_url(),OLD)
  with patch.object(app,"tg",side_effect=RuntimeError("offline")):
   app.refresh_bot_identity()
   self.assertIsNone(app.verified_order_url())

 def test_no_result_text_uses_direct_and_never_legacy_dm(self):
  item={"id":999,"topic":"Доступні програми для громад","status":"pending",
        "checked_on":"2026-11-08","reason":"no_candidate","engine_version":app.SEARCH_ENGINE_VERSION}
  with patch.object(app,"VERIFIED_BOT_USERNAME","ngogratsAI_bot"),\
       patch.object(app,"VERIFIED_MAIN_MINI_APP",True):
   body=app.public_no_results_text(item)
   self.assertIn("🤖 Знайти гранти:",body)
   self.assertIn(VALID,body)
   self.assertNotIn("🤖 Замовити добірку: "+OLD+"\n",body)
   self.assertTrue(app.order_link_line().endswith(VALID))

 def test_no_result_public_post_has_direct_inline_button(self):
  item={"id":999,"topic":"Гранти для українських громад",
        "status":"pending","checked_on":"2026-11-08",
        "reason":"no_candidate","engine_version":app.SEARCH_ENGINE_VERSION}
  state={"no_results":[item]}
  seen=[]
  def fake_send(method,params):
   seen.append((method,params))
   return {"result":{"message_id":9009}}
  with patch.object(app,"VERIFIED_BOT_USERNAME","ngogratsAI_bot"),\
       patch.object(app,"VERIFIED_MAIN_MINI_APP",True),\
       patch.object(app,"tg",side_effect=fake_send):
   self.assertTrue(app.publish_pending_no_results(
       state,now=datetime(2026,11,8,12,tzinfo=timezone.utc)))
  self.assertEqual(len(seen),1)
  self.assertEqual(seen[0][0],"sendMessage")
  self.assertEqual(seen[0][1]["reply_markup"],
      {"inline_keyboard":[[{"text":"🤖 Знайти гранти","url":VALID}]]})
  self.assertIn(VALID,seen[0][1]["text"])
  self.assertEqual(item["status"],"published")
  self.assertEqual(item["channel_url"],"https://t.me/ngo_grants/9009")

 def test_inactive_app_has_no_old_chat_link_or_button(self):
  item={"topic":"Гранти для українських громад","checked_on":"2026-11-08"}
  with patch.object(app,"VERIFIED_BOT_USERNAME","ngogratsAI_bot"),\
       patch.object(app,"VERIFIED_MAIN_MINI_APP",False):
   self.assertEqual(app.order_link_line(),"")
   self.assertNotIn(OLD,app.public_no_results_text(item))
