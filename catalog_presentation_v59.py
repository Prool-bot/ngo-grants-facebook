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
                                 funding_profile, open_for_new_applicants,
                                 institutional_application_dependency,
                                 missing_actionable_source)


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
        support_kind, support_label, support_warnings = funding_profile(
            row.get("text") or "")
        row["_opportunity_type"] = kind
        row["_opportunity_label"] = kind_label
        row["_support_type"] = support_kind
        row["_support_label"] = support_label
        if kind == "conference_cfp" and facets and facets.get("funding_format") == "grant_only":
            continue
        # A funding-only request cannot receive an exhibition or paid open call
        # without affirmative project-grant evidence.
        if (facets and facets.get("funding_format") == "grant_only"
                and support_kind in ("open_call", "award", "scholarship",
                                     "fellowship", "residency")):
            # These are valuable for the "any opportunity" menu, but a prize,
            # study stipend or non-cash exhibition is not a project grant.
            continue
        warnings = qualification_warnings(row.get("text") or "", facets)
        # Being a qualified artist, PhD candidate or student is an eligibility
        # requirement, NOT a change in the legal right to apply personally.
        # Keep qualification warnings visible without forcing CONDITIONAL.
        previous_warning = str(row.get("_funding_warning") or "").strip()
        information = " ".join(support_warnings + warnings)
        row["_funding_warning"] = " ".join(
            x for x in (previous_warning, information) if x)
        mandatory_partner = institutional_application_dependency(row.get("text") or "")
        source_missing = missing_actionable_source(row.get("text") or "")
        funding_unconfirmed = bool(
            facets and facets.get("funding_format") == "grant_only"
            and support_kind == "other"
        )
        if (kind == "conference_cfp" or mandatory_partner
                or source_missing or funding_unconfirmed):
            level = "conditional"
            previous_reason = str(row.get("_conditional_reason") or "").strip()
            reasons = [
                kind_label if kind == "conference_cfp" else "",
                mandatory_partner,
                ("Не підтверджено саме проєктне грантове фінансування.")
                if funding_unconfirmed else "",
                ("Не знайдено дієвого посилання на правила організатора; "
                 "право подання не підтверджене першоджерелом.")
                if source_missing else "",
            ]
            row["_conditional_reason"] = " ".join(
                x for x in (previous_reason, *reasons) if x
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
