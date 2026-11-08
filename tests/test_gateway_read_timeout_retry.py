import os
import unittest
from unittest.mock import patch

import ngo_grants_ai as bot

ENV={
 "NGO_BOT_GATEWAY_URL":"https://example.workers.dev",
 "NGO_BOT_SYNC_SECRET":"FAKE_TEST_SECRET"
}
class CloudflareRetryTests(unittest.TestCase):
 def test_retry_timeout_only_for_pending_read(self):
  calls=[]
  def fetch(url,*,data=None,headers=None,timeout=0):
   calls.append((url,data,timeout))
   if len(calls)<3:raise TimeoutError("temporary socket read timeout")
   return {"requests":[]}
  with patch.dict(os.environ,ENV,clear=False),\
       patch.object(bot,"http_json",side_effect=fetch),\
       patch.object(bot.time,"sleep") as sleep:
   self.assertEqual(bot.gateway_api("/internal/pending"),{"requests":[]})
  self.assertEqual(len(calls),3)
  self.assertTrue(all(url.endswith("/internal/pending") and data is None for url,data,_ in calls))
  self.assertEqual([call.args for call in sleep.call_args_list],[(1,),(2,)])
 def test_never_retry_post_after_uncertain_result(self):
  with patch.dict(os.environ,ENV,clear=False),\
       patch.object(bot,"http_json",side_effect=TimeoutError("write result unknown")) as fetch,\
       patch.object(bot.time,"sleep") as sleep:
   with self.assertRaises(TimeoutError):
    bot.gateway_api("/internal/sync",{"requests":[]})
  self.assertEqual(fetch.call_count,1)
  sleep.assert_not_called()
 def test_bounded_get_timeout_fails_without_leaking_bearer(self):
  with patch.dict(os.environ,ENV,clear=False),\
       patch.object(bot,"http_json",side_effect=TimeoutError("secret private context")) as fetch,\
       patch.object(bot.time,"sleep"):
   with self.assertRaises(RuntimeError) as error:
    bot.gateway_api("/internal/pending")
  self.assertEqual(fetch.call_count,3)
  self.assertNotIn("FAKE_TEST_SECRET",str(error.exception))
  self.assertNotIn("private context",str(error.exception))
 def test_http_auth_failure_is_not_retried(self):
  with patch.dict(os.environ,ENV,clear=False),\
       patch.object(bot,"http_json",side_effect=RuntimeError("HTTP 403")) as fetch,\
       patch.object(bot.time,"sleep") as sleep:
   with self.assertRaises(RuntimeError):
    bot.gateway_api("/internal/pending")
  self.assertEqual(fetch.call_count,1)
  sleep.assert_not_called()
if __name__=="__main__":unittest.main()
