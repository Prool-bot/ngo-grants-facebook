import unittest
from datetime import date
from catalog_presentation_v59 import partition_reviewed_rows

TODAY = date(2026, 11, 7)
FACETS = {"audience": "nonprofit", "funding_format": "grant_only", "sectors": ["social"]}
POST = ("Грантова програма на соціальні послуги.\n"
        "ХТО МОЖЕ ПОДАВАТИСЯ: громадські організації.\n"
        "ЩО ПІДТРИМУЄТЬСЯ: фінансування проєктів соціальних послуг.")
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

    def test_professional_prerequisite_does_not_make_artist_indirect(self):
        facets = {"audience": "individual", "sectors": ["culture"],
                  "funding_format": "any"}
        post = (
            "Міжнародний конкурс для художників.\n"
            "👥 ХТО МОЖЕ ПОДАВАТИСЯ: художники віком від 21 року, "
            "які мають професійне портфоліо.\n"
            "📅 ДЕДЛАЙН: 31 грудня 2026 року.\n"
            "🔗 https://example.org/call"
        )
        d,c = partition_reviewed_rows(
            [row(101, text=post)], facets, as_of=TODAY)
        self.assertEqual([101], [x["id"] for x in d])
        self.assertFalse(c)
        self.assertIn("Професійна спеціалізація", d[0]["_funding_warning"])

    def test_required_institutional_pi_is_conditional_not_personal_degree(self):
        facets = {"audience": "individual", "sectors": ["education"]}
        post = (
            "Дослідницький грант для студентів.\n"
            "👥 ХТО МОЖЕ ПОДАВАТИСЯ: студенти PhD.\n"
            "Один викладач має виступити інституційним Principal Investigator (PI).\n"
            "🔗 https://example.org/grants"
        )
        d,c = partition_reviewed_rows(
            [row(102, text=post)], facets, as_of=TODAY)
        self.assertFalse(d)
        self.assertEqual([102], [x["id"] for x in c])
        self.assertIn("інституційний PI", c[0]["_conditional_reason"])

    def test_missing_link_stub_is_conditional_not_confirmed(self):
        facets = {"audience": "individual", "sectors": ["education"]}
        post = (
            "Освітній мінігрант.\n"
            "👥 Хто може податися: студенти університетів.\n"
            "🔗 Офіційна сторінка програми та подача"
        )
        d,c = partition_reviewed_rows(
            [row(103, text=post)], facets, as_of=TODAY)
        self.assertFalse(d)
        self.assertEqual([103], [x["id"] for x in c])
        self.assertIn("посилання", c[0]["_conditional_reason"])

    def test_paid_exhibition_is_labeled_non_grant_and_blocked_for_grant_only(self):
        post = (
            "WILD AT HEART — міжнародний open call для художниць.\n"
            "Відібрані учасниці беруть участь у виставці.\n"
            "👥 ХТО МОЖЕ ПОДАВАТИСЯ: сучасні художниці від 18 років.\n"
            "Вартість участі: $45 за подання заявки.\n"
            "🔗 https://example.org/open-call"
        )
        facets = {"audience": "individual", "sectors": ["culture"],
                  "funding_format": "any"}
        d,c = partition_reviewed_rows(
            [row(104, text=post)], facets, as_of=TODAY)
        self.assertEqual([104], [x["id"] for x in d])
        self.assertFalse(c)
        self.assertEqual("open_call", d[0]["_support_type"])
        self.assertIn("платні", d[0]["_funding_warning"])
        strict = dict(facets, funding_format="grant_only")
        self.assertEqual(([], []), partition_reviewed_rows(
            [row(104, text=post)], strict, as_of=TODAY))

    def test_grant_only_rejects_study_stipend_not_all_opportunities(self):
        post = (
            "Стипендія PhD для молодих дослідників.\n"
            "👥 Хто може подаватися: студенти PhD з усіх країн.\n"
            "Фінансування: щомісячна стипендія на навчання.\n"
            "🔗 https://example.org/scholarship"
        )
        broad = {"audience": "individual", "sectors": ["education"],
                 "funding_format": "any"}
        d, c = partition_reviewed_rows([row(105, text=post)], broad,
                                       as_of=TODAY)
        self.assertEqual([105], [item["id"] for item in d])
        strict = dict(broad, funding_format="grant_only")
        self.assertEqual(([], []), partition_reviewed_rows(
            [row(105, text=post)], strict, as_of=TODAY))

    def test_actual_november_artist_call_is_individual_and_paid(self):
        import json
        from pathlib import Path
        archive = Path(__file__).resolve().parents[1] / "archive/telegram/months/2026-11.json"
        posts = {int(x["id"]): x["text"] for x in json.loads(archive.read_text("utf-8"))}
        facets = {"audience": "individual", "sectors": ["culture"],
                  "funding_format": "any"}
        for ident, expected in ((3654, "open_call"), (3671, "award")):
            d,c = partition_reviewed_rows(
                [row(ident, text=posts[ident], deadline="2026-12-21")],
                facets, as_of=date(2026, 11, 25))
            self.assertEqual([ident], [x["id"] for x in d], ident)
            self.assertFalse(c)
            self.assertEqual(expected, d[0]["_support_type"])
        d,c = partition_reviewed_rows(
            [row(3654, text=posts[3654], deadline="2026-12-21")],
            facets, as_of=date(2026, 11, 25))
        self.assertIn("платні", d[0]["_funding_warning"])

    def test_actual_short_education_post_needs_primary_source(self):
        import json
        from pathlib import Path
        archive = Path(__file__).resolve().parents[1] / "archive/telegram/months/2026-08.json"
        posts = {int(x["id"]): x["text"] for x in json.loads(archive.read_text("utf-8"))}
        facets = {"audience": "individual", "sectors": ["education"],
                  "funding_format": "any"}
        d,c = partition_reviewed_rows(
            [row(1982, text=posts[1982], deadline="2026-12-29")],
            facets, as_of=date(2026, 11, 25))
        self.assertFalse(d)
        self.assertEqual([1982], [x["id"] for x in c])
        self.assertIn("посилання", c[0]["_conditional_reason"])

    def test_no_direct_still_keeps_conditional(self):
        d,c=partition_reviewed_rows(
            [row(9,"conditional",_conditional_reason="Потрібен консорціум.")],
            FACETS,as_of=TODAY)
        self.assertFalse(d)
        self.assertEqual("Потрібен консорціум.",c[0]["_conditional_reason"])

if __name__ == "__main__":
    unittest.main()
