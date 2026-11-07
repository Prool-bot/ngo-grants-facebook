"""Quota accounting for partial two-document deliveries."""
import unittest
from datetime import datetime, timezone

import ngo_grants_ai as app

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

def doc(status, at="2026-11-07T10:00:00+00:00"):
    return {"status": status, "started_at": at}

class DailyQuotaTests(unittest.TestCase):
    def test_in_flight_may_have_been_sent(self):
        state={"published":[], "v59_deliveries":{
            "4":{"documents":[doc("sending"),doc("prepared")]}}}
        self.assertEqual(1,app.publication_slots_used(state,NOW))

    def test_two_unfinished_sent_docs_count_two(self):
        state={"published":[], "v59_deliveries":{
            "4":{"documents":[doc("sent"),doc("sending")]}}}
        self.assertEqual(2,app.publication_slots_used(state,NOW))

    def test_completed_delivery_not_double_counted(self):
        state={"published":[{"id":4,"published_on":"2026-11-07",
                             "v59_document_count":2}],
               "v59_deliveries":{"4":{"documents":[doc("sent"),doc("sent")]}}}
        self.assertEqual(2,app.publication_slots_used(state,NOW))

    def test_combined_old_and_unresolved_reaches_quota(self):
        state={"published":[{"id":1,"published_on":"2026-11-07"}],
               "v59_deliveries":{"4":{"documents":[doc("sent"),doc("sending")]}}}
        self.assertEqual(3,app.publication_slots_used(state,NOW))
        self.assertFalse(app.can_publish(state,NOW))

    def test_previous_day_does_not_consume_today(self):
        state={"published":[], "v59_deliveries":{
            "4":{"documents":[doc("sent","2026-11-06T07:00:00+00:00")]}}}
        self.assertEqual(0,app.publication_slots_used(state,NOW))

    def test_corrupt_timestamp_blocks_safely(self):
        state={"published":[], "v59_deliveries":{
            "4":{"documents":[doc("sending","not-a-time")]}}}
        self.assertFalse(app.can_publish(state,NOW))

if __name__=="__main__":
    unittest.main()
