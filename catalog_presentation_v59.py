"""No-side-effect catalogue partitioning for the v5.9 preview.

Only validated, reviewed candidate rows may enter this helper. It does not
search the archive, send Telegram messages, or alter the stored order queue.
"""
from __future__ import annotations

from datetime import date
from catalog_guard_v57 import quality_status


def partition_reviewed_rows(rows: list[dict], facets: dict | None,
                            *, as_of: date) -> tuple[list[dict], list[dict]]:
    """Return (direct, conditional); reject expired and unverifiable calls.

    The historical AI tier cannot upgrade a guard-level conditional to direct.
    Conditional rows must carry a user-facing verification reason.
    """
    direct, conditional = [], []
    seen = set()
    for original in rows:
        row = dict(original)
        ident = row.get("id")
        if ident in seen:
            continue
        seen.add(ident)
        deadline_raw = row.get("_deadline")
        try:
            deadline = date.fromisoformat(deadline_raw) if deadline_raw else None
        except (ValueError, TypeError):
            continue
        if deadline is None and not row.get("_rolling"):
            continue
        if deadline is not None and deadline < as_of:
            continue
        guard = quality_status(row.get("text") or "", facets) if facets is not None else "direct"
        if guard == "reject":
            continue
        level = row.get("_relevance")
        if level not in ("direct", "conditional"):
            continue
        if guard == "conditional" and level == "direct":
            level = "conditional"
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
