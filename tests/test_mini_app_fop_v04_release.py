import importlib.util
import os
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
  "deploy_worker_mini_app_fop_v04",
  ROOT/"worker"/"deploy_worker_mini_app_fop_v04.py")
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

STAGED="8a725e8c-0fd2-489f-9163-b6c870302227"
ENV={
  "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
  "NGO_MINI_APP_RELEASE_APPROVED":"YES_FOP_GUIDANCE_V04_CANARY",
  "NGO_BOT_GATEWAY_URL":"https://ngo-grants-test.workers.dev"
}
EXPECTED={"BOT_TOKEN":"secret_text","WEBHOOK_SECRET":"secret_text",
          "SYNC_SECRET":"secret_text","DB":"d1","AI":"ai"}
BINDINGS=[{"name":k,"type":v} for k,v in EXPECTED.items()]
def fake_api(path,method="GET",payload=None):
    if path.endswith("/deployments"):
        return {"deployments":[{"versions":[{
            "version_id":MOD.OLD_VERSION,"percentage":100
        }]}]}
    if "/versions/" in path:
        return {"resources":{"bindings":BINDINGS}}
    raise RuntimeError("Unexpected API path")
class CanaryTests(TestCase):
    def test_requires_explicit_release_and_correct_baseline(self):
        with patch.dict(os.environ,{**ENV,"GITHUB_REF":"refs/heads/feature"},clear=True),\
             patch.object(MOD,"api") as no_api,\
             patch.object(MOD,"VERSION",STAGED):
            with self.assertRaisesRegex(RuntimeError,"only on GitHub main"):
                MOD.main()
            no_api.assert_not_called()
        with patch.dict(os.environ,ENV,clear=True),\
             patch.object(MOD,"VERSION","invalid"),\
             patch.object(MOD,"api") as no_api:
            with self.assertRaisesRegex(RuntimeError,"version ID"):
                MOD.main()
            no_api.assert_not_called()
    def test_canary_failure_restores_previous_worker(self):
        changes=[]
        with patch.dict(os.environ,ENV,clear=True),\
             patch.object(MOD,"VERSION",STAGED),\
             patch.object(MOD,"api",side_effect=fake_api),\
             patch.object(MOD,"health",return_value={"menu_version":"5.8"}),\
             patch.object(MOD,"mini_app_smoke",side_effect=RuntimeError("Start button missing")),\
             patch.object(MOD,"forbidden",return_value=True),\
             patch.object(MOD,"deploy",side_effect=lambda ver,msg:changes.append(ver)),\
             patch.object(MOD.time,"sleep"):
            with self.assertRaisesRegex(RuntimeError,"Start button missing"):
                MOD.main()
        self.assertEqual(changes[0],[(MOD.OLD_VERSION,99.99),(STAGED,0.01)])
        self.assertEqual(changes[-1],[(MOD.OLD_VERSION,100)])
    def test_success_promotes_after_both_smokes(self):
        changes=[]
        with patch.dict(os.environ,ENV,clear=True),\
             patch.object(MOD,"VERSION",STAGED),\
             patch.object(MOD,"api",side_effect=fake_api),\
             patch.object(MOD,"health",return_value={"menu_version":"5.8"}),\
             patch.object(MOD,"mini_app_smoke",return_value=True) as smoke,\
             patch.object(MOD,"forbidden",return_value=True),\
             patch.object(MOD,"deploy",side_effect=lambda ver,msg:changes.append(ver)),\
             patch.object(MOD.time,"sleep"):
            MOD.main()
        self.assertEqual(changes[-1],[(STAGED,100)])
        self.assertEqual(smoke.call_count,2)

if __name__=="__main__":main()
