"""No-side-effect catalogue partitioning for the v5.9 preview.

Only validated, reviewed candidate rows may enter this helper. It does not
search the archive, send Telegram messages, or alter the stored order queue.
"""
from __future__ import annotations

from datetime import date, datetime
from catalog_guard_v57 import quality_status
from catalog_precision_guard import supports_explicit_open_applicants, same_grant_round
from catalog_quality_v60 import (effective_entry_deadline, same_day_deadline_expired,
                                 qualification_warnings, opportunity_kind,
                                 open_for_new_applicants)


def partition_reviewed_rows(rows: list[dict], facets: dict | None,
                            *, as_of: date, as_of_dt: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """Return (direct, conditional); reject expired and unverifiable calls.

    The historical AI tier cannot upgrade a guard-level conditional to direct.
    Conditional rows must carry a user-facing verification reason.
    """
    direct, conditional = [], []
    seen = set()
    accepted: list[dict] = []
    for original in rows:
        row = dict(original)
        ident = row.get("id")
        if not open_for_new_applicants(row.get("text") or "", as_of):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        deadline_raw = row.get("_deadline")
        try:
            deadline = date.fromisoformat(deadline_raw) if deadline_raw else None
        except (ValueError, TypeError):
            continue
        deadline = effective_entry_deadline(row.get("text") or "", deadline)
        if deadline is not None:
            row["_deadline"] = deadline.isoformat()
        if deadline is None and not row.get("_rolling"):
            continue
        if deadline is not None and deadline < as_of:
            continue
        if same_day_deadline_expired(row.get("text") or "", deadline, as_of_dt):
            continue
        # The same programme must never appear in both direct and conditional PDFs.
        if any(same_grant_round(row, previous) for previous in accepted):
            continue
        if facets is not None and not supports_explicit_open_applicants(
                row.get("text") or "", facets.get("detail") or ""):
            continue
        guard = quality_status(row.get("text") or "", facets) if facets is not None else "direct"
        if guard == "reject":
            continue
        level = row.get("_relevance")
        if level not in ("direct", "conditional"):
            continue
        if guard == "conditional" and level == "direct":
            level = "conditional"
        kind, kind_label = opportunity_kind(row.get("text") or "")
        row["_opportunity_type"] = kind
        row["_opportunity_label"] = kind_label
        if kind == "conference_cfp" and facets and facets.get("funding_format") == "grant_only":
            continue
        warnings = qualification_warnings(row.get("text") or "", facets)
        if warnings or kind == "conference_cfp":
            level = "conditional"
            previous_reason = str(row.get("_conditional_reason") or "").strip()
            details = " ".join(warnings + ((kind_label,) if kind == "conference_cfp" else ()))
            row["_conditional_reason"] = " ".join(
                x for x in (previous_reason, details) if x
            )
        accepted.append(row)
        row["_relevance"] = level
        if level == "direct":
            direct.append(row)
        else:
            reason = str(row.get("_conditional_reason") or "").strip()
            if not reason:
                reason = (
                    "Не всі умови участі або відповідність конкретної цільової "
                    "групи підтверджені. Перевірте правила до подання."
                )
            row["_conditional_reason"] = reason
            conditional.append(row)
    return direct, conditional
