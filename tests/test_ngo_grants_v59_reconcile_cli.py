"""Operator reconciliation CLI must not publish, fetch bots or process orders."""
import sys
import unittest
from unittest.mock import patch
import ngo_grants_ai as app

class ReconcileCommandTests(unittest.TestCase):
    def test_explicit_three_arguments_reconcile_without_telegram(self):
        initial={"schema_version":1,"queue":[],"published":[],
                 "v59_deliveries":{"77":{"fingerprint":"xyz",
                     "documents":[{"tier":"conditional","path":"x.pdf",
                     "caption":"x","status":"sending","message_id":None}]}}}
        with patch.object(sys,"argv",["ngo_grants_ai.py",
                                      "--v59-reconcile-order","77",
                                      "--v59-reconcile-tier","conditional",
                                      "--v59-reconcile-message","99001"]), \
             patch.object(app,"load_state",return_value=initial), \
             patch.object(app,"durable_checkpoint") as checkpoint, \
             patch.object(app,"upload_pdf") as upload, \
             patch.object(app,"tg") as telegram:
            app.main()
        checkpoint.assert_called_once()
        upload.assert_not_called()
        telegram.assert_not_called()
        doc=initial["v59_deliveries"]["77"]["documents"][0]
        self.assertEqual("sent",doc["status"])
        self.assertEqual(99001,doc["message_id"])

    def test_missing_field_refused_without_mutation(self):
        with patch.object(sys,"argv",["ngo_grants_ai.py",
                                      "--v59-reconcile-order","77"]), \
             patch.object(app,"load_state") as loader:
            with self.assertRaisesRegex(RuntimeError,"три параметри"):
                app.main()
        loader.assert_not_called()

if __name__=="__main__":
    unittest.main()
