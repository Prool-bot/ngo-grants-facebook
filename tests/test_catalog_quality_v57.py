"""v5.7 regression tests: seven real catalogue failures and menu contract."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import catalog_guard_v57 as guard
import ngo_grants_ai as app


def grant(title: str, eligible: str, supported: str, *,
          region: str = "Україна", deadline: str = "31 грудня 2026 року") -> str:
    return (f"📚 {title}\n\n📅 ДЕДЛАЙН:\n{deadline}\n\n"
            f"🌍 ГЕОГРАФІЯ:\n{region}\n\n"
            f"👥 ХТО МОЖЕ ПОДАВАТИСЯ?\n{eligible}\n\n"
            f"🎯 ЩО ПІДТРИМУЄТЬСЯ?\n{supported}\n\n"
            "🔗 ОФІЦІЙНА СТОРІНКА: https://example.org/call")


def facets(audience="nonprofit", sectors=("all",), geo="ukraine",
           detail="", role=None, funding=None):
    f={"audience":audience, "sectors":list(sectors), "custom_sector":"",
       "geo":geo, "region":"", "detail":detail}
    if role is not None:
        f["applicant_role"]=role
    if funding is not None:
        f["funding_format"]=funding
    return f


class QualityV57Tests(unittest.TestCase):
    def test_reject_schoolchildren_from_municipal_ngo_catalogue(self):
        f=facets(detail="Гранти для територіальних громад")
        school=grant("Конкурс для школярів з усього світу",
                     "Учні шкіл 8–18 років", "Написання листа меру про громаду")
        self.assertEqual(guard.quality_status(school,f),"reject")

    def test_municipal_vs_ngo_not_conflated(self):
        f=facets(detail="Гранти для територіальних громад")
        municipality=grant("€60 000 на енергетичні концепції громад",
                           "Територіальні громади та муніципалітети",
                           "Гранти муніципалітетам на енергетичні проєкти")
        ngo=grant("Грант для організацій на розвиток територіальних громад",
                  "Громадські та благодійні організації України",
                  "Розвиток громад і соціальні послуги")
        self.assertEqual(guard.quality_status(municipality,f),"reject")
        self.assertEqual(guard.quality_status(ngo,f),"direct")

    def test_women_business_not_every_generic_business_competition(self):
        f=facets(audience="commercial",sectors=("business",),
                 detail="Гранти для жіночого підприємництва")
        generic=grant("EIC STEP Scale Up Defence — технологічні компанії",
                      "Українські технологічні компанії",
                      "Розробки оборонних технологій")
        women=grant("Women TechEU — гранти для жіночих стартапів",
                    "Компанії, стартапи, очолювані жінками",
                    "Підтримка жіночого підприємництва у сфері deep tech")
        self.assertEqual(guard.quality_status(generic,f),"reject")
        self.assertEqual(guard.quality_status(women,f),"direct")

    def test_education_ngo_vs_individual_research(self):
        f=facets(audience="nonprofit",sectors=("education",))
        student=grant("Fung Global Fellows оплачувана дослідницька стипендія",
                      "Науковці та дослідники як фізичні особи",
                      "Індивідуальна стипендія для досліджень")
        self.assertEqual(guard.quality_status(student,f),"reject")

    def test_rights_vs_women_business_voucher(self):
        f=facets(audience="all",sectors=("rights",))
        voucher=grant("Бізнес-ваучери для підприємиць",
                      "Жінки-підприємці",
                      "Підтримка малого бізнесу, ваучери до 250 000 грн")
        rights=grant("Грант на захист прав людини",
                     "Громадські організації",
                     "Правозахисні проєкти та захист прав людини")
        self.assertEqual(guard.quality_status(voucher,f),"reject")
        self.assertEqual(guard.quality_status(rights,f),"direct")

    def test_commercial_request_rejects_NGO_only_program(self):
        f=facets(audience="commercial")
        ngo=grant("WPHF — гранти для громадських організацій",
                  "Жіночі громадські організації. Не допускаються приватні компанії.",
                  "Підтримка участі жінок у мирних процесах")
        self.assertEqual(guard.quality_status(ngo,f),"reject")

    def test_individual_request_rejects_FOP_only(self):
        f=facets(audience="individual",sectors=("agriculture","social"))
        employer=grant("REMARKET — підтримка нових робочих місць",
                       "Юридичні особи та фізичні особи-підприємці (ФОП)",
                       "Гранти роботодавцям для створення робочих місць")
        self.assertEqual(guard.quality_status(employer,f),"reject")

    def test_no_unsupported_partnership_inferred(self):
        f=facets(audience="nonprofit",detail="Кіно",role="either")
        film_company=grant("Кіновиробництво — Creative Europe MEDIA",
                           "Незалежні продюсерські компанії",
                           "Виробництво художніх фільмів")
        self.assertEqual(guard.quality_status(film_company,f),"reject")

    def test_partner_role_needs_named_eligible_organizations(self):
        f=facets(audience="nonprofit",detail="Соціальні проєкти",role="partner")
        collab=grant("Спільні соціальні проєкти",
                     "Громадські організації можуть бути партнерами у консорціумі",
                     "Соціальні проєкти для вразливих груп")
        self.assertEqual(guard.quality_status(collab,f),"conditional")

    def test_real_archived_catalogue_false_positives(self):
        # The failures originated in seven actual PDF catalogues. The test
        # reads the public source archive, not rewritten synthetic snippets.
        archive = {p['id']: p['text'] for p in app.read_archive()}
        samples = [
            (facets(detail="Гранти для територіальних громад"),
             (3524, 3308, 1188, 3527, 3538)),
            (facets(audience="commercial",sectors=("business",),
                    detail="Гранти для жіночого підприємництва"),
             (3441, 3326, 3423, 2713)),
            (facets(audience="nonprofit",sectors=("all",),geo="international"),
             (3282, 3577, 3626)),
            (facets(audience="all",sectors=("rights",)),
             (3592, 1974, 3207)),
            (facets(audience="commercial"),
             (3337, 1672, 3574)),
            (facets(audience="individual",sectors=("agriculture","social")),
             (1020, 3715, 2973)),
        ]
        for f, ids in samples:
            for ident in ids:
                with self.subTest(id=ident, audience=f['audience'],
                                  topic=f.get('detail') or f['sectors']):
                    self.assertIn(ident, archive, "Referenced post missing from archive")
                    self.assertEqual(guard.quality_status(archive[ident],f),
                                     "reject", f"Unexpectedly eligible: {ident}, eligibility={guard.applicant_evidence(archive[ident])[:700]!r}")

    def test_menu_contract_backward_compatible_and_bounded(self):
        legacy=facets(audience="individual",sectors=("agriculture",))
        self.assertEqual(app.normalized_menu_facets(legacy)["audience"],"individual")
        enhanced=facets(audience="municipal",detail="Енергетика",
                        role="either",funding="grant_only")
        normalized=app.normalized_menu_facets(enhanced)
        self.assertEqual(normalized["applicant_role"],"either")
        self.assertEqual(normalized["funding_format"],"grant_only")
        enhanced["applicant_role"]="unknown"
        self.assertIsNone(app.normalized_menu_facets(enhanced))

    def test_menu_questions_before_spending_daily_quota(self):
        f=facets(audience="nonprofit",sectors=("recovery",),
                 detail="Гранти для територіальних громад")
        self.assertIn("го",guard.clarification_questions(f)[0]["question"].casefold())
        f=facets(audience="individual",sectors=("agriculture",))
        self.assertIn("ФОП",guard.clarification_questions(f)[0]["question"])
        f=facets(audience="commercial",sectors=("business",),
                 detail="Гранти для жіночого підприємництва")
        self.assertEqual(guard.clarification_questions(f)[0]["field"],"scope")
        f=facets(audience="nonprofit",sectors=("education","culture","social"))
        self.assertEqual(guard.clarification_questions(f)[0]["field"],"detail")

    def test_split_line_deadline(self):
        self.assertEqual(
            app.deadline_from_post("📅 ДЕДЛАЙН:\n31 грудня 2026 року",date(2026,11,7)),
            date(2026,12,31))
        self.assertIsNone(app.deadline_from_post(
            "📅 Дата події:\n31 грудня 2026 року",date(2026,11,7)))

    def test_ranked_candidates_and_model_cannot_bypass(self):
        good=grant("Грант для ГО на соціальні проєкти",
                   "Громадські та благодійні організації",
                   "Соціальна підтримка вразливих людей")
        bad=grant("REMARKET — грант роботодавцям",
                  "ФОП і зареєстровані підприємства",
                  "Створення нових робочих місць")
        f=facets(audience="nonprofit",sectors=("social",))
        plan=app._menu_plan(f,"Соціальні проєкти")
        # No Cloudflare call is needed when menu detail is empty.
        ranked=app.rank_posts([
            {"id":10001,"text":good},
            {"id":10002,"text":bad},
        ],"Соціальні проєкти",plan,now=date(2026,11,7),facets=f)
        self.assertNotIn(10002,[r["id"] for r in ranked])
        self.assertEqual([r["id"] for r in ranked],[10001])
        with patch.object(app,"cf_ai",return_value={"direct_ids":[10001,10002],
                                                   "conditional_ids":[]}):
            accepted=app.ai_classify("Соціальні проєкти",ranked)
        self.assertNotIn(10002,accepted)


if __name__ == "__main__":
    unittest.main()
