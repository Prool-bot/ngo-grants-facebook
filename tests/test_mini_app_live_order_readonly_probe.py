import unittest
from scripts.mini_app_live_order_readonly_probe import audit,BASE,END
class OrderAuditTests(unittest.TestCase):
 def test_detects_real_direct_without_exposing_details(self):
    state={"queue":[],"published":[],"no_results":[]}
    incoming={"requests":[{"id":BASE+7,"user_hash":"private","topic":"sensitive"},
                          {"id":234567,"topic":"other"}]}
    r=audit(incoming,state)
    self.assertEqual(r["gateway_pending_direct"],1)
    self.assertEqual(r["gateway_pending_total"],2)
    self.assertTrue(r["direct_order_seen"])
    self.assertNotIn("private",repr(r))
    self.assertNotIn("sensitive",repr(r))
 def test_detects_processed_direct_order_without_pending(self):
    r=audit({"requests":[]},{"queue":[],
      "published":[{"id":BASE+1}],"no_results":[{"id":END-1}]})
    self.assertEqual(r["github_direct_published"],1)
    self.assertEqual(r["github_direct_no_results"],1)
    self.assertTrue(r["direct_order_seen"])
 def test_old_bot_is_not_a_direct_order(self):
    r=audit({"requests":[{"id":1234}]},{"queue":[],"published":[]})
    self.assertFalse(r["direct_order_seen"])
 def test_malformed_response_fails_closed(self):
    with self.assertRaises(RuntimeError):audit({"requests":None},{})
