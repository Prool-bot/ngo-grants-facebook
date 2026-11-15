from unittest import TestCase
from worker.patch_mini_app_v053_telegram_fix import patch,OLD,NEW,MARKER
from worker.patch_mini_app_telegram_upstream_probe_v053 import ROUTE
from worker.patch_mini_app_real_session_dryrun import ROUTE as DRY
class FixTests(TestCase):
 def sample(self):
  markers=["NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC","NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY",
  "NGO_MINI_APP_DIRECT_API_DORMANT_V05","NGO_GRANTS_NATIVE_MINI_APP_V01","NGO_MINI_APP_NAV_FIX_V02",
  "NGO_MINI_APP_DIRECT_START_V03","NGO_MINI_APP_FOP_STATUS_HINT_V04",
  "const __ngoMiniAppDirectRouteEnabled=true;","if(env&&env.__miniAppHttpOrderMode===true)","menu_version:'5.8'"]
  return "\n".join(markers)+"\n"+'''
async function checkChannelMembership({userId,token,request=fetch}={}){
 const response=await request("https://api.telegram.org/bot"+token+"/getChatMember",{
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({chat_id:"@ngo_grants",user_id:userId}),
        redirect:"error"
      });
}
/** Select only the receipt metadata; 
'''
 def test_surgical_change_only_and_no_temporary_probe(self):
  src=self.sample()
  for staged in [src,src+ROUTE,src+DRY]:
   fixed=patch(staged)
   self.assertEqual(fixed.replace("// "+MARKER+"\n","").replace(NEW,OLD),src)
   self.assertIn(MARKER,fixed)
   self.assertNotIn(OLD,fixed)
   self.assertNotIn("NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053",fixed)
   with self.assertRaises(RuntimeError):patch(fixed)
 def test_unexpected_source_blocks_release(self):
  with self.assertRaises(RuntimeError):patch("unrelated")
