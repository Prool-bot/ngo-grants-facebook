"""Read-only acceptance QA on new REAL user catalog PDFs (after baseline #3940).

Runs after public Git-backed delivery, never reprocesses a user order. Does
not call Cloudflare, Telegram APIs, an LLM or any network endpoint. Uses the
already-public archive and already-published PDF files only.
"""
from __future__ import annotations
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader

from catalog_precision_guard import same_grant_round
from catalog_quality_v60 import (
    effective_entry_deadline, first_mandatory_stage_deadline,
    qualification_warnings, opportunity_kind,
)
from ngo_grants_ai import deadline_from_post, read_archive

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PDFS = (ROOT / "ai_catalogs" / "pdfs").resolve()
BASELINE_LAST_POST = 3940
REAL_MIN = 2 ** 51
REAL_MAX = REAL_MIN + 2 ** 48
POST_LINK = re.compile(r"^https://t\.me/ngo_grants/(\d+)$")


def public_message_ids(item: dict) -> list[int]:
    urls = item.get("channel_urls") or [item.get("channel_url")]
    return [int(m.group(1)) for url in urls if url
            if (m := POST_LINK.fullmatch(str(url)))]


def pdf_source_ids(path: Path) -> tuple[list[int], str]:
    doc = PdfReader(str(path))
    ids = []
    for page in doc.pages:
        for ref in page.get("/Annots", []) or []:
            try:
                annotation = ref.get_object()
                uri = str((annotation.get("/A") or {}).get("/URI") or "")
                match = POST_LINK.fullmatch(uri)
                if match:
                    ids.append(int(match.group(1)))
            except (KeyError, ValueError, TypeError, AttributeError):
                pass
    text = "\n".join(page.extract_text() or "" for page in doc.pages)
    return ids, text


def check_catalog(item: dict, archive: dict[int, str]) -> list[str]:
    errors = []
    order = item.get("id")
    try:
        published = date.fromisoformat(item["published_on"])
    except (KeyError, TypeError, ValueError):
        return ["missing_published_date"]
    docs = item.get("pdfs") or ([item["pdf"]] if item.get("pdf") else [])
    if not docs:
        return ["missing_pdfs"]
    found_ids: list[int] = []
    direct_ids: list[int] = []
    conditional_ids: list[int] = []
    all_text = []
    for raw in docs:
        target = (ROOT / str(raw)).resolve()
        if not target.is_relative_to(PUBLIC_PDFS) or not target.is_file():
            errors.append("missing_or_unsafe_pdf")
            continue
        ids, text = pdf_source_ids(target)
        if not ids:
            errors.append("no_telegram_links_in_pdf")
        all_text.append(text)
        found_ids.extend(ids)
        # Tier inferred solely from the source filename of immutable v5.9 files.
        if target.name.endswith("_direct.pdf"):
            direct_ids.extend(ids)
        elif target.name.endswith("_conditional.pdf"):
            conditional_ids.extend(ids)
    expected_ids = [int(i) for i in item.get("post_ids") or []]
    if Counter(found_ids) != Counter(expected_ids):
        errors.append("pdf_source_links_disagree_with_manifest")
    if len(set(found_ids)) != len(found_ids):
        errors.append("duplicate_archive_post_in_pdf")
    rows = []
    facets = item.get("facets") or {}
    for ident in sorted(set(found_ids)):
        post = archive.get(ident)
        if post is None:
            errors.append(f"missing_public_archive_post:{ident}")
            continue
        mandatory = first_mandatory_stage_deadline(post)
        if mandatory and mandatory < published:
            errors.append(f"expired_mandatory_entry:{ident}")
        if ident in direct_ids and qualification_warnings(post, facets):
            errors.append(f"unverified_individual_qualification_in_direct:{ident}")
        kind, label = opportunity_kind(post)
        if kind == "conference_cfp" and facets.get("funding_format") == "grant_only":
            errors.append(f"unfunded_conference_in_grant_only:{ident}")
        if kind == "conference_cfp" and label not in "\n".join(all_text):
            # Formatting/extraction can suppress a label; warn rather than
            # misreport an otherwise valid grant as a production failure.
            print("QA_TYPE_LABEL_REVIEW=" + str(ident))
        first_date = effective_entry_deadline(post, deadline_from_post(post, published))
        rows.append({"id": ident, "text": post, "_deadline":
                     first_date.isoformat() if first_date else None,
                     "_title": post.splitlines()[0]})
    for idx, left in enumerate(rows):
        for right in rows[idx + 1:]:
            if same_grant_round(left, right):
                errors.append(f"duplicate_grant_programme:{left['id']}:{right['id']}")
    print("QA_ORDER=" + str(order)
          + " PDFS=" + str(len(docs))
          + " LINKS=" + str(len(found_ids))
          + " UNIQUE_ARCHIVE_POSTS=" + str(len(set(found_ids)))
          + " DIRECT=" + str(len(direct_ids))
          + " CONDITIONAL=" + str(len(conditional_ids))
          + " ERRORS=" + str(len(errors)))
    return errors


def main() -> int:
    state = json.loads((ROOT / "ai_catalogs" / "state.json").read_text("utf-8"))
    published = state.get("published") or []
    # Baseline catalogs #3933–3940 are known historical failures and MUST NOT
    # cause a post-fix regression alarm. Never modify or resend them.
    new = [item for item in published
           if isinstance(item.get("id"), int)
           and REAL_MIN <= item["id"] < REAL_MAX
           and any(n > BASELINE_LAST_POST for n in public_message_ids(item))]
    if not new:
        print("QA_NEW_REAL_CATALOGS=0 BASELINE_LAST_POST=3940 KNOWN_PREVIOUS_DEBT=3933-3940")
        return 0
    archive = {int(p["id"]): str(p.get("text") or "") for p in read_archive()}
    problems = []
    for item in new:
        for issue in check_catalog(item, archive):
            problems.append((item["id"], issue))
    for order, issue in problems:
        print(f"QA_ERROR_ORDER={order} REASON={issue}")
    print("QA_NEW_REAL_CATALOGS=" + str(len(new))
          + " QA_ERRORS=" + str(len(problems))
          + " NO_PUBLISH_NO_AI_NO_REPLAY=True")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
