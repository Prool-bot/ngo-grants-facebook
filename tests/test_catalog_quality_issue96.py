"""Issue #96 regression: real failure patterns, no network/Telegram/AI use."""
import unittest
from datetime import date, datetime, timezone
import json
from pathlib import Path

from catalog_precision_guard import same_grant_round
from catalog_quality_v60 import (
    effective_entry_deadline, first_mandatory_stage_deadline,
    same_day_deadline_expired, qualification_warnings, opportunity_kind,
)
from catalog_presentation_v59 import partition_reviewed_rows
from ngo_grants_ai import dedupe_programmes

TODAY = date(2026, 11, 15)
KAUST = """🔬 KAUST Global Fellowship 2027
📅 Дедлайн першого етапу: 1 жовтня 2026 року
👥 Хто може податися: дослідники з PhD, early-career scientists.
📝 Етап 1 — Concept Note
📆 Етап 2 / Full Proposal — лише за запрошенням
📅 Дедлайн Full Proposal: 15 січня 2027 року
"""
AASM = """AASM Foundation — Strategic Research Grant 2027
📅 Дедлайн LOI: 19 жовтня 2026 року, 23:59 ET
👥 Хто може податися: дослідники з Master's або PhD.
Конкурс проходить у два етапи.
1️⃣ Letter of Intent — до 19 жовтня 2026
LOI є обов'язковим.
2️⃣ Full Application — лише за запрошенням
📅 Дедлайн: 8 березня 2027 року, 23:59 ET
"""
SIMPSON = """George and Cleary Simpson Award for Emerging Researchers
📅 Дедлайн попередніх заявок: 12 листопада 2026 року
📅 Дедлайн основних заявок: 29 січня 2027 року
👥 ХТО МОЖЕ ПОДАТИСЯ? аспіранти та дослідники.
Етап 1. Попередня заявка — до 12 листопада 2026 року.
Необов'язковий етап, який дозволяє отримати попередній відгук.
Етап 2. Основна заявка — 7 грудня 2026 – 29 січня 2027 року.
"""
ASPRS_A = """🛰 ASPRS GEOSPATIAL SCIENCE RESEARCH GRANT 2027 — ГРАНТ $25 000
📅 ДЕДЛАЙН: 1 грудня 2026 року.
👥 ХТО МОЖЕ ПОДАВАТИСЯ:
* студенти магістерських і докторських програм;
* обов'язкова умова — членство в ASPRS у категорії Student Member.
🔗 https://www.asprs.org/Main/Main/Education---Careers/ASPRS-Scholarships.aspx
"""
ASPRS_B = """🌍 ДО 25 000 ДОЛАРІВ НА ДОСЛІДЖЕННЯ У СФЕРІ ГЕОПРОСТОРОВИХ ТЕХНОЛОГІЙ
Американське товариство фотограмметрії та дистанційного зондування (ASPRS)
оголосило конкурс Geospatial Science Research Grant 2027 для магістрантів і докторантів.
📅 ДЕДЛАЙН: 1 грудня 2026 року — подання заявки.
👥 ХТО МОЖЕ ПОДАВАТИСЯ?
* Студенти магістерських програм.
* Обов'язкова умова — членство в ASPRS у статусі Student Member.
🔗 https://www.asprs.org/Main/Education---Careers/ASPRS-Awards-and-Scholarships.aspx
"""
NAF = """🧠 NAF Research Seed Money Grant 2027
📅 Дедлайн LOI: 18 листопада 2026 року
📅 Full Proposal: до 1 березня 2027 року — лише за запрошенням
👥 Хто може податися:
• дослідники, які завершили postdoctoral training понад 5 років тому;
• full-time faculty member, clinician or senior scientist в університеті.
"""
MEOS = """MEOS GEO 2027 — міжнародний Call for Proposals
📅 Дедлайн: 31 січня 2027 року
🌍 Географія: весь світ
👥 Хто може податися: дослідники, інженери, геологи.
Міжнародна конференція, прийом технічних доповідей та abstract.
Переліт, проживання та реєстраційні витрати організатори не покривають —
їх оплачує учасник.
"""


def row(ident, post, deadline, level="direct"):
    return {
        "id": ident, "text": post, "_title": post.splitlines()[0],
        "_deadline": deadline, "_relevance": level, "_score": 10,
    }


class StageDeadlineTests(unittest.TestCase):
    def test_kaust_invitation_only_later_date_is_not_new_entry(self):
        self.assertEqual(date(2026, 10, 1), first_mandatory_stage_deadline(KAUST))
        self.assertEqual(date(2026, 10, 1),
                         effective_entry_deadline(KAUST, date(2027, 1, 15)))
        self.assertEqual(([], []), partition_reviewed_rows(
            [row(2561, KAUST, "2027-01-15")], None, as_of=TODAY))

    def test_aasm_mandatory_loi_is_closed(self):
        self.assertEqual(date(2026, 10, 19), first_mandatory_stage_deadline(AASM))
        self.assertEqual(([], []), partition_reviewed_rows(
            [row(2678, AASM, "2027-03-08")], None, as_of=TODAY))

    def test_optional_preliminary_stage_does_not_close_main_round(self):
        self.assertIsNone(first_mandatory_stage_deadline(SIMPSON))
        direct, conditional = partition_reviewed_rows(
            [row(3357, SIMPSON, "2027-01-29")], None, as_of=TODAY)
        self.assertEqual([3357], [x["id"] for x in direct])
        self.assertFalse(conditional)

    def test_future_required_loi_becomes_displayed_deadline(self):
        self.assertEqual(date(2026, 11, 18),
                         effective_entry_deadline(NAF, date(2027, 3, 1)))

    def test_same_day_cannot_assume_timezone_or_midnight(self):
        post = "📅 Дедлайн: 15 листопада 2026 року, 23:59 EST"
        self.assertFalse(same_day_deadline_expired(
            post, TODAY, datetime(2026, 11, 16, 3, 0, tzinfo=timezone.utc)))
        self.assertTrue(same_day_deadline_expired(
            post, TODAY, datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc)))
        self.assertFalse(same_day_deadline_expired(
            "📅 Дедлайн: 15 листопада 2026 року", TODAY,
            datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc)))


