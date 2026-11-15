"""Conservative, source-grounded guardrails for NGO Grants catalog quality.

Two independent failure modes:
* Two Telegram posts describing the SAME *round* of a grant, even if their
  Ukrainian headlines differ, must not occupy two rows of a PDF.
* A query explicitly requesting alternatives for individuals / informal groups
  / school pupils cannot be satisfied by merely mentioning young people as
  beneficiaries of a grant reserved for registered institutional applicants.

This module has NO networking, LLM calls, private-user data, or side effects.
It is not a donor allowlist. Ambiguous broad requests keep the old behavior.
"""
from __future__ import annotations
import re
import unicodedata
from urllib.parse import unquote, urlsplit

_COMMON_ENGLISH = {
    "international", "foundation", "organization", "organisation",
    "european", "europe", "program", "programme", "project", "projects",
    "grant", "grants", "open", "call", "fund", "funding", "the", "for",
    "and", "from", "with", "of", "in", "to", "on", "development",
}
_TITLE_NAME = re.compile(
    r"\b[A-Z][A-Za-z]{3,}(?:\s+(?:(?:and|of|for|the|in|to)\s+)?"
    r"[A-Z][A-Za-z]{3,}){2,7}\b"
)
_BROAD_URL_SLUGS = {
    "grants", "calls", "funding", "opportunities", "apply", "programmes",
    "programs", "open-calls", "calls-for-proposals", "news", "events",
    "applications", "search", "index", "home",
}

def _named_programme_signatures(text: str) -> set[tuple[str, ...]]:
    """Only distinctive multi-word Latin call names, not generic donor names."""
    result = set()
    snippet = str(text or "")[:1600]
    for match in _TITLE_NAME.finditer(snippet):
        words = tuple(w.casefold() for w in re.findall(r"[A-Za-z]{3,}", match.group()))
        rare = tuple(w for w in words if w not in _COMMON_ENGLISH)
        # A shared donor acronym or "Creative Europe" is insufficient.
        if len(rare) >= 2 and len(words) >= 4:
            result.add(rare)
    return result

def _specific_official_paths(row: dict) -> set[str]:
    urls = row.get("canonical_urls") or row.get("urls") or []
    keys = set()
    for raw in urls:
        try:
            parsed = urlsplit(str(raw))
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                continue
            host = parsed.hostname.casefold().removeprefix("www.")
            if host in ("t.me", "telegram.me"):
                continue
            path = unquote(parsed.path).casefold().strip("/")
            last = path.split("/")[-1]
            # A donor home page or broad grants index can represent many calls.
            if not last or last in _BROAD_URL_SLUGS:
                continue
            # The programme-specific slug must contain at least two terms.
            parts = [w for w in re.split(r"[^a-zа-яіїєґ0-9]+", last) if len(w) >= 2]
            if len(parts) < 2:
                continue
            keys.add(host + "/" + path)
        except ValueError:
            continue
    return keys

def same_grant_round(a: dict, b: dict) -> bool:
    """Source-backed duplicate detection with a strict equal round deadline.

    Exact programme-specific official URL OR distinctive named programme in
    both descriptions. Never dedupe on donor host/year or generic subject alone.
    """
    deadline = a.get("_deadline")
    if not deadline or deadline != b.get("_deadline"):
        return False
    if _specific_official_paths(a) & _specific_official_paths(b):
        return True
    left = _named_programme_signatures(a.get("text") or "")
    right = _named_programme_signatures(b.get("text") or "")
    return bool(left & right)

def _detail_modalities(detail: str) -> set[str]:
    q = unicodedata.normalize("NFKC", str(detail or "")).casefold()
    types = set()
    if re.search(
        r"(?:неформальн\w*\s+(?:молодіжн\w*\s+)?груп\w*|"
        r"ініціативн\w*\s+груп\w*|молодіжн\w*\s+команд\w*|"
        r"informal\s+(?:youth\s+)?groups?)", q
    ):
        types.add("informal")
    if re.search(r"індивідуальн\w*|фізичн\w*\s+особ\w*|"
                 r"individual(?:s|\s+applicants?)", q):
        types.add("individual")
    if re.search(r"школяр\w*|\bучн(?:і|ів|ям|ями)\b|"
                 r"schoolchildren|school\s+pupils?", q):
        types.add("pupil")
    return types

_ELIGIBLE_HEADING = re.compile(
    r"хто\s+мож(?:е|уть)\s+(?:пода\w*|брати\s+участ)|"
    r"хто\s+пода\w*|для\s+кого|кому\s+доступн|"
    r"eligible\s+(?:applicants?|participants?)|who\s+can\s+apply",
    re.I,
)
_INFORMAL = re.compile(
    r"неформальн\w*\s+(?:молодіжн\w*\s+)?груп\w*|"
    r"ініціативн\w*\s+груп\w*|молодіжн\w*\s+команд\w*|"
    r"informal\s+(?:youth\s+)?groups?|grassroots\s+groups?",
    re.I,
)
_INDIVIDUAL = re.compile(
    r"фізичн\w*\s+особ\w*|індивідуальн\w*\s+(?:особ\w*|"
    r"заявник\w*|учасник\w*)|individual\s+applicants?|"
    r"\bindividuals\b|\bprivate\s+persons\b",
    re.I,
)
_SCHOOL_PUPIL = re.compile(
    r"школяр\w*|\bучн(?:і|ів|ям|ями)\b|"
    r"schoolchildren|school\s+pupils?|high\s+school\s+students?",
    re.I,
)

def _applicant_evidence(post: str) -> str:
    """Only the applicant-eligibility block, not project beneficiary mentions."""
    lines = str(post or "").splitlines()
    results = []
    for i, line in enumerate(lines):
        clean = re.sub(r"^[^\w]+", "", line).strip()
        if _ELIGIBLE_HEADING.search(clean):
            # The next lines are eligibility examples; do not scan all
            # body text where young people may only be service recipients.
            results.append(" ".join(lines[i:i+9])[:1100])
    return " ".join(results).casefold()

def supports_explicit_open_applicants(post: str, detail: str) -> bool:
    """AND with the user's explicitly listed applicant modes; OR among modes.

    Activate only for multi-mode requests. A single mention of children/youth
    in an ordinary NGO project topic remains a beneficiary, NOT a hard
    applicant requirement. The structured menu's other hard filters still apply.
    """
    requested = _detail_modalities(detail)
    if len(requested) < 2:
        return True
    evidence = _applicant_evidence(post)
    if not evidence:
        return False
    return bool(
        ("informal" in requested and _INFORMAL.search(evidence)) or
        ("individual" in requested and _INDIVIDUAL.search(evidence)) or
        ("pupil" in requested and _SCHOOL_PUPIL.search(evidence))
    )
