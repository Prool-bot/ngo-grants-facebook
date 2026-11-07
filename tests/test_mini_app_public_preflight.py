import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"scripts"/"mini_app_public_preflight.py"
spec=importlib.util.spec_from_file_location("mini_app_public_preflight",PATH)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Tests(TestCase):
 def test_existing_bot_allowed_channel_and_commands(self):
  r=mod.inspect({"id":12345678,"username":"ActualNGoGrantsBot","is_bot":True},
    {"type":"channel","username":"ngo_grants"},
    {"status":"administrator","can_post_messages":True},
    [{"command":"start"},{"command":"assistant"}])
  self.assertTrue(r["channel_can_post"])
  self.assertTrue(r["assistant_already_in_commands"])
 def test_bot_must_be_admin_to_post(self):
  result=mod.inspect({"id":12345678,"username":"ActualNGoGrantsBot","is_bot":True},
    {"type":"channel","username":"ngo_grants"},
    {"status":"member"},[{"command":"start"}])
  self.assertFalse(result["channel_can_post"])
 def test_wrong_channel_denied(self):
  with self.assertRaises(RuntimeError):
   mod.inspect({"id":12345678,"username":"ActualNGoGrantsBot","is_bot":True},
      {"type":"channel","username":"unrelated_channel"},{"status":"creator"},[])
 def test_hardcoded_allowlist_rejects_writes(self):
  with self.assertRaises(ValueError):
   mod.telegram("sendMessage",{"chat_id":"@ngo_grants","text":"not sent"},token="invalid_test_token")
 def test_wrong_bot_identity_denied(self):
  with self.assertRaises(RuntimeError):
   mod.inspect({"id":1,"username":"someone","is_bot":False},
    {"type":"channel","username":"ngo_grants"},{"status":"creator"},[])

if __name__=="__main__":main()
