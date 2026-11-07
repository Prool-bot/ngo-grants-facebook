"""No-network tests for private v5.9 Telegram staging safety contract."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from contextlib import redirect_stdout
import io
import os

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "v59_private_telegram_staging",ROOT/"scripts"/"v59_private_telegram_staging.py")
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)

TEST_CHAT="-1001234567890"
BOT={"id":456,"is_bot":True,"username":"NgoGrantStagingTestBot"}
CHAT={"id":int(TEST_CHAT),"type":"channel","title":"[TEST] Grants E2E"}
MEMBER={"status":"administrator","can_post_messages":True,"can_edit_messages":True}

class StagingSafetyTests(unittest.TestCase):
    def test_only_private_test_channel_accepted(self):
        staging.check_config(BOT,CHAT,MEMBER,TEST_CHAT)
        with self.assertRaisesRegex(RuntimeError,"public channel"):
            staging.check_config(BOT,dict(CHAT,username="ngo_grants"),MEMBER,TEST_CHAT)
        with self.assertRaisesRegex(RuntimeError,"TEST"):
            staging.check_config(BOT,dict(CHAT,title="Main public"),MEMBER,TEST_CHAT)
        with self.assertRaisesRegex(RuntimeError,"TEST bot"):
            staging.check_config(dict(BOT,username="ngoGrantsAI_bot"),CHAT,MEMBER,TEST_CHAT)
        with self.assertRaisesRegex(RuntimeError,"permissions"):
            staging.check_config(BOT,CHAT,dict(MEMBER,can_edit_messages=False),TEST_CHAT)

    def test_preflight_does_not_send_or_edit(self):
        class MockAPI:
            def __init__(self):self.methods=[]
            def call(self,method,payload,pdf=None):
                self.methods.append(method)
                return {"getMe":BOT,"getChat":CHAT,"getChatMember":MEMBER}[method]
        api=MockAPI()
        with redirect_stdout(io.StringIO()):
            staging.preflight(api,TEST_CHAT)
        self.assertEqual(["getMe","getChat","getChatMember"],api.methods)

    def test_missing_confirmation_fails_before_api(self):
        with self.assertRaisesRegex(RuntimeError,"confirmation"):
            staging.execute(Mock(),TEST_CHAT,Path("/tmp/no-pdfs"),
                            token_confirm="")

    def test_two_synthetic_pdfs_and_private_link(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=Path(temp)
            (paths/"direct.pdf").write_bytes(b"%PDF-1.4 DIRECT")
            (paths/"conditional.pdf").write_bytes(b"%PDF-1.4 CONDITIONAL")
            class MockAPI:
                def __init__(self):self.methods=[];self.edited=None
                def call(self,method,data,pdf=None):
                    self.methods.append(method)
                    if method=="getMe":return BOT
                    if method=="getChat":return CHAT
                    if method=="getChatMember":return MEMBER
                    if method=="sendDocument":
                        return {"message_id":900+len([m for m in self.methods if m=="sendDocument"])}
                    if method=="editMessageReplyMarkup":
                        self.edited=data
                        return {"message_id":901}
                    self.fail(method)
            api=MockAPI()
            with redirect_stdout(io.StringIO()):
                staging.execute(api,TEST_CHAT,paths,
                                token_confirm=staging.CONFIRMATION)
            self.assertEqual(2,api.methods.count("sendDocument"))
            self.assertEqual(1,api.methods.count("editMessageReplyMarkup"))
            self.assertEqual(901,api.edited["message_id"])
            markup=api.edited["reply_markup"]
            self.assertEqual("https://t.me/c/1234567890/902",
                             markup["inline_keyboard"][0][0]["url"])

    def test_no_staging_secret_does_not_connect_to_telegram(self):
        with patch.dict(os.environ,{},clear=True), \
             patch.object(staging,"TelegramTestAPI") as remote, \
             redirect_stdout(io.StringIO()) as printed, \
             patch("sys.argv",["v59_private_telegram_staging.py"]):
            self.assertEqual(2,staging.main())
        remote.assert_not_called()
        self.assertIn("NOT_CONFIGURED",printed.getvalue())

if __name__=="__main__":
    unittest.main()
