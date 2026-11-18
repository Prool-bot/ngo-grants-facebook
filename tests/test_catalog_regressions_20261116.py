"""Regression checks using real public archived grant announcements."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import TestCase

from catalog_precision_guard import same_grant_round
from catalog_quality_v60 import (
    first_mandatory_stage_deadline, open_for_new_applicants,
    same_day_deadline_expired,
)
from catalog_presentation_v59 import partition_reviewed_rows
from ngo_grants_ai import dedupe_programmes, deadline_from_post

ROOT=Path(__file__).resolve().parents[1]
IDS={3095,3513,3424,3498,3268,3499,2775,3680,3234,3762,374,3004}
def samples():
    posts={}
    for name in ("2026-05","2026-09","2026-10","2026-11"):
        for p in json.loads((ROOT/"archive/telegram/months"/(name+".json")).read_text("utf8")):
            if int(p["id"]) in IDS:
                posts[int(p["id"])]=p["text"]
    if set(posts)!=IDS:
        raise AssertionError("Missing public archive sample posts")
    return posts


class RealNovemberCatalogRegressions(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts=samples()
    def make(self, id_, deadline):
        return {"id":id_,"text":self.posts[id_],
                "_title":self.posts[id_].splitlines()[0],
                "_deadline":deadline,"_relevance":"conditional","_score":6}
    def test_four_real_cross_language_repeat_pairs(self):
        for one,two,deadline in (
            (3095,3513,"2026-11-16"),
            (3424,3498,"2026-11-20"),
            (3268,3499,"2026-11-29"),
            (2775,3680,"2026-12-15")
        ):
            with self.subTest(ids=(one,two)):
                rows=[self.make(one,deadline),self.make(two,deadline)]
                self.assertTrue(same_grant_round(*rows))
                self.assertEqual(1,len(dedupe_programmes(rows)))
                direct,conditional=partition_reviewed_rows(
                    rows,None,as_of=date(2026,11,16))
                self.assertEqual(1,len(direct)+len(conditional))
    def test_horizon_two_different_topic_codes_not_duplicate(self):
        a,b=self.make(374,"2026-12-01"),self.make(3004,"2026-12-01")
        self.assertFalse(same_grant_round(a,b))
    def test_amee_mandatory_preproposal_first_not_invite_only_full_proposal(self):
        self.assertEqual(date(2027,1,15),
                         first_mandatory_stage_deadline(self.posts[3762]))
        self.assertEqual(date(2027,1,15),min(
            first_mandatory_stage_deadline(self.posts[3762]),
            deadline_from_post(self.posts[3762],date(2026,11,16))))
    def test_unopened_horizon_call_never_marked_open(self):
        self.assertFalse(open_for_new_applicants(self.posts[3234],date(2026,11,16)))
        self.assertEqual(([],[]),partition_reviewed_rows(
            [self.make(3234,"2027-09-22")],None,as_of=date(2026,11,16)))
    def test_live_pipeline_uses_clock_aware_filter_at_every_stage(self):
        """A resumed review and a public PDF must share the same exact cutoff."""
        import inspect
        from ngo_grants_ai import make_one_catalog
        source = inspect.getsource(make_one_catalog)
        self.assertIn(
            'rank_posts(rows, query, keywords, facets=facets, as_of_dt=now)',
            source)
        self.assertIn(
            'picked, facets, as_of=now.astimezone(KYIV).date(), as_of_dt=now)',
            source)

    def test_missing_title_does_not_collapse_distinct_calls_on_donor_url(self):
        from ngo_grants_ai import dedupe_programmes
        root = "https://example.org/funding"
        rows = [
            {"id": 900001, "_title": "", "_deadline": "2026-12-10",
             "text": "Programme Alpha: arts awards", "canonical_urls": [root]},
            {"id": 900002, "_title": "", "_deadline": "2026-12-10",
             "text": "Programme Beta: science awards", "canonical_urls": [root]},
        ]
        self.assertEqual(2, len(dedupe_programmes(rows)))

    def test_same_day_separate_clock_line_is_effective(self):
        post=self.posts[3513]
        deadline=date(2026,11,16)
        self.assertFalse(same_day_deadline_expired(
            post,deadline,datetime(2026,11,16,12,0,tzinfo=timezone.utc)))
        self.assertTrue(same_day_deadline_expired(
            post,deadline,datetime(2026,11,16,18,0,tzinfo=timezone.utc)))
