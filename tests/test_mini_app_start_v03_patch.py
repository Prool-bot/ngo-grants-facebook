import importlib.util
import subprocess
from pathlib import Path
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "patch_start",ROOT/"worker"/"patch_live_worker_mini_app_start_v03.py")
patchmod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patchmod)

SOURCE="""// NGO_GRANTS_NATIVE_MINI_APP_V01
// NGO_MINI_APP_NAV_FIX_V02
const __ngoMiniAppBridge={miniAppKeyboard(){return {keyboard:[]}}};
const __ngoMiniAppOrigin="https://mini.example";
async function __ngoMiniAppTelegramSend(env,id,text,keyboard){return true;}
async function defaultDraft(){return {};}
async function handleTelegram(env,update){
  const __miniMessage=update&&update.message;
  if(__miniMessage && typeof __miniMessage.text==="string" &&
     /^\\/assistant(?:@[A-Za-z0-9_]+)?$/.test(__miniMessage.text.trim()) &&
     __miniMessage.chat && __miniMessage.chat.type==="private"){
    return;
  }
  if(__miniMessage && __miniMessage.web_app_data){
    return await __ngoMiniAppBridge.processMiniAppUpdate(update,env,{});
  }
}
const oldHeader={"x-ngo-mini-app-version":"0.2"};
const health={menu_version:'5.8'};
export default {};
"""

class Tests(TestCase):
    def test_surgical_patch_retains_optional_assistant_and_old_backend(self):
        out=patchmod.patch(SOURCE)
        self.assertEqual(out.count("NGO_MINI_APP_DIRECT_START_V03"),1)
        self.assertIn('Вітаємо в NGO Grants AI',out)
        self.assertIn('text:"/request"',out)
        self.assertIn('text:"/catalogs"',out)
        self.assertIn('/assistant',out)
        self.assertIn('processMiniAppUpdate',out)
        self.assertIn('"x-ngo-mini-app-version":"0.3"',out)
        result=subprocess.run(["node","--input-type=module","--check"],input=out,
            text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_refuses_wrong_baseline_and_repatch(self):
        out=patchmod.patch(SOURCE)
        with self.assertRaises(RuntimeError):patchmod.patch(out)
        for modified in (
            SOURCE.replace("NGO_MINI_APP_NAV_FIX_V02","v0.1"),
            SOURCE.replace('"x-ngo-mini-app-version":"0.2"','"x-ngo-mini-app-version":"0.3"'),
            SOURCE.replace("  const __miniMessage=update&&update.message;","")
        ):
            with self.assertRaises(RuntimeError):patchmod.patch(modified)

if __name__=="__main__":main()
