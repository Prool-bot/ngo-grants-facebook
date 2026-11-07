import unittest
from datetime import date
from catalog_presentation_v59 import partition_reviewed_rows

TODAY = date(2026, 11, 7)
FACETS = {"audience": "nonprofit", "funding_format": "grant_only", "sectors": ["social"]}
POST = ("ХТО МОЖЕ ПОДАВАТИСЯ: громадські організації.\n"
        "ЩО ПІДТРИМУЄТЬСЯ: соціальні послуги.")
def row(ident, level="direct", deadline="2026-12-01", **kwargs):
    return {"id":ident, "text":POST, "_relevance":level,
            "_deadline":deadline, **kwargs}

class TestPartition(unittest.TestCase):
    def test_direct_and_conditional_are_distinct(self):
        direct, cond = partition_reviewed_rows(
            [row(1),row(2,"conditional")],FACETS,as_of=TODAY)
        self.assertEqual([1],[x["id"] for x in direct])
        self.assertEqual([2],[x["id"] for x in cond])
        self.assertTrue(cond[0]["_conditional_reason"])

    def test_expired_is_not_in_either_document(self):
        self.assertEqual(([],[]),partition_reviewed_rows(
            [row(1,deadline="2026-10-19")],FACETS,as_of=TODAY))

    def test_missing_deadline_must_have_rolling_confirmation(self):
        direct, cond=partition_reviewed_rows(
            [row(1,deadline=None),row(2,deadline=None,_rolling=True)],
            FACETS,as_of=TODAY)
        self.assertEqual([2],[x["id"] for x in direct])
        self.assertFalse(cond)

    def test_unverified_applicant_rejected(self):
        bad=row(1,text="ХТО МОЖЕ ПОДАВАТИСЯ: лише фізичні особи.")
        self.assertEqual(([],[]),partition_reviewed_rows(
            [bad],FACETS,as_of=TODAY))

    def test_duplicates_and_unrecognized_tiers_removed(self):
        d,c=partition_reviewed_rows([row(1),row(1),row(3,"unknown")],
                                     FACETS,as_of=TODAY)
        self.assertEqual(1,len(d));self.assertFalse(c)

    def test_no_direct_still_keeps_conditional(self):
        d,c=partition_reviewed_rows(
            [row(9,"conditional",_conditional_reason="Потрібен консорціум.")],
            FACETS,as_of=TODAY)
        self.assertFalse(d)
        self.assertEqual("Потрібен консорціум.",c[0]["_conditional_reason"])

if __name__ == "__main__":
    unittest.main()
