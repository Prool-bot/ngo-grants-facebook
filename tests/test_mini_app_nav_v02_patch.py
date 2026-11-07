import importlib.util
import json
import subprocess
from pathlib import Path
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
    "patch_live_worker_mini_app_nav_v02",
    ROOT/"worker"/"patch_live_worker_mini_app_nav_v02.py")
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
PREVIEW=(ROOT/"mini-app"/"preview.html").read_text("utf-8")

def original():
    old='<main data-native-send="true"><script src="telegram-web-app.js"></script><script>'+MOD.OLD_BUG+'</script></main>'
    return ('// NGO_GRANTS_NATIVE_MINI_APP_V01\n'
      'const __ngoMiniAppHTML='+json.dumps(old,ensure_ascii=True)+';\n'
      'const __ngoMiniAppBridge={};\n'
      'export default {async fetch(request,env){return new Response("ok",'
      '{headers:{"x-ngo-mini-app-version":"0.1"}});}};\n'
      'const health={menu_version:\'5.8\'};\n')

class NavHotfixTests(TestCase):
 def test_does_not_touch_non_html_worker_code(self):
    old=original()
    new=MOD.patch(old,PREVIEW)
    self.assertIn('NGO_MINI_APP_NAV_FIX_V02',new)
    self.assertIn('"x-ngo-mini-app-version":"0.2"',new)
    self.assertIn("const explicitNext",new)
    self.assertIn('data-native-send=\\\"true\\\"',new)
    self.assertIn('telegram-web-app.js',new)
    self.assertIn('const health={menu_version:',new)
    self.assertIn('export default {async fetch',new)
    result=subprocess.run(["node","--input-type=module","--check"],
       input=new,text=True,capture_output=True)
    self.assertEqual(result.returncode,0,result.stderr)
 def test_cannot_patch_twice(self):
    changed=MOD.patch(original(),PREVIEW)
    with self.assertRaises(RuntimeError):
       MOD.patch(changed,PREVIEW)
 def test_stale_worker_is_rejected_before_any_write(self):
    for source in (
      original().replace("NGO_GRANTS_NATIVE_MINI_APP_V01","old"),
      original().replace(MOD.OLD_BUG,"old implementation"),
      original().replace('"x-ngo-mini-app-version":"0.1"','"x-ngo-mini-app-version":"0.0"'),
    ):
      with self.assertRaises(RuntimeError):
        MOD.patch(source,PREVIEW)
 def test_offline_preview_must_never_be_enabled(self):
    with self.assertRaises(RuntimeError):
      MOD.patch(original(),PREVIEW.replace('data-native-send="false"','data-native-send="true"'))

if __name__=="__main__":main()
