import importlib.util
import json
import subprocess
from pathlib import Path
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
 "mini_app_fop_v04",ROOT/"worker"/"patch_live_worker_mini_app_fop_v04.py")
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)
PREVIEW=(ROOT/"mini-app"/"preview.html").read_text("utf8")

def fake():
 old='<main data-native-send="true"><script src="https://telegram.org/js/telegram-web-app.js"></script><script>const explicitNext=1;</script></main>'
 return ('// NGO_GRANTS_NATIVE_MINI_APP_V01\n'
  'const __ngoMiniAppHTML='+json.dumps(old,ensure_ascii=True)+';\n'
  '// NGO_MINI_APP_NAV_FIX_V02\n'
  'const __ngoMiniAppBridge={};\n'
  '// NGO_MINI_APP_DIRECT_START_V03\n'
  'const oldHeader={"x-ngo-mini-app-version":"0.3"};\n'
  "const health={menu_version:'5.8'};\n"
  'export default {async fetch(){return Response.json({ok:true});}};\n')

class Tests(TestCase):
 def test_only_html_and_version_header_change(self):
  before=fake()
  after=MOD.patch(before,PREVIEW)
  self.assertIn('NGO_MINI_APP_FOP_STATUS_HINT_V04',after)
  self.assertIn('"x-ngo-mini-app-version":"0.4"',after)
  self.assertIn('businessApplicantNeedsReview',after)
  self.assertIn('data-native-send=\\\"true\\\"',after)
  self.assertIn('const __ngoMiniAppBridge={};',after)
  self.assertIn('NGO_MINI_APP_DIRECT_START_V03',after)
  checked=subprocess.run(["node","--input-type=module","--check"],
    input=after,capture_output=True,text=True)
  self.assertEqual(checked.returncode,0,checked.stderr)
 def test_wrong_baseline_and_double_patch_fail_closed(self):
  once=MOD.patch(fake(),PREVIEW)
  with self.assertRaises(RuntimeError):MOD.patch(once,PREVIEW)
  with self.assertRaises(RuntimeError):MOD.patch(
      fake().replace("NGO_MINI_APP_DIRECT_START_V03","x"),PREVIEW)
  with self.assertRaises(RuntimeError):MOD.patch(
      fake().replace('"x-ngo-mini-app-version":"0.3"',
                     '"x-ngo-mini-app-version":"0.4"'),PREVIEW)
 def test_offline_preview_remains_no_send(self):
  with self.assertRaises(RuntimeError):
    MOD.patch(fake(),PREVIEW.replace('data-native-send="false"','data-native-send="true"'))

if __name__=="__main__":main()
