import importlib.util
from pathlib import Path
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
SP=importlib.util.spec_from_file_location("v05_active",ROOT/"worker"/"activate_mini_app_direct_v05_candidate.py")
module=importlib.util.module_from_spec(SP);SP.loader.exec_module(module)

SRC="""// NGO_GRANTS_NATIVE_MINI_APP_V01
// NGO_MINI_APP_NAV_FIX_V02
// NGO_MINI_APP_DIRECT_START_V03
// NGO_MINI_APP_FOP_STATUS_HINT_V04
// NGO_MINI_APP_DIRECT_API_DORMANT_V05
const __ngoMiniAppDirectRouteEnabled=false;
function tell(env){if(env&&env.__miniAppHttpOrderMode===true)return {message_id:0};}
if(__directPath==="/api/mini-app/order"){ return; }
const health={menu_version:'5.8'};
"""
class ActivationTests(TestCase):
 def test_changes_exactly_one_flag_and_no_queue_code(self):
  result=module.activate(SRC)
  self.assertEqual(result, SRC.replace(module.FLAG_OFF,module.FLAG_ON,1))
  self.assertEqual(result.count(module.FLAG_ON),1)
 def test_refuses_already_enabled_or_wrong_version(self):
  for bad in (SRC.replace(module.FLAG_OFF,module.FLAG_ON),
              SRC.replace("NGO_MINI_APP_FOP_STATUS_HINT_V04","bad"),
              SRC+"// NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01"):
   with self.assertRaises(RuntimeError):module.activate(bad)
if __name__=="__main__":main()
