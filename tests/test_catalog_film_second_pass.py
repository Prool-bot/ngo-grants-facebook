import inspect
import unittest

import ngo_grants_ai as ai
from catalog_film_second_pass import broader_film_funding_evidence

TODAY = ai.date(2026, 11, 28)
FACETS = {
    "audience": "nonprofit", "sectors": ["culture", "media", "social"],
    "custom_sector": "Документальне кіно", "detail": "На розвиток кіно",
    "geo": "ukraine", "region": "", "applicant_role": "lead",
    "funding_format": "any",
}
AUDIOVISUAL = (
    "🎬 Конкурс підтримки культури та аудіовізуальних проєктів\n"
    "ЩО ПІДТРИМУЄТЬСЯ: фінансування проєктів створення "
    "аудіовізуальної продукції, відеопроєктів та мистецьких ініціатив.\n"
    "ХТО МОЖЕ ПОДАВАТИСЯ: громадські організації та благодійні фонди.\n"
    "ГЕОГРАФІЯ: Україна.\n"
    "ДЕДЛАЙН: 31 грудня 2026 року.\n"
    "🔗 https://example.org/audiovisual-projects"
)

class SecondPassTests(unittest.TestCase):
    def test_positive_audiovisual_funded_scope(self):
        self.assertTrue(broader_film_funding_evidence(AUDIOVISUAL))

    def test_not_just_applicant_profile(self):
        self.assertFalse(broader_film_funding_evidence(
            "Грант на соціальні послуги.\n"
            "ХТО МОЖЕ ПОДАВАТИСЯ: кінокомпанії, режисери."))

    def test_not_an_exclusion(self):
        self.assertFalse(broader_film_funding_evidence(
            "Грант на розвиток культури.\n"
            "Не підтримуються аудіовізуальні проєкти та кіно."))

    def test_no_generic_culture_without_cinema(self):
        self.assertFalse(broader_film_funding_evidence(
            "Грант на розвиток культури та мистецтва.\n"
            "Хто може подаватися: ГО."))

    def test_second_pass_preserves_grant_only_gate(self):
        f = dict(FACETS, funding_format="grant_only")
        self.assertFalse(ai.grant_only_eligible("Безкоштовне менторство для кінотворців.", f))

    def test_rank_second_pass_retrieves_provisional_film_candidate(self):
        # Normal subject filter remains strict, fallback must not invent rights.
        post = {"id": 99001, "text": AUDIOVISUAL}
        plan = dict(version=ai.SEARCH_ENGINE_VERSION,
                    title="Кінопроєкти", subject="На розвиток кіно",
                    activity="На розвиток кіно", applicant="", requirements=[],
                    topic_groups=[["кіно"]], topic_synonyms=[],
                    semantic_terms=[], query_anchors=[],
                    audience="any", region_root="", regional_focus=False,
                    applicant_required=False, facets=FACETS)
        qa = {}
        selected = ai.rank_posts([post], "На розвиток кіно", plan,
                                 now=TODAY, facets=FACETS,
                                 diagnostics=qa, film_second_pass=True)
        self.assertEqual([99001], [r["id"] for r in selected])
        self.assertTrue(selected[0]["_film_second_pass"])
        self.assertIn("аудіовізуальна", selected[0]["_conditional_reason"])

    def test_other_subjects_not_changed(self):
        self.assertFalse(broader_film_funding_evidence(
            "Гранти на сільськогосподарські теплиці."))

    def test_review_resume_records_second_pass(self):
        source = inspect.getsource(ai.make_one_catalog)
        self.assertIn("keywords['film_second_pass']", source)
        self.assertIn("if keywords.get('film_second_pass')", source)

if __name__ == "__main__":
    unittest.main()
