import importlib.util
import subprocess
from pathlib import Path
from unittest import TestCase,main
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("stage_schema",ROOT/"worker"/"patch_staged_readonly_schema_route.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
SOURCE="""// NGO_GRANTS_NATIVE_MINI_APP_V01
// NGO_MINI_APP_NAV_FIX_V02
// NGO_MINI_APP_DIRECT_START_V03
// NGO_MINI_APP_FOP_STATUS_HINT_V04
const health={menu_version:'5.8'};
export default {async fetch(request,env){
  return new Response("original Worker",{status:200});
}};
"""
class Tests(TestCase):
 def test_synthetically_patched_worker_compiles_and_keeps_legacy_fetch(self):
    out=mod.patch(SOURCE)
    self.assertEqual(out.count(mod.MARKER),1)
    self.assertIn("PRAGMA table_info(",out)
    self.assertIn("PRAGMA index_list(",out)
    self.assertIn('new Response("original Worker"',out)
    self.assertIn('"authorization"',out)
    checked=subprocess.run(["node","--input-type=module","--check"],
      input=out,text=True,capture_output=True)
    self.assertEqual(checked.returncode,0,checked.stderr)
 def test_unsafe_baseline_is_rejected(self):
    with self.assertRaises(RuntimeError):mod.patch(SOURCE.replace("NGO_MINI_APP_FOP_STATUS_HINT_V04","missing"))
    with self.assertRaises(RuntimeError):mod.patch(mod.patch(SOURCE))
if __name__=="__main__":main()
