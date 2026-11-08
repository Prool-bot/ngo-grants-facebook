from pathlib import Path
import importlib.util
import subprocess
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
 "miniapp_direct_patch",ROOT/"worker"/"patch_live_worker_mini_app_direct_v05.py")
# The patch imports the existing stage-only route data.
import sys
sys.path.insert(0,str(ROOT/"worker"))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
from patch_staged_readonly_schema_route import ROUTE_BODY

SYNTHETIC_V04="""// NGO_GRANTS_NATIVE_MINI_APP_V01
// NGO_MINI_APP_NAV_FIX_V02
// NGO_MINI_APP_DIRECT_START_V03
// NGO_MINI_APP_FOP_STATUS_HINT_V04
const health={menu_version:'5.8'};
async function tell(env,chatId,text,markup=null,editId=null){
  return 1;
}
function defaultDraft(){return {stage:'begin'};}
function validatedDraft(d){return d.stage==='confirm';}
async function createRequest(env,chat,userId,d,updateId){return 1;}
export default {async fetch(request,env){
  return new Response("original");
}};
"""

class Tests(TestCase):
 def test_stage_route_reconstruction_is_exact_and_rejects_stale(self):
    stage=SYNTHETIC_V04.replace(
       "export default {async fetch(request,env){",
       "export default {async fetch(request,env){\n"+ROUTE_BODY)
    self.assertEqual(mod.reconstruct_base(stage),SYNTHETIC_V04)
    with self.assertRaises(RuntimeError):
       mod.reconstruct_base(SYNTHETIC_V04)
    with self.assertRaises(RuntimeError):
       mod.reconstruct_base(stage.replace("NGO_MINI_APP_FOP_STATUS_HINT_V04","OTHER"))
 def test_bundle_compiles_and_disables_all_real_orders(self):
    candidate=mod.patch(SYNTHETIC_V04,ROOT)
    self.assertEqual(candidate.count(mod.DIRECT_MARKER),1)
    self.assertEqual(candidate.count(mod.DISABLED_FLAG),1)
    self.assertIn('"/mini-app/direct"',candidate)
    self.assertIn('"/api/mini-app/order"',candidate)
    self.assertIn('if(env&&env.__miniAppHttpOrderMode===true)',candidate)
    self.assertIn('NGO_GRANTS_NATIVE_MINI_APP_V01',candidate)
    self.assertIn('return new Response("original");',candidate)
    self.assertIn('telegram-web-app.js',candidate)
    self.assertIn('data-direct-send=\\\"true\\\"',candidate)
    self.assertNotIn("NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01",candidate)
    checked=subprocess.run(["node","--input-type=module","--check"],
       input=candidate,capture_output=True,text=True)
    self.assertEqual(checked.returncode,0,checked.stderr[:1000])
    with self.assertRaises(RuntimeError):mod.patch(candidate,ROOT)
 def test_missing_or_duplicate_bot_message_handler_refuses_patch(self):
    with self.assertRaises(RuntimeError):
      mod.patch(SYNTHETIC_V04.replace(mod.TELL_ANCHOR,''),ROOT)
    with self.assertRaises(RuntimeError):
      mod.patch(SYNTHETIC_V04.replace(mod.TELL_ANCHOR,mod.TELL_ANCHOR*2),ROOT)

if __name__=="__main__":main()
