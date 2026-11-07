"""Offline PDF smoke checks for the v5.9 separate-tier preview."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from catalog_presentation_v59 import partition_reviewed_rows
from ngo_grants_ai import pdf_catalog

TODAY = date(2026, 11, 7)
FACETS = {"audience": "nonprofit", "sectors": ["social"],
          "funding_format": "grant_only", "detail": "",
          "geo": "ukraine", "region": "", "custom_sector": ""}

def make_post(title):
    return (f"📚 {title}\n\n"
            "📅 ДЕДЛАЙН\n30 листопада 2026 року\n\n"
            "🌍 ГЕОГРАФІЯ\nУкраїна\n\n"
            "👥 ХТО МОЖЕ ПОДАВАТИСЯ\nГромадські організації.\n\n"
            "🎯 ЩО ПІДТРИМУЄТЬСЯ\nСоціальні послуги для людей з інвалідністю.\n\n"
            "💰 ФІНАНСУВАННЯ\nГрант до 100 000 грн.\n")

class TestPreviewPdf(unittest.TestCase):
    def test_direct_and_conditional_pdf_files_are_distinct(self):
        rows = [
            dict(id=900001, text=make_post("Прямий грант"), _relevance="direct",
                 _deadline="2026-11-30", _rolling=False, _title="Прямий грант",
                 _score=10, link="https://t.me/ngo_grants/900001"),
            dict(id=900002, text=make_post("Умовна програма"), _relevance="conditional",
                 _conditional_reason="Потрібне співфінансування 20%.",
                 _deadline="2026-11-30", _rolling=False, _title="Умовна програма",
                 _score=8, link="https://t.me/ngo_grants/900002"),
            dict(id=900003, text=make_post("Прострочено"), _relevance="direct",
                 _deadline="2026-10-01", _rolling=False, _title="Прострочено",
                 _score=6, link="https://t.me/ngo_grants/900003"),
        ]
        direct, conditional = partition_reviewed_rows(rows, FACETS, as_of=TODAY)
        self.assertEqual([900001], [r["id"] for r in direct])
        self.assertEqual([900002], [r["id"] for r in conditional])
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"direct.pdf", Path(tmp)/"conditional.pdf"
            pdf_catalog(a,"ПІДТВЕРДЖЕНІ ГРАНТИ", "Соціальні послуги",
                        direct,TODAY,facets=FACETS)
            pdf_catalog(b,"УМОВНІ МОЖЛИВОСТІ", "Соціальні послуги",
                        conditional,TODAY,facets=FACETS)
            self.assertTrue(a.is_file() and b.is_file())
            direct_text = "\n".join(p.extract_text() for p in PdfReader(str(a)).pages)
            conditional_text = "\n".join(p.extract_text() for p in PdfReader(str(b)).pages)
            self.assertIn("Прямий грант", direct_text)
            self.assertNotIn("Умовна програма", direct_text)
            self.assertIn("Умовна програма", conditional_text)
            self.assertIn("співфінансування 20%", conditional_text)
            self.assertNotIn("Прострочено", direct_text + conditional_text)

if __name__ == "__main__":
    unittest.main()
