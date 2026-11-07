"""Recovery from persisted two-file outbox without AI, dedupe or redelivery."""
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import ngo_grants_ai as app

NOW = datetime(2026,11,7,15,tzinfo=timezone.utc)

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.docs = []
        hashes = {}
        for tier in ("direct","conditional"):
            p=self.directory/(tier+".pdf")
            p.write_bytes(("%PDF-1.4 "+tier).encode("utf-8"))
            hashes[tier]=hashlib.sha256(p.read_bytes()).hexdigest()
            self.docs.append({
                "tier":tier,"path":str(p),"caption":tier,
                "status":"prepared","message_id":None
            })
        self.meta={
            "title":"Соціальні послуги","query":"соціальні послуги",
            "facets":{"audience":"nonprofit"},
            "post_ids":[1001,1002],
            "valid_until":"2026-12-01",
            "pdf_sha256":hashes,
            "deadlines_by_tier":{"direct":["2026-12-01"],
                                  "conditional":["2026-12-01"]}
        }
        self.state={"queue":[{"id":123,"topic":"Соціальні послуги"}],
                    "published":[],"v59_deliveries":{"123":{
                         "fingerprint":"abc","metadata":self.meta,
                         "documents":self.docs}}}
        self.entry=self.state["queue"][0]

    def test_resume_one_sent_one_prepared_only_sends_second(self):
        self.docs[0].update(status="sent",message_id=7001,
                            started_at="2026-11-07T10:00:00+00:00")
        sent=[]
        with patch.object(app,"upload_pdf",side_effect=lambda path,caption:
                          (sent.append(path.name) or 7002)), \
             patch.object(app,"durable_checkpoint") as checkpoint:
            result=app.resume_v59_delivery(self.state,self.entry,NOW)
        self.assertTrue(result)
        self.assertEqual(["conditional.pdf"],sent)
        self.assertEqual([7001,7002],
                         [x["message_id"] for x in self.docs])
        self.assertEqual([],self.state["queue"])
        self.assertEqual(1,len(self.state["published"]))
        self.assertEqual(2,checkpoint.call_count)

    def test_all_sent_finishes_without_telegram(self):
        for i,d in enumerate(self.docs):
            d.update(status="sent",message_id=8001+i,
                     started_at="2026-11-07T10:00:00+00:00")
        with patch.object(app,"upload_pdf") as upload, \
             patch.object(app,"durable_checkpoint") as checkpoint:
            self.assertTrue(app.resume_v59_delivery(self.state,self.entry,NOW))
        upload.assert_not_called()
        checkpoint.assert_not_called()
        self.assertEqual([],self.state["queue"])

    def test_ambiguous_sending_stops_without_ai_or_resend(self):
        self.docs[0].update(status="sending",
                            started_at="2026-11-07T10:00:00+00:00")
        with patch.object(app,"upload_pdf") as upload:
            self.assertFalse(app.resume_v59_delivery(self.state,self.entry,NOW))
        upload.assert_not_called()
        self.assertEqual(1,len(self.state["queue"]))

    def test_expired_frozen_grant_blocks_unsent_pdf(self):
        self.meta["deadlines_by_tier"]["conditional"]=["2026-10-01"]
        with patch.object(app,"upload_pdf") as upload:
            with self.assertRaisesRegex(RuntimeError,"закрито"):
                app.resume_v59_delivery(self.state,self.entry,NOW)
        upload.assert_not_called()

    def test_tampered_pdf_fails_before_send(self):
        self.directory.joinpath("direct.pdf").write_bytes(b"tampered")
        with patch.object(app,"upload_pdf") as upload:
            with self.assertRaisesRegex(RuntimeError,"Контрольна сума"):
                app.resume_v59_delivery(self.state,self.entry,NOW)
        upload.assert_not_called()

if __name__=="__main__":
    unittest.main()
