"""Regression audit of the exact 15 Nov 2026 youth catalog sources.

All source text is loaded from the existing public Telegram archive. These
tests NEVER fetch live websites or produce Telegram messages/PDF deliveries.
They protect against (a) duplicated rounds with different headlines, and
(b) 'youth' mentioned only as a recipient of a legal-entity grant.
"""
from __future__ import annotations
import json
from pathlib import Path
from unittest import TestCase
from catalog_precision_guard import (
    same_grant_round, supports_explicit_open_applicants
)
from ngo_grants_ai import dedupe_programmes

ROOT=Path(__file__).resolve().parents[1]
YOUTH_DETAIL="можливості для неформальних молодіжних груп, індивідуальні, для школярів"
SELECTED_IDS=(2255,3028,939,2884,3660,3488,3448,3381,3541,1672)

def public_source_posts()->dict[int,dict]:
    indexed={}
    for month in ("2026-07","2026-08","2026-09","2026-10","2026-11"):
        rows=json.loads((ROOT/"archive"/"telegram"/"months"/(month+".json")).read_text("utf8"))
        for item in rows:
            if item.get("id") in SELECTED_IDS:
                indexed[item["id"]]=item
    if set(indexed)!=set(SELECTED_IDS):
        raise AssertionError("Latest youth PDF source IDs missing from public archive")
    return indexed

def as_ranked(item:dict,deadline:str)->dict:
    return dict(item,
        _deadline=deadline,
        _title=(item.get("text") or "").splitlines()[0],
        _score=10)

class PublishedYouthCatalogRegressionTests(TestCase):
 @classmethod
 def setUpClass(cls):
    cls.posts=public_source_posts()

 def test_same_v4_gen_round_collapses_despite_different_headline(self):
    a=as_ranked(self.posts[2884],"2026-11-15")
    b=as_ranked(self.posts[3028],"2026-11-15")
    self.assertTrue(same_grant_round(a,b))
    self.assertEqual(len(dedupe_programmes([a,b])),1)

 def test_same_creative_europe_film_call_collapses_despite_different_url(self):
    a=as_ranked(self.posts[3381],"2027-03-02")
    b=as_ranked(self.posts[3541],"2027-03-02")
    self.assertTrue(same_grant_round(a,b))
    self.assertEqual(len(dedupe_programmes([a,b])),1)

 def test_different_rounds_same_organizer_not_collapsed(self):
    a=as_ranked(self.posts[2884],"2026-11-15")
    b=as_ranked(self.posts[3028],"2027-04-15")
    self.assertFalse(same_grant_round(a,b))
    self.assertEqual(len(dedupe_programmes([a,b])),2)

 def test_no_unrelated_calls_from_shared_umbrella_website(self):
    a={"_title":"Digital Skills for Schools","_deadline":"2027-03-02",
       "canonical_urls":["https://example.org/grants"],
       "text":"Digital Skills for Schools — grants for school programmes."}
    b={"_title":"Wildlife Restoration Fund","_deadline":"2027-03-02",
       "canonical_urls":["https://example.org/grants"],
       "text":"Wildlife Restoration Fund — grants for ecological programmes."}
    self.assertFalse(same_grant_round(a,b))

 def test_applicant_modes_keep_only_explicit_individual_or_informal_programmes(self):
    accepted=[id for id in SELECTED_IDS
              if supports_explicit_open_applicants(self.posts[id]["text"],YOUTH_DETAIL)]
    self.assertEqual(set(accepted),{2255,3660},
       "A youth beneficiary mention is not an eligible individual or informal applicant")

 def test_generic_nonprofit_requests_keep_existing_broad_workflow(self):
    self.assertTrue(supports_explicit_open_applicants(
        self.posts[3381]["text"],"Гранти для громадських організацій у сфері кіноосвіти"))
    self.assertTrue(supports_explicit_open_applicants(
        self.posts[1672]["text"],"Проєкти для жінок та молоді"))

 def test_no_match_without_verified_applicant_block(self):
    self.assertFalse(supports_explicit_open_applicants(
        "Конкурс для молоді та школярів. Дедлайн 2027.",YOUTH_DETAIL))
