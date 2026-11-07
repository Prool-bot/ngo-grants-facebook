"""Mocked end-to-end live-mode delivery, without Telegram or Git writes."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ngo_grants_ai as app

def post(i):
    return dict(id=i,
      text=f"📚 Соціальний грант {i}\n👥 ХТО МОЖЕ ПОДАВАТИСЯ: громадські організації.\n"
           "🎯 ЩО ПІДТРИМУЄТЬСЯ: соціальні послуги.",
      _title=f"Соціальний грант {i}",_score=10-i,
      _deadline="2026-12-01",_rolling=False)

class EndToEndDeliveryTests(unittest.TestCase):
    def test_successful_two_document_delivery_mutates_queue_only_after_both(self):
        state={"queue":[{"id":601,"topic":"Соціальні послуги"}],
               "published":[],"no_results":[]}
        posts=[post(101),post(102)]
        calls=[]
        checkpoints=[]
        def mock_send(path,caption):
            calls.append((path,caption))
            if len(calls)==1:
                self.assertEqual([601],[i["id"] for i in state["queue"]])
                self.assertFalse(state["published"])
            return 9000+len(calls)
        def checkpoint(current_state,**kwargs):
            checkpoints.append(copy.deepcopy(current_state))
        with tempfile.TemporaryDirectory() as dirname, \
             patch.dict(os.environ,{"NGO_GRANTS_V59_LIVE_DELIVERY":"true"}), \
             patch.object(app,"PDF_DIR",Path(dirname)), \
             patch.object(app,"can_publish",return_value=True), \
             patch.object(app,"recent_no_result",return_value=None), \
             patch.object(app,"ai_expand",return_value=("Тест",{"version":0})), \
             patch.object(app,"rank_posts",return_value=posts), \
             patch.object(app,"ai_classify",return_value={101:"direct",102:"conditional"}), \
             patch.object(app,"pdf_catalog") as pdf, \
             patch.object(app,"upload_pdf",side_effect=mock_send), \
             patch.object(app,"durable_checkpoint",side_effect=checkpoint), \
             patch.object(app,"tg") as telegram, \
             patch.object(app,"save_state"):
            pdf.side_effect = lambda path,*args,**kwargs: Path(path).write_bytes(b"%PDF-test")
            result=app.make_one_catalog(state,posts,dry_run=False)
        self.assertTrue(result)
        self.assertEqual(2,len(calls))
        self.assertEqual(2,pdf.call_count)
        self.assertEqual(5,len(checkpoints))
        telegram.assert_called_once()
        self.assertEqual("editMessageReplyMarkup",telegram.call_args.args[0])
        self.assertIn("/9002",str(telegram.call_args.args[1]))
        self.assertEqual([],state["queue"])
        self.assertEqual(1,len(state["published"]))
        self.assertEqual(["https://t.me/ngo_grants/9001",
                          "https://t.me/ngo_grants/9002"],
                         state["published"][0]["channel_urls"])
        self.assertEqual("sending",checkpoints[0]["v59_deliveries"]["601"]["documents"][0]["status"])
        self.assertEqual("sent",checkpoints[1]["v59_deliveries"]["601"]["documents"][0]["status"])

    def test_first_send_exception_leaves_queue_unfinished(self):
        state={"queue":[{"id":602,"topic":"Соціальні послуги"}],
               "published":[],"no_results":[]}
        posts=[post(101)]
        with tempfile.TemporaryDirectory() as dirname, \
             patch.dict(os.environ,{"NGO_GRANTS_V59_LIVE_DELIVERY":"true"}), \
             patch.object(app,"PDF_DIR",Path(dirname)), \
             patch.object(app,"can_publish",return_value=True), \
             patch.object(app,"recent_no_result",return_value=None), \
             patch.object(app,"ai_expand",return_value=("Тест",{"version":0})), \
             patch.object(app,"rank_posts",return_value=posts), \
             patch.object(app,"ai_classify",return_value={101:"direct"}), \
             patch.object(app,"pdf_catalog") as pdf, \
             patch.object(app,"upload_pdf",side_effect=TimeoutError), \
             patch.object(app,"durable_checkpoint"), \
             patch.object(app,"save_state"):
            pdf.side_effect = lambda path,*args,**kwargs: Path(path).write_bytes(b"%PDF-test")
            with self.assertRaises(TimeoutError):
                app.make_one_catalog(state,posts,dry_run=False)
        self.assertEqual([602],[i["id"] for i in state["queue"]])
        self.assertFalse(state["published"])
        self.assertEqual("sending",state["v59_deliveries"]["602"]["documents"][0]["status"])

if __name__=="__main__":
    unittest.main()
