import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
import os,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
SP=importlib.util.spec_from_file_location(
    "mini_app_v05_health_readonly",ROOT/"scripts"/"mini_app_v05_health_readonly.py")
MOD=importlib.util.module_from_spec(SP);SP.loader.exec_module(MOD)

class HealthTests(TestCase):
 def test_only_expected_new_version_is_allowed(self):
  MOD.assess_deployment({"deployments":[{
    "versions":[{"version_id":MOD.NEW,"percentage":100}]
  }]})
  with self.assertRaises(RuntimeError):
   MOD.assess_deployment({"deployments":[{
     "versions":[{"version_id":"wrong","percentage":100}]
   }]})
  with self.assertRaises(RuntimeError):
   MOD.assess_deployment({"deployments":[{
     "versions":[{"version_id":MOD.NEW,"percentage":0.01}]
   }]})
 def test_live_check_is_read_only_and_requires_main_registration(self):
  env={
   "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
   "NGO_BOT_GATEWAY_URL":"https://example.workers.dev",
   "NGO_GRANTS_AI_BOT_TOKEN":"123456789:FAKE_TEST_ONLY"
  }
  with patch.dict(os.environ,env,clear=True),\
       patch.object(MOD,"api",return_value={
          "deployments":[{"versions":[{"version_id":MOD.NEW,"percentage":100}]}]
       }) as api,\
       patch.object(MOD,"health",return_value={"menu_version":"5.8"}),\
       patch.object(MOD,"forbidden",return_value=True),\
       patch.object(MOD,"mini_app_smoke",return_value=True),\
       patch.object(MOD,"inspect",return_value=True),\
       patch.object(MOD,"telegram",return_value={
         "is_bot":True,"username":"ngogratsAI_bot","has_main_web_app":True
       }) as bot:
   self.assertTrue(MOD.main())
   self.assertEqual(api.call_count,1)
   self.assertEqual(bot.call_args.args,("getMe",))
 def test_live_main_app_registration_regression_is_alerted(self):
  good={"is_bot":True,"username":"ngogratsAI_bot","has_main_web_app":True}
  MOD.assess_main_registration(good)
  for broken in (
      {**good,"has_main_web_app":False},
      {**good,"has_main_web_app":None},
      {**good,"username":"other_bot"},
      {**good,"is_bot":False},
  ):
   with self.assertRaises(RuntimeError):MOD.assess_main_registration(broken)

 def test_health_cannot_run_from_unapproved_branch(self):
  with patch.dict(os.environ,{"GITHUB_ACTIONS":"true",
     "GITHUB_REF":"refs/heads/unapproved"},clear=True),\
       patch.object(MOD,"api") as api:
   with self.assertRaises(RuntimeError):MOD.main()
   api.assert_not_called()
if __name__=="__main__":main()
