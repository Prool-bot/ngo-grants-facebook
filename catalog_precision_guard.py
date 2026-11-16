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

def _latin_call_names(text: str) -> set[tuple[str, ...]]:
    """Case-insensitive actual programme names, including all-caps titles.

    E.g. ASPRS GEOSPATIAL SCIENCE RESEARCH GRANT vs
    Geospatial Science Research Grant within Ukrainian prose.
    Avoid matching a generic two-word 'research grant'.
    """
    phrases = set()
    for match in re.finditer(
        r"\b((?:[A-Za-z]{3,}\s+){2,8}"
        r"(?:grants?|awards?|fellowships?|scholarships?))\b",
        str(text or "")[:2600], re.I
    ):
        words = tuple(re.findall(r"[a-z]{3,}", match.group().casefold()))
        if len(words) >= 4:
            phrases.add(words[-4:])
    return phrases


def _shared_donor_acronyms(a: str, b: str) -> bool:
    stop = {"NGO", "USD", "EUR", "OPEN", "CALL", "GRANT", "GRANTS",
            "THE", "FOR", "WITH", "PDF"}
    pattern = r"(?<![A-Za-z])[A-Z]{3,12}(?![A-Za-z])"
    left = set(re.findall(pattern, str(a or "")[:1500])) - stop
    right = set(re.findall(pattern, str(b or "")[:1500])) - stop
    return bool(left & right)


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
    if left & right:
        return True
    # These distinctive names survive capitalization, donor URL aliases and
    # Ukrainian introductions. Requiring a shared donor acronym makes a
    # common research/award phrase alone insufficient to merge calls.
    latin = _latin_call_names(a.get("text") or "") & _latin_call_names(
        b.get("text") or "")
    if not latin:
        return _same_branded_round(a, b)
    generic = _COMMON_ENGLISH | {"research", "science", "award", "awards",
                                  "fellowship", "scholarship"}
    return (
        (_shared_donor_acronyms(a.get("text") or "", b.get("text") or "")
         and any(len([w for w in phrase if w not in generic]) >= 1
                 for phrase in latin))
        or _same_branded_round(a, b)
    )


# A second, evidence-backed route for repeated programme announcements in
# different languages / headline styles. Generic foundation/donor words are
# excluded: two awards by one donor must remain distinct.
_BRAND_STOP = (_COMMON_ENGLISH | {
    "foundation", "fund", "research", "award", "awards", "prize", "prizes",
    "fellowship", "scholarship", "international", "creative", "europe",
    "global", "european", "the", "new", "for", "grants", "grant", "2027",
    "inc", "open", "opportunity", "competition", "national", "university",
    "program", "programme", "call", "science", "funding",
})


def _brand_phrases(text: str) -> set[tuple[str, ...]]:
    """Programme names within an announcement, not a broad host/umbrella URL.

    A full two-token brand (Cities Deliver, SPARK Incubation) or a distinctive
    hyphenated/CamelCase call word (BIE-Cosmos, WoodStock) counts as identity.
    Ordinary donor terms such as 'Parkinson Foundation' are not programme IDs.
    """
    excerpt = str(text or "")[:2400]
    found: set[tuple[str, ...]] = set()
    # Mixed-case and distinctive hyphenated proper names are programme cues.
    for m in re.finditer(r"\b[A-Za-z]{2,}(?:-[A-Za-z]{3,})+\b|"
                         r"\b[A-Z][a-z]{2,}[A-Z][A-Za-z]{2,}\b", excerpt):
        label = m.group().casefold()
        if label not in _BRAND_STOP and len(label) >= 7:
            found.add((label,))
    for m in re.finditer(
        r"(?<![A-Za-z])(?:[A-Z]{3,}|[A-Z][a-z]{2,})"
        r"(?:[ -](?:[A-Z]{3,}|[A-Z][a-z]{2,})){1,4}\b", excerpt
    ):
        words = tuple(w.casefold() for w in re.findall(r"[A-Za-z]{3,}", m.group()))
        meaningful = tuple(w for w in words if w not in _BRAND_STOP)
        if len(meaningful) >= 2:
            for i in range(len(meaningful)-1):
                found.add(meaningful[i:i+2])
    return found


def _same_branded_round(a: dict, b: dict) -> bool:
    if not a.get("_deadline") or a.get("_deadline") != b.get("_deadline"):
        return False
    both = _brand_phrases(a.get("text") or "") & _brand_phrases(b.get("text") or "")
    if not both:
        return False
    # For an isolated brand word, avoid donor-only collisions: insist on
    # same monetary evidence or an additional matching branded multiword phrase.
    if any(len(parts) > 1 for parts in both):
        return True
    # Cross-language single-word names, particularly CamelCase / hyphenated,
    # require a matching grant amount. Don't merge unrelated donor awards.
    def amounts(post: str) -> set[tuple[str, int]]:
        out = set()
        for match in re.finditer(
            r"([$€£₴])\s*(\d{1,3}(?:[.,\s]\d{3})+|\d{4,9})", post[:1900]):
            value = int(re.sub(r"\D", "", match.group(2)))
            if value >= 1000:
                out.add((match.group(1), value))
        return out
    return bool(amounts(a.get("text") or "") & amounts(b.get("text") or ""))


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
