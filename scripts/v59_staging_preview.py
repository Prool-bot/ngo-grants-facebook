"""Offline sample preview for GitHub Actions: no Telegram, AI or secrets."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog_presentation_v59 import partition_reviewed_rows
from ngo_grants_ai import pdf_catalog


def post(id: int, title: str, level: str, deadline: str, reason: str = "") -> dict:
    text = (f"📚 {title}\n\n📅 ДЕДЛАЙН\n30 листопада 2026 року\n"
            "🌍 ГЕОГРАФІЯ\nУкраїна\n"
            "👥 ХТО МОЖЕ ПОДАВАТИСЯ\nГромадські організації.\n"
            "🎯 ЩО ПІДТРИМУЄТЬСЯ\nСоціальні послуги для людей з інвалідністю.\n"
            "💰 ФІНАНСУВАННЯ\nГрант до 100 000 грн.\n")
    return {"id": id, "text":text, "_title":title, "_deadline":deadline,
            "_rolling":False, "_relevance":level, "_score":9,
            "_conditional_reason":reason}


def main() -> None:
    today = date(2026,11,7)
    facets = {"audience":"nonprofit","sectors":["social"],"geo":"ukraine",
              "region":"","detail":"","custom_sector":"",
              "funding_format":"grant_only"}
    rows = [
        post(990001,"Демонстрація підтвердженого гранту","direct","2026-11-30"),
        post(990002,"Демонстрація умовної програми","conditional","2026-11-30",
             "Потрібне підтвердження співфінансування."),
        post(990003,"Демонстрація простроченої програми","direct","2026-10-01")
    ]
    direct, conditional = partition_reviewed_rows(rows,facets,as_of=today)
    assert len(direct)==1 and len(conditional)==1
    directory = ROOT / "output" / "v59-staging-preview"
    directory.mkdir(parents=True,exist_ok=True)
    for tier, selected, label in [
        ("direct",direct,"ПІДТВЕРДЖЕНІ ГРАНТИ — СИНТЕТИЧНІ ДАНІ"),
        ("conditional",conditional,"УМОВНІ МОЖЛИВОСТІ — СИНТЕТИЧНІ ДАНІ")
    ]:
        target=directory/f"{tier}.pdf"
        pdf_catalog(target,label,"Тестовий пошук",selected,today,facets=facets)
        pages=PdfReader(str(target)).pages
        extracted="\n".join(page.extract_text() for page in pages)
        assert selected[0]["_title"] in extracted
        assert "простроченої програми" not in extracted.lower()
        print(f"STAGING_{tier.upper()}_PDF_OK pages={len(pages)} bytes={target.stat().st_size}")
    print("STAGING_NO_TELEGRAM_NO_AI=TRUE")


if __name__=="__main__":
    main()
