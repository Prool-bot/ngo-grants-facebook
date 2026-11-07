import copy
import unittest
from ngo_grants_v59_delivery import ensure_delivery, deliver_documents, reconcile_document

def manifest():
    return [{"tier":"direct","path":"/tmp/direct.pdf","caption":"Прямі"},
            {"tier":"conditional","path":"/tmp/conditional.pdf","caption":"Умовні"}]

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.state={}
        self.snapshots=[]
        self.save=lambda state: self.snapshots.append(copy.deepcopy(state))
        ensure_delivery(self.state,order_id=10,fingerprint="abc",
                        documents=manifest(),save=self.save)

    def test_manifest_is_saved_before_sending(self):
        self.assertEqual(self.snapshots[0]["v59_deliveries"]["10"]["documents"][0]["status"],"prepared")

    def test_success_sends_two_and_records_ids(self):
        sent=[]
        done,ids=deliver_documents(self.state,order_id=10,
            send=lambda file,caption:(sent.append(file) or len(sent)+100),
            save=self.save)
        self.assertTrue(done)
        self.assertEqual([101,102],ids)
        self.assertEqual(2,len(sent))
        self.assertEqual(["sent","sent"],[d["status"] for d in self.state["v59_deliveries"]["10"]["documents"]])

    def test_repeat_after_success_does_not_resend(self):
        deliver_documents(self.state,order_id=10,send=lambda *_:101,save=self.save)
        done,ids=deliver_documents(self.state,order_id=10,
            send=lambda *_:self.fail("duplicate send"),save=self.save)
        self.assertTrue(done);self.assertEqual([101,101],ids)

    def test_unknown_delivery_failure_is_not_retried(self):
        def fail(*_):
            raise TimeoutError("network timed out after upload")
        with self.assertRaises(TimeoutError):
            deliver_documents(self.state,order_id=10,send=fail,save=self.save)
        self.assertEqual("sending",self.state["v59_deliveries"]["10"]["documents"][0]["status"])
        with self.assertRaisesRegex(RuntimeError,"Повторно не надсилати"):
            deliver_documents(self.state,order_id=10,send=lambda *_:self.fail("duplicate"),save=self.save)

    def test_partial_delivery_does_not_repeat_first(self):
        calls=[]
        def fail_second(*_):
            calls.append(1)
            if len(calls)==2: raise TimeoutError()
            return 1001
        with self.assertRaises(TimeoutError):
            deliver_documents(self.state,order_id=10,send=fail_second,save=self.save)
        self.assertEqual(["sent","sending"],[x["status"] for x in self.state["v59_deliveries"]["10"]["documents"]])
        with self.assertRaises(RuntimeError):
            deliver_documents(self.state,order_id=10,send=lambda *_:self.fail("duplicate"),save=self.save)

    def test_manual_reconciliation_requires_valid_id(self):
        try:
            deliver_documents(self.state,order_id=10,
                send=lambda *_:(_ for _ in ()).throw(TimeoutError()),save=self.save)
        except TimeoutError:
            pass
        with self.assertRaises(ValueError):
            reconcile_document(self.state,order_id=10,tier="direct",message_id=0,save=self.save)
        reconcile_document(self.state,order_id=10,tier="direct",message_id=2001,save=self.save)
        calls=[]
        done,ids=deliver_documents(self.state,order_id=10,
            send=lambda *_:(calls.append(True) or 2002),save=self.save)
        self.assertEqual([2001,2002],ids)
        self.assertEqual(1,len(calls))

    def test_fingerprint_mismatch_rejected(self):
        with self.assertRaises(RuntimeError):
            ensure_delivery(self.state,order_id=10,fingerprint="changed",
                documents=manifest(),save=self.save)

    def test_invalid_duplicate_tiers_rejected(self):
        with self.assertRaises(ValueError):
            ensure_delivery({},order_id=55,fingerprint="x",
                documents=[manifest()[0],manifest()[0]],save=self.save)

if __name__=="__main__":
    unittest.main()
