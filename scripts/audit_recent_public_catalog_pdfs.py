"""Read-only content QA for the most recently published real-user PDF catalogs.

Prints only content already published in public @ngo_grants PDFs and technical
aggregate counts. No bot token, D1 reads/writes, AI calls, order creation,
catalog regeneration, Telegram send or Git mutations.
"""
from __future__ import annotations
import json
import os
import re
from collections import Counter
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"ai_catalogs"/"pdfs"
state=json.loads((ROOT/"ai_catalogs/state.json").read_text("utf8"))
real=[x for x in state["published"] if isinstance(x.get("id"),int) and 2**51<=x["id"]<2**51+2**48]
print("REAL_USER_PUBLISHED_CATALOGS="+str(len(real)))
for item in real[-5:]:
    print("=== PUBLIC CATALOG "+str(item["published_on"])+" ===")
    print("CATALOG_TITLE="+item.get("title","")[:175].replace("\n"," "))
    print("PUBLIC_POSTS="+",".join(item.get("channel_urls") or []))
    print("FILTERS="+json.dumps(item.get("facets") or {},ensure_ascii=False,sort_keys=True))
    print("SOURCE_ID_COUNT="+str(len(item.get("post_ids") or [])))
    for f in item.get("pdfs") or [item.get("pdf")]:
        if not f:continue
        p=(ROOT/f).resolve()
        if not str(p).startswith(str(PUBLIC)+"/") or not p.is_file():
            raise SystemExit("Unsafe or missing PDF")
        document=PdfReader(str(p))
        pages=[page.extract_text(extraction_mode="layout") or "" for page in document.pages]
        urls=[]
        for page in document.pages:
            for a in page.get("/Annots",[]) or []:
                try:
                    annotation=a.get_object()
                    action=annotation.get("/A") or {}
                    u=str(action.get("/URI") or "")
                    if u.startswith("https://t.me/ngo_grants/"):urls.append(u)
                except (ValueError,TypeError,AttributeError,KeyError):
                    continue
        counts=Counter(urls)
        text="\n".join(pages)
        print("PUBLIC_PDF="+p.name+" PAGES="+str(len(pages))+" BYTES="+str(p.stat().st_size))
        print("PUBLIC_TG_LINK_ANNOTATIONS="+str(len(urls))+" UNIQUE="+str(len(counts)))
        print("PDF_REPEATED_POST_LINKS="+json.dumps({k:v for k,v in counts.items() if v>1},ensure_ascii=False))
        print("PDF_POST_LINKS="+",".join(sorted(counts)))
        print("TEXT_LENGTH="+str(len(text))+" TEXT_EXTRACTED="+str(bool(text.strip())))
        # Log just the first lines, still enough to inspect which tier and
        # whether PDF contains expected source attributions and key disclaimers.
        for i,line in enumerate(text.splitlines()):
            if i>=65:break
            if line.strip():print("PDF_LINE_"+str(i+1)+"="+line.strip()[:180].replace("\r"," "))
        print("END_PDF")
print("NO_WRITES_NO_AI_NO_TELEGRAM_NO_PERSONAL_DATA=True")
