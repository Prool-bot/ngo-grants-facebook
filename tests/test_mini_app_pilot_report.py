import importlib.util
from pathlib import Path
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "mini_app_pilot_report",ROOT/"scripts"/"mini_app_pilot_report.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PilotTests(TestCase):
 def test_aggregated_recent_success_and_eligibility_warning_without_identity(self):
    state={
      "published":[
        {"published_on":"2026-11-06","facets":{"audience":"individual"}},
        {"published_on":"2026-11-08","v59_document_count":2,
         "facets":{"audience":"nonprofit"}}
      ],
      "no_results":[
        {"checked_on":"2026-11-06","facets":{"audience":"nonprofit"}},
        {"checked_on":"2026-11-08","facets":{"audience":"individual",
          "sectors":["business"]},"topic":"a private topic","chat_id":123}
      ],
      "queue":[],
      "users_days":{"123":"private"}
    }
    out=mod.parse_state(state)
    self.assertEqual(out["new_published_since_cutoff"],1)
    self.assertEqual(out["new_v59_two_tier_catalogs"],1)
    self.assertEqual(out["new_no_results_individual_business"],1)
    self.assertEqual(out["new_no_results_since_cutoff"],1)
    self.assertEqual(out["attribution_to_mini_app"],"unknown")
    self.assertNotIn("private",repr(out))
    self.assertNotIn("123",repr(out))
 def test_pilot_comment_count_and_missing_archive_are_explicit(self):
    self.assertEqual(mod.comment_summary(None)["status"],"archive_not_yet_synced")
    meta={"channel":"ngo_grants","post_count":2,"comment_count":11,"updated_at":"2026-11-08",
          "posts":[{"post_id":3813,"count":3},{"post_id":3800,"count":8}]}
    out=mod.comment_summary(meta)
    self.assertEqual(out["pilot_post_comment_count"],3)
    with self.assertRaises(ValueError):
      mod.comment_summary({**meta,"channel":"other"})
 def test_bad_state_fail_closed(self):
    with self.assertRaises(ValueError):
      mod.parse_state({"published":"invalid","no_results":[],"queue":[]})

if __name__=="__main__":main()