class UniquenessTests(unittest.TestCase):
    def test_asprs_cross_language_and_donor_url_variant_dedupe(self):
        a, b = row(3623, ASPRS_B, "2026-12-01"), row(3590, ASPRS_A, "2026-12-01", "conditional")
        self.assertTrue(same_grant_round(a, b))
        self.assertEqual(1, len(dedupe_programmes([a, b])))
        direct, conditional = partition_reviewed_rows([a, b], None, as_of=TODAY)
        self.assertEqual(1, len(direct) + len(conditional))

    def test_different_awards_same_donor_are_not_merged(self):
        a = row(1, "Parkinson Foundation Visiting Scholar Award", "2026-12-01")
        b = row(2, "Parkinson Foundation Melvin Yahr Research Award", "2026-12-01")
        self.assertFalse(same_grant_round(a, b))
        self.assertEqual(2, len(dedupe_programmes([a, b])))

    def test_different_deadlines_are_distinct_rounds(self):
        a = row(1, ASPRS_A, "2026-12-01")
        b = row(2, ASPRS_B, "2027-12-01")
        self.assertFalse(same_grant_round(a, b))


class EligibilityAndTypeTests(unittest.TestCase):
    def test_unverified_qualified_individual_is_conditional(self):
        facets = {"audience": "individual", "sectors": ["education"]}
        self.assertTrue(qualification_warnings(ASPRS_A, facets))
        direct, conditional = partition_reviewed_rows(
            [row(3623, ASPRS_A, "2026-12-01")], facets, as_of=TODAY)
        self.assertFalse(direct)
        self.assertEqual(1, len(conditional))
        self.assertIn("членство не підтверджене", conditional[0]["_conditional_reason"])

    def test_restrictive_naf_degree_and_job_requirements(self):
        facets = {"audience": "individual", "sectors": ["education"]}
        self.assertTrue(qualification_warnings(NAF, facets))

    def test_meos_is_not_a_funding_grant(self):
        self.assertEqual("conference_cfp", opportunity_kind(MEOS)[0])
        facets = {"audience": "individual", "sectors": ["education"],
                  "funding_format": "grant_only"}
        d, c = partition_reviewed_rows([row(2537, MEOS, "2027-01-31")],
                                       facets, as_of=TODAY)
        self.assertFalse(d or c)
        d, c = partition_reviewed_rows([row(2537, MEOS, "2027-01-31")],
                                       None, as_of=TODAY)
        self.assertFalse(d)
        self.assertEqual("conference_cfp", c[0]["_opportunity_type"])



class ArchivedNovember2026RegressionTests(unittest.TestCase):
    """Match actual channel archive, not just synthetic headline fixtures."""

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1] / "archive" / "telegram" / "months"
        cls.posts = {}
        ids = {2561, 2678, 3357, 3590, 3623, 2490, 2596, 2537}
        for month in ("2026-09", "2026-10"):
            for item in json.loads((root / (month + ".json")).read_text("utf-8")):
                if item.get("id") in ids:
                    cls.posts[item["id"]] = item["text"]
        if set(cls.posts) != ids:
            raise AssertionError("Some archived real QA samples have disappeared")

    def test_real_kaust_aasm_and_optional_simpson(self):
        self.assertEqual(date(2026, 10, 1),
                         first_mandatory_stage_deadline(self.posts[2561]))
        self.assertEqual(date(2026, 10, 19),
                         first_mandatory_stage_deadline(self.posts[2678]))
        self.assertIsNone(first_mandatory_stage_deadline(self.posts[3357]))
        rows = [row(2561, self.posts[2561], "2027-01-15"),
                row(2678, self.posts[2678], "2027-03-08"),
                row(3357, self.posts[3357], "2027-01-29")]
        direct, conditional = partition_reviewed_rows(rows, None, as_of=TODAY)
        self.assertEqual([3357], [x["id"] for x in direct])
        self.assertFalse(conditional)

    def test_real_asprs_duplicate_and_unknown_individual_qualifications(self):
        a = row(3623, self.posts[3623], "2026-12-01", "direct")
        b = row(3590, self.posts[3590], "2026-12-01", "conditional")
        self.assertTrue(same_grant_round(a, b))
        self.assertEqual(1, len(dedupe_programmes([a, b])))
        facets = {"audience": "individual", "sectors": ["education", "it", "social"]}
        direct, conditional = partition_reviewed_rows([a, b], facets, as_of=TODAY)
        self.assertFalse(direct)
        self.assertEqual(1, len(conditional))
        self.assertTrue(conditional[0]["_conditional_reason"])

    def test_real_meos_type_ushmm_and_naf_qualification(self):
        self.assertEqual("conference_cfp",
                         opportunity_kind(self.posts[2537])[0])
        for ident in (2490, 2596):
            self.assertTrue(qualification_warnings(
                self.posts[ident], {"audience": "individual"}))

if __name__ == "__main__":
    unittest.main()
