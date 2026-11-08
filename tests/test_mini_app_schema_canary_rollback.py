import importlib.util
import json,os
from pathlib import Path
import tempfile
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SP=importlib.util.spec_from_file_location(
 "schema_canary",ROOT/"worker"/"staged_schema_canary_with_rollback.py")
import sys
sys.path.insert(0,str(ROOT/"worker"))
spec=importlib.util.module_from_spec(SP);SP.loader.exec_module(spec)
NEW="779cb6b9-a6b5-42c1-9671-ff3842fa8833"

class CanaryTests(TestCase):
 def invoke(self,fail=False,wrong_old=False):
    with tempfile.TemporaryDirectory() as temp:
      Path(temp,"ngo-worker-miniapp-stage.json").write_text(json.dumps({
        "staged_only":True,"script":spec.SCRIPT,"version_id":NEW
      }))
      versions=[{"version_id":spec.OLD if not wrong_old else "wrong",
                "percentage":100}]
      expected={"resources":{"bindings":[{"name":k,"type":v}
              for k,v in spec.BINDINGS.items()]}}
      def fake_api(path):
        if path.endswith("/deployments"):
          return {"deployments":[{"versions":versions}]}
        if path.endswith("/versions/"+NEW):return expected
        raise AssertionError("Unexpected API call")
      actions=[]
      def fake_deploy(vers,msg):actions.append(vers)
      with patch.dict(os.environ,{
        "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
        "MINI_APP_SCHEMA_CANARY_APPROVED":"YES_READONLY_001_WITH_ROLLBACK",
        "NGO_BOT_GATEWAY_URL":"https://example.workers.dev",
        "RUNNER_TEMP":temp
      },clear=True),\
           patch.object(spec,"api",side_effect=fake_api),\
           patch.object(spec,"deploy",side_effect=fake_deploy),\
           patch.object(spec,"health",return_value={"menu_version":"5.8"}),\
           patch.object(spec,"forbidden",return_value=True),\
           patch.object(spec,"mini_app_smoke",return_value=True),\
           patch.object(spec,"read_schema",side_effect=RuntimeError("read schema failed") if fail else lambda:True),\
           patch.object(spec.time,"sleep"):
         if fail:
            with self.assertRaisesRegex(RuntimeError,"read schema failed"):spec.main()
         elif wrong_old:
            with self.assertRaisesRegex(RuntimeError,"changed"):spec.main()
         else:spec.main()
      return actions
 def test_even_success_must_roll_back_not_promote(self):
    actions=self.invoke()
    self.assertEqual(actions,[[(spec.OLD,99.99),(NEW,0.01)],[(spec.OLD,100)]])
 def test_failure_must_roll_back(self):
    actions=self.invoke(fail=True)
    self.assertEqual(actions[-1],[(spec.OLD,100)])
 def test_changed_production_refuses_all_changes(self):
    self.assertEqual(self.invoke(wrong_old=True),[])
if __name__=="__main__":main()
