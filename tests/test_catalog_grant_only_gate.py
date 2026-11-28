import unittest
from catalog_grant_only_gate import funding_evidence, grant_only_eligible

FACETS = {"funding_format": "grant_only", "audience": "nonprofit"}


class GrantOnlyGateTests(unittest.TestCase):
    def test_project_grant(self):
        self.assertTrue(grant_only_eligible(
            "Грантова програма для ГО.\nФінансування проєктів соціальних послуг.", FACETS))

    def test_award_not_project_funding(self):
        self.assertFalse(grant_only_eligible(
            "Благодійна Україна — конкурс нагород.\nНомінації для ГО.", FACETS))

    def test_partner_search_not_grant(self):
        self.assertFalse(grant_only_eligible(
            "ASB Ukraine — пошук потенційних партнерів. "
            "Це не грантовий конкурс, фінансування не гарантовано.", FACETS))

    def test_mentoring_not_grant(self):
        self.assertFalse(grant_only_eligible(
            "Безкоштовне менторство для ГО, розвиток інституційної спроможності.", FACETS))

    def test_incidental_grant_mention_not_enough(self):
        self.assertFalse(grant_only_eligible(
            "Конкурс нагород для ГО.\nОкремі учасники раніше отримували гранти.", FACETS))

    def test_no_funding_evidence(self):
        self.assertFalse(grant_only_eligible("Інформаційний конкурс для громад.", FACETS))

    def test_project_grant_with_consortium_is_not_rejected(self):
        self.assertTrue(grant_only_eligible(
            "Horizon Europe — project grants for community recovery. "
            "Required consortium of three entities.", FACETS))

    def test_all_opportunities_unaffected(self):
        self.assertTrue(grant_only_eligible("Безкоштовне менторство.", {"funding_format":"any"}))

    def test_negative_statement_overrides_grant_title(self):
        self.assertFalse(funding_evidence(
            "Грантова програма. Не передбачає фінансування проєктів.")[0])


if __name__ == "__main__":
    unittest.main()
