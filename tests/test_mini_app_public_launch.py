import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
import os,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("mini_app_public_launch",ROOT/"scripts"/"mini_app_public_launch.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ENV={
 "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
 "GITHUB_REPOSITORY":"Prool-bot/ngo-grants-facebook",
 "NGO_MINI_APP_PUBLIC_LAUNCH_APPROVED":"YES_EXISTING_BOT_PUBLIC_TEST",
 "NGO_GRANTS_AI_BOT_TOKEN":"12345678:TEST-only-never-real"
}
IDENTITY={"id":12345678,"username":"ngogratsAI_bot","is_bot":True}
CHANNEL={"type":"channel","username":"ngo_grants"}
MEMBER={"status":"administrator","can_post_messages":True}
CMDS=[
 {"command":"start","description":"Почати"},
 {"command":"request","description":"Замовити"},
 {"command":"catalogs","description":"Каталоги"}
]

def fake_telegram(method,data=None,*,token):
 assert token==ENV["NGO_GRANTS_AI_BOT_TOKEN"]
 if method=="getMe":return IDENTITY
 if method=="getChat":return CHANNEL
 if method=="getChatMember":return MEMBER
 if method=="getMyCommands":return list(CMDS)
 raise AssertionError("unrecognized read method")

class PublicLaunchTests(TestCase):
 def test_post_includes_existing_verified_bot_without_creating_new_one(self):
    html=mod.announcement_text("ngogratsAI_bot")
    self.assertIn("@ngogratsAI_bot",html)
    self.assertIn("<code>/assistant</code>",html)
    self.assertIn("публічне тестування нового інтерфейсу в уже наявному боті",html)
    self.assertLess(len(html),4096)
    with self.assertRaises(ValueError):
        mod.announcement_text("bad invalid bot name")
 def test_write_methods_are_allowlisted(self):
    with self.assertRaises(ValueError):
        mod.bot_write("deleteWebhook",{},token="FAKE")
 def test_refuses_launch_outside_main_or_without_explicit_gate(self):
    with patch.dict(os.environ,{**ENV,"GITHUB_REF":"refs/heads/other"},clear=True):
        with self.assertRaises(RuntimeError):mod.validate_environment()
    with patch.dict(os.environ,{**ENV,"NGO_MINI_APP_PUBLIC_LAUNCH_APPROVED":""},clear=True):
        with self.assertRaises(RuntimeError):mod.validate_environment()
 def test_existing_commands_preserved_then_post_once(self):
    writes=[]
    def fake_write(method,payload,*,token):
        writes.append((method,payload))
        if method=="setMyCommands":
            CMDS[:]=list(payload["commands"])
            return True
        return {"message_id":98765,"chat":{"username":"ngo_grants"}}
    original=list(CMDS)
    with patch.dict(os.environ,ENV,clear=True),\
         patch.object(mod,"telegram",side_effect=fake_telegram),\
         patch.object(mod,"bot_write",side_effect=fake_write),\
         patch.object(mod,"lock_attempt",return_value=("fake-sha",{"status":"attempted"})),\
         patch.object(mod,"mark_published",return_value="https://t.me/ngo_grants/98765"):
        try:mod.main()
        finally:CMDS[:]=original
    self.assertEqual([x[0] for x in writes],["setMyCommands","sendMessage"])
    self.assertEqual(writes[0][1]["commands"][:3],original)
    self.assertEqual(writes[0][1]["commands"][-1]["command"],"assistant")
    self.assertEqual(writes[1][1]["chat_id"],"@ngo_grants")
    self.assertEqual(writes[1][1]["reply_markup"]["inline_keyboard"][0][0]["url"],
                     "https://t.me/ngogratsAI_bot")
 def test_launch_lock_blocks_post_before_mutation(self):
    writes=[]
    existing=list(CMDS)+[{"command":"assistant","description":"Грантовий помічник"}]
    def get(method,data=None,*,token):
        if method=="getMyCommands":return existing
        return fake_telegram(method,data,token=token)
    with patch.dict(os.environ,ENV,clear=True),\
         patch.object(mod,"telegram",side_effect=get),\
         patch.object(mod,"bot_write",side_effect=lambda *a,**k:writes.append(a)),\
         patch.object(mod,"lock_attempt",side_effect=RuntimeError("already attempted")):
        with self.assertRaisesRegex(RuntimeError,"already attempted"):mod.main()
    self.assertEqual(writes,[])
 def test_no_channel_permission_means_no_write(self):
    writes=[]
    def no_right(method,data=None,*,token):
        if method=="getChatMember":return {"status":"member"}
        return fake_telegram(method,data,token=token)
    with patch.dict(os.environ,ENV,clear=True),\
         patch.object(mod,"telegram",side_effect=no_right),\
         patch.object(mod,"bot_write",side_effect=lambda *a,**k:writes.append(a)):
        with self.assertRaisesRegex(RuntimeError,"cannot publish"):mod.main()
    self.assertEqual(writes,[])

if __name__=="__main__":main()
