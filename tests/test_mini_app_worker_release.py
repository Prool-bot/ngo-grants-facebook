import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch,Mock
import os

PATH=Path(__file__).resolve().parents[1]/"worker"/"deploy_worker_mini_app.py"
spec=importlib.util.spec_from_file_location("deploy_worker_mini_app",PATH)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

ENV={
    "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
    "NGO_MINI_APP_RELEASE_APPROVED":"YES_NATIVE_TELEGRAM_CANARY",
    "NGO_BOT_GATEWAY_URL":"https://ngo-grants-instant-bot.example.workers.dev"
}
BINDINGS=[{"name":key,"type":value} for key,value in
          {"BOT_TOKEN":"secret_text","WEBHOOK_SECRET":"secret_text",
           "SYNC_SECRET":"secret_text","DB":"d1","AI":"ai"}.items()]

def api(path,method="GET",payload=None):
    if path.endswith("/deployments"):
        return {"deployments":[{"versions":[{"version_id":"prior-version","percentage":100}]}]}
    if "/versions/" in path:
        return {"resources":{"bindings":BINDINGS}}
    raise RuntimeError("unexpected API path")

class DeploymentTests(TestCase):
    def test_off_main_refuses_before_touching_cloudflare(self):
        with patch.dict(os.environ,{**ENV,"GITHUB_REF":"refs/heads/feature"},clear=True), \
             patch.object(mod,"api") as calls:
            with self.assertRaisesRegex(RuntimeError,"only on GitHub main"):
                mod.main()
        calls.assert_not_called()

    def test_failed_canary_rolls_back_before_users_see_invalid_html(self):
        deployments=[]
        def deploy(versions,explanation):
            deployments.append(versions)
        with patch.dict(os.environ,ENV,clear=True), \
             patch.object(mod,"api",side_effect=api), \
             patch.object(mod,"health",return_value={"menu_version":"5.8"}), \
             patch.object(mod,"forbidden",return_value=True), \
             patch.object(mod,"mini_app_smoke",side_effect=RuntimeError("canary HTML failed")), \
             patch.object(mod,"deploy",side_effect=deploy), \
             patch.object(mod.time,"sleep"):
            with self.assertRaisesRegex(RuntimeError,"canary HTML failed"):
                mod.main()
        self.assertEqual(deployments[0],[("prior-version",99.99),(mod.VERSION,0.01)])
        self.assertEqual(deployments[-1],[("prior-version",100)])

    def test_success_checks_both_canary_and_production(self):
        deployments=[]
        with patch.dict(os.environ,ENV,clear=True), \
             patch.object(mod,"api",side_effect=api), \
             patch.object(mod,"health",return_value={"menu_version":"5.8"}), \
             patch.object(mod,"forbidden",return_value=True), \
             patch.object(mod,"mini_app_smoke",return_value=True) as smoke, \
             patch.object(mod,"deploy",side_effect=lambda *args:deployments.append(args[0])), \
             patch.object(mod.time,"sleep"):
            mod.main()
        self.assertEqual(len(deployments),2)
        self.assertEqual(deployments[0],[("prior-version",99.99),(mod.VERSION,0.01)])
        self.assertEqual(deployments[1],[(mod.VERSION,100)])
        self.assertEqual(smoke.call_count,2)

if __name__=="__main__":main()
