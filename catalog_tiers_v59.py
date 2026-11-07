"""Evidence-based two-tier catalogue decisions (isolated v5.9 prototype).

This module deliberately does not publish to Telegram or update the live
catalogue. The calling pipeline must validate the requested activity and
geography; this module never turns a missing mandatory fact into eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from catalog_guard_v57 import quality_status


@dataclass(frozen=True)
class MatchDecision:
    tier: str  # direct | conditional | reject
    reason: str
    missing_verification: tuple[str, ...] = ()


def decide_match(
    post: str,
    facets: dict,
    *,
    as_of: date,
    deadline: date | None,
    rolling_confirmed: bool,
    activity_confirmed: bool,
    geography_confirmed: bool,
    beneficiary_confirmed: bool,
    project_funding_confirmed: bool,
    external_restriction: str = "",
) -> MatchDecision:
    """Evaluate evidence after archive parsing and AI review.

    Unknown deadline is not an ongoing call. Missing project-financing proof
    is a hard rejection for grant_only, not an invitation to guess.
    """
    if deadline is not None and deadline < as_of:
        return MatchDecision("reject", "Дедлайн завершився.")
    if deadline is None and not rolling_confirmed:
        return MatchDecision("reject", "Немає підтвердженого відкритого прийому.")
    if not geography_confirmed:
        return MatchDecision("reject", "Географічна відповідність не підтверджена.")
    if not activity_confirmed:
        return MatchDecision("reject", "Фінансування запитаної діяльності не підтверджене.")
    if facets.get("funding_format") == "grant_only" and not project_funding_confirmed:
        return MatchDecision("reject", "Проєктне фінансування не підтверджене.")
    guard = quality_status(post, facets)
    if guard == "reject":
        return MatchDecision("reject", "Не підтверджена відповідність обов'язковим критеріям заявника або тематики.")
    if guard == "direct" and beneficiary_confirmed and not external_restriction:
        return MatchDecision("direct", "Підтверджені заявник, діяльність, цільова група, географія і прийом.")
    reasons: list[str] = []
    checks: list[str] = []
    if guard == "conditional":
        reasons.append("Право подання обраного заявника потребує перевірки.")
        checks.append("Перевірити роль заявника, партнерство та юридичні вимоги.")
    if not beneficiary_confirmed:
        reasons.append("Відповідність конкретної цільової групи не підтверджена.")
        checks.append("Перевірити допустимі категорії бенефіціарів.")
    if external_restriction:
        reasons.append(external_restriction.strip())
        checks.append("Перевірити зазначену додаткову умову за офіційними правилами.")
    if not reasons:
        return MatchDecision("reject", "Немає документованої підстави для умовного рівня.")
    return MatchDecision("conditional", " ".join(reasons), tuple(checks))
