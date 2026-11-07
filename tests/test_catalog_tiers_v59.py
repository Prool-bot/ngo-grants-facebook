import unittest
from datetime import date
from catalog_tiers_v59 import decide_match

POST = """📌 Грант на соціальні послуги для людей з інвалідністю
👥 ХТО МОЖЕ ПОДАВАТИСЯ: громадські організації та благодійні фонди.
🎯 ЩО ПІДТРИМУЄТЬСЯ: соціальні послуги для людей з інвалідністю.
"""
FACETS = {"audience": "nonprofit", "funding_format": "grant_only", "sectors": ["social"]}
TODAY = date(2026, 11, 7)


def match(**overrides):
    kwargs = dict(post=POST, facets=FACETS, as_of=TODAY,
                  deadline=date(2026, 12, 1), rolling_confirmed=False,
                  activity_confirmed=True, geography_confirmed=True,
                  beneficiary_confirmed=True, project_funding_confirmed=True)
    kwargs.update(overrides)
    return decide_match(**kwargs)


class TestTwoTiers(unittest.TestCase):
    def test_verified_grant_is_direct(self):
        self.assertEqual(match().tier, "direct")

    def test_expired_grant_is_rejected_even_if_otherwise_perfect(self):
        self.assertEqual(match(deadline=date(2026, 10, 19)).tier, "reject")

    def test_unknown_deadline_not_rolling(self):
        self.assertEqual(match(deadline=None).tier, "reject")

    def test_confirmed_rolling_acceptance(self):
        self.assertEqual(match(deadline=None, rolling_confirmed=True).tier, "direct")

    def test_mentoring_is_not_grant_only(self):
        self.assertEqual(match(project_funding_confirmed=False).tier, "reject")

    def test_unfunded_activity_rejected_not_conditional(self):
        self.assertEqual(match(activity_confirmed=False).tier, "reject")

    def test_wrong_geography_rejected(self):
        self.assertEqual(match(geography_confirmed=False).tier, "reject")

    def test_target_population_unknown_conditional_with_reason(self):
        result = match(beneficiary_confirmed=False)
        self.assertEqual(result.tier, "conditional")
        self.assertIn("цільової групи", result.reason)
        self.assertTrue(result.missing_verification)

    def test_additional_restriction_is_explained(self):
        result = match(external_restriction="Потрібне співфінансування 20%.")
        self.assertEqual(result.tier, "conditional")
        self.assertIn("20%", result.reason)

    def test_individual_only_is_rejected_for_ngo(self):
        result = match(post="ХТО МОЖЕ ПОДАВАТИСЯ: виключно фізичні особи.\n"
                            "ЩО ПІДТРИМУЄТЬСЯ: соціальні послуги.")
        self.assertEqual(result.tier, "reject")


if __name__ == "__main__":
    unittest.main()
