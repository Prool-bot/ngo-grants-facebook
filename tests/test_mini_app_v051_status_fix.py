from unittest import TestCase
from worker.patch_mini_app_v051_status_fix import patch,OLD,NEW,FLAG,MARKER

class PatchTests(TestCase):
 def test_only_status_readback_changes(self):
    sample=(OLD+"\n"+FLAG+"\n"+
     "NGO_MINI_APP_DIRECT_API_DORMANT_V05\n"+
     "NGO_GRANTS_NATIVE_MINI_APP_V01\n"+
     "NGO_MINI_APP_NAV_FIX_V02\n"+
     "NGO_MINI_APP_DIRECT_START_V03\n"+
     "NGO_MINI_APP_FOP_STATUS_HINT_V04\n"+
     "if(env&&env.__miniAppHttpOrderMode===true)\n"+
     "menu_version:'5.8'")
    fixed=patch(sample)
    self.assertIn(NEW,fixed)
    self.assertIn(MARKER,fixed)
    self.assertEqual(fixed.replace(NEW,OLD).replace("// "+MARKER+"\n",""),sample)
    with self.assertRaises(RuntimeError):patch(fixed)
 def test_other_worker_rejected(self):
    with self.assertRaises(RuntimeError):patch("unknown")
