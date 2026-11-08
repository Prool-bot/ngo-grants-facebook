import importlib.util
import os
import json
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
spec=importlib.util.spec_from_file_location(
  "direct_canary",ROOT/"worker"/"verify_mini_app_direct_v05_canary.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ENV={
 "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
 "MINI_APP_V05_CANARY_APPROVED":"YES_DISABLED_001_WITH_ROLLBACK",
 "NGO_BOT_GATEWAY_URL":"https://fake-test.workers.dev"
}

def fake_api(path):
  if path.endswith("/deployments"):
    return {"deployments":[{"versions":[{"version_id":mod.OLD,"percentage":100}]}]}
  if path.endswith("/versions/"+mod.CANDIDATE):
    return {"resources":{"bindings":[{"name":k,"type":v} for k,v in mod.EXPECTED.items()]}}
  raise AssertionError("Unexpected API call")

class Tests(TestCase):
 def invoke(self,fail=False):
    deployments=[]
    def mock_inspect(*args,**kwargs):
      if fail:raise RuntimeError("disabled POST accidentally enabled")
      return True
    def mock_get(gateway,path,version=None,method="GET",payload=None):
      if not version and path==mod.APP_URL:return 404,{},b"Not Found"
      raise AssertionError("Unexpected direct HTTP request")
    with patch.dict(os.environ,ENV,clear=True),\
         patch.object(mod,"api",side_effect=fake_api),\
         patch.object(mod,"deploy",side_effect=lambda versions,msg:deployments.append(versions)),\
         patch.object(mod,"health",return_value={"menu_version":"5.8"}),\
         patch.object(mod,"forbidden",return_value=True),\
         patch.object(mod,"mini_app_smoke",return_value=True),\
         patch.object(mod,"inspect_version",side_effect=mock_inspect),\
         patch.object(mod,"request",side_effect=mock_get),\
         patch.object(mod.time,"sleep"):
      if fail:
        with self.assertRaisesRegex(RuntimeError,"accidentally enabled"):mod.main()
      else:mod.main()
    return deployments
 def test_success_still_unconditionally_restores_100_percent_legacy(self):
    events=self.invoke()
    self.assertEqual(events,[
      [(mod.OLD,99.99),(mod.CANDIDATE,0.01)],[(mod.OLD,100)]
    ])
 def test_failed_staged_verification_must_rollback(self):
    events=self.invoke(fail=True)
    self.assertEqual(events[-1],[(mod.OLD,100)])
 def test_no_main_release_flag_stops_before_any_api_or_traffic(self):
    with patch.dict(os.environ,{**ENV,"GITHUB_REF":"refs/heads/feature"},clear=True),\
         patch.object(mod,"api") as calls,\
         patch.object(mod,"deploy") as deploy:
       with self.assertRaisesRegex(RuntimeError,"authorization missing"):mod.main()
    calls.assert_not_called()
    deploy.assert_not_called()
 def test_html_and_503_refusal_are_required_for_staged_success(self):
    calls=[]
    def request(gateway,path,version=None,method="GET",payload=None):
      calls.append((path,version,method))
      if path==mod.APP_URL:
        return 200,{"x-ngo-mini-app-direct-version":"0.5-stage"},(
          'ngo-grants-miniapp-v1 data-native-send="false" data-direct-send="true" '+
          'https://telegram.org/js/telegram-web-app.js').encode()
      if path==mod.POST_PATH:return 503,{},json.dumps({"ok":False,"error":"Not enabled"}).encode()
      raise AssertionError("Unexpected request")
    with patch.object(mod,"request",side_effect=request):
      self.assertTrue(mod.inspect_version(ENV["NGO_BOT_GATEWAY_URL"],mod.CANDIDATE))
    self.assertEqual(calls[0][0],mod.APP_URL)
    self.assertEqual(calls[1][0],mod.POST_PATH)
    self.assertEqual(calls[1][2],"POST")
    with patch.object(mod,"request",side_effect=lambda *args:(201,{},b'{"ok":true}')):
      with self.assertRaises(RuntimeError):mod.inspect_version(ENV["NGO_BOT_GATEWAY_URL"],mod.CANDIDATE)
if __name__=="__main__":main()
