"""Strict grant-only checks based on *positive* funding evidence.

Applied at archive prefilter and immediately before PDF output. These
checks cannot independently verify that an archival post is still live.
"""
from __future__ import annotations

import re

NON_GRANT = re.compile(
    r"(?:\b(?:award|prize|mentorship|mentoring|training|workshop)\b|"
    r"премі\w*|нагород\w*|ментор\w*|навчанн\w*|"
    r"пошук\s+(?:потенційних\s+)?партнер\w*|"
    r"expression\s+of\s+interest|\beoi\b)",
    re.I,
)
EXPLICIT_NO_GRANT = re.compile(
    r"(?:не\s+(?:є|передбачає|надає)\s+(?:грантов\w*\s+)?"
    r"(?:грантовим\s+конкурсом|грант\w*|фінансуванн\w*)|"
    r"фінансуванн\w*\s+не\s+гарант\w*|"
    r"не\s+передбач\w*\s+(?:фінансуванн\w*|грант\w*)|"
    r"not\s+(?:a\s+)?grant\s+(?:competition|call|programme|program)|"
    r"no\s+(?:direct\s+)?(?:grant\s+)?funding\s+(?:is\s+)?(?:provided|available)|"
    r"funding\s+(?:is\s+)?not\s+guaranteed)",
    re.I,
)
GRANT_EVIDENCE = re.compile(
    r"(?:\b(?:microgrants?|subgrants?|grants?)\b|"
    r"мікрогрант\w*|грант(?:и|ів|у|ом|ова|ову|овий|ові)?\b|"
    r"безповоротн\w*\s+фінансуванн\w*)", re.I,
)
FUNDED_PROJECT = re.compile(
    r"(?:фінансуванн\w*\s+(?:проєкт\w*|проект\w*|ініціатив\w*)|"
    r"грант(?:и|ів|у|ом|ова|ову|овий|ові)?\s+(?:на|для|до)|"
    r"грантов\w*\s+(?:підтримк\w*|фінансуванн\w*)|"
    r"(?:project|community|small|institutional|organizational|programme|program)\s+grants?\b|"
    r"grants?\s+(?:for|to|up\s+to|of)\b)", re.I,
)


def funding_evidence(text: str) -> tuple[bool, str]:
    """Return (verified-in-text grant mechanism, reason).

    A mere mention in eligibility, FAQ, hashtags, or a negation is insufficient.
    When a funding offer and a partnership/award appear together, don't infer
    grant funding unless project-grant language is explicit.
    """
    raw = str(text or "")
    lines = [x.strip(" *#\t") for x in raw.splitlines() if x.strip()]
    relevant = "\n".join(lines[:16])
    relevant = re.sub(r"https?://\S+|#[^\s]+", " ", relevant)
    if EXPLICIT_NO_GRANT.search(raw):
        return False, "explicit_non_grant_or_unfunded"
    if not GRANT_EVIDENCE.search(relevant):
        return False, "grant_mechanism_missing"
    if NON_GRANT.search("\n".join(lines[:5])) and not FUNDED_PROJECT.search(relevant):
        return False, "non_grant_competition"
    if not FUNDED_PROJECT.search(relevant):
        return False, "project_grant_not_demonstrated"
    return True, "grant_evidence_present"


def grant_only_eligible(text: str, facets: dict | None) -> bool:
    if not facets or facets.get("funding_format") != "grant_only":
        return True
    return funding_evidence(text)[0]
