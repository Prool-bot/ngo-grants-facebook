import importlib.util
import os
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/"worker"))
sp=importlib.util.spec_from_file_location("release_v05",ROOT/"worker"/"release_mini_app_direct_v05_active.py")
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
ENV={
 "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
 "MINI_APP_DIRECT_V05_RELEASE_APPROVED":"YES_ACTIVATE_SIGNED_V05_CANARY",
 "NGO_BOT_GATEWAY_URL":"https://fake.workers.dev"
}
def api(path):
 if path.endswith("/versions/"+mod.NEW):
  return {"resources":{"bindings":[{"name":k,"type":v} for k,v in mod.EXPECTED.items()]}}
 if path.endswith("/deployments"):
  return {"deployments":[{"versions":[{"version_id":mod.OLD,"percentage":100}]}]}
 raise AssertionError("Unexpected API path")

class ReleaseTests(TestCase):
 def invoke(self,fail=False):
  changes=[]
  def fake_deploy(versions,reason):
   changes.append(versions)
  def fake_inspect(gateway,version=None):
   if fail and version is None:raise RuntimeError("production smoke failed")
   return True
  def fake_api(path):
   if path.endswith("/deployments") and len(changes)>=2:
    return {"deployments":[{"versions":[{"version_id":mod.NEW,"percentage":100}]}]}
   return api(path)
  with patch.dict(os.environ,ENV,clear=True),\
       patch.object(mod,"api",side_effect=fake_api),\
       patch.object(mod,"deploy",side_effect=fake_deploy),\
       patch.object(mod,"health",return_value={"menu_version":"5.8"}),\
       patch.object(mod,"forbidden",return_value=True),\
       patch.object(mod,"mini_app_smoke",return_value=True),\
       patch.object(mod,"inspect",side_effect=fake_inspect),\
       patch.object(mod.time,"sleep"):
    if fail:
     with self.assertRaisesRegex(RuntimeError,"production smoke failed"):
      mod.main()
    else:mod.main()
  return changes
 def test_exact_canary_then_full_promote_after_smokes(self):
  events=self.invoke()
  self.assertEqual(events,[
   [(mod.OLD,99.99),(mod.NEW,0.01)],[(mod.NEW,100)]
  ])
 def test_full_release_smoke_failure_restores_100_percent_v04(self):
  events=self.invoke(fail=True)
  self.assertEqual(events[-1],[(mod.OLD,100)])
 def test_incorrect_branch_or_missing_explicit_gate_fails_before_api(self):
  with patch.dict(os.environ,{**ENV,"GITHUB_REF":"refs/heads/not-main"},clear=True),\
       patch.object(mod,"api") as call,patch.object(mod,"deploy") as change:
   with self.assertRaisesRegex(RuntimeError,"release gate missing"):
    mod.main()
  call.assert_not_called()
  change.assert_not_called()
 def test_invalid_signed_data_and_origin_must_have_distinct_error_codes(self):
  called=[]
  def fake_request(gateway,path,version=None,method="GET",body=None,foreign=False):
   called.append((path,method,foreign))
   if path==mod.APP_PATH:
    return 200,{"x-ngo-mini-app-direct-version":"0.5-stage"},(
      'data-native-send="false" data-direct-send="true" '+
      '<script src="https://telegram.org/js/telegram-web-app.js"></script> NGO Grants AI'
    ).encode()
   if method=="POST":
    return (403 if foreign else 401),{},b'{"ok":false,"error":"Denied"}'
   return 405,{},b'{"ok":false}'
  with patch.object(mod,"request",side_effect=fake_request):
   self.assertTrue(mod.inspect(ENV["NGO_BOT_GATEWAY_URL"],mod.NEW))
  self.assertEqual(called[-1],(mod.ORDER_PATH,"GET",False))
  self.assertEqual(len(called),4)
 def test_invalid_hmac_never_allowed_to_create_an_order(self):
  def dangerous_success(gateway,path,version=None,method="GET",body=None,foreign=False):
   if path==mod.APP_PATH:
    return 200,{"x-ngo-mini-app-direct-version":"0.5-stage"},(
      'data-native-send="false" data-direct-send="true" '+
      '<script src="https://telegram.org/js/telegram-web-app.js"></script> NGO Grants AI'
    ).encode()
   if method=="POST":
    return 201,{},b'{"ok":true,"status":"created","order_id":1}'
   return 405,{},b'{"ok":false}'
  with patch.object(mod,"request",side_effect=dangerous_success):
   with self.assertRaisesRegex(RuntimeError,"did not reject invalid Telegram HMAC"):
    mod.inspect(ENV["NGO_BOT_GATEWAY_URL"],mod.NEW)
 def test_wrong_current_version_refuses_release_before_traffic_change(self):
  def changed_api(path):
   if path.endswith("/deployments"):
    return {"deployments":[{"versions":[{"version_id":"unexpected-version","percentage":100}]}]}
   return api(path)
  with patch.dict(os.environ,ENV,clear=True),\
       patch.object(mod,"api",side_effect=changed_api),\
       patch.object(mod,"deploy") as deploy:
   with self.assertRaisesRegex(RuntimeError,"Production Worker changed"):
    mod.main()
  deploy.assert_not_called()
 def test_canary_signature_rejection_failure_restores_old_worker(self):
  changed=[]
  def fake_api(path):
   return api(path)
  with patch.dict(os.environ,ENV,clear=True),\
       patch.object(mod,"api",side_effect=fake_api),\
       patch.object(mod,"deploy",side_effect=lambda versions,reason:changed.append(versions)),\
       patch.object(mod,"health",return_value={"menu_version":"5.8"}),\
       patch.object(mod,"forbidden",return_value=True),\
       patch.object(mod,"mini_app_smoke",return_value=True),\
       patch.object(mod,"inspect",side_effect=RuntimeError("HMAC rejection failed")),\
       patch.object(mod.time,"sleep"):
   with self.assertRaisesRegex(RuntimeError,"HMAC rejection failed"):
    mod.main()
  self.assertEqual(changed,[[(mod.OLD,99.99),(mod.NEW,0.01)],[(mod.OLD,100)]])
if __name__=="__main__":main()
