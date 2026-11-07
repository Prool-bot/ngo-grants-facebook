"""NGO Grants AI v5.7: evidence-based suitability and menu clarification.

No external requests, model calls, user IDs or secrets. This module is a
deterministic, fail-closed guard for structured (Worker/D1) catalogue queries.
It does not decide whether a donor's official rules changed since publication.
"""
from __future__ import annotations

import re
import unicodedata


def _clean(text: str) -> str:
    return re.sub(r"https?://\S+|#[\wа-яіїєґ]+", " ",
                  unicodedata.normalize("NFKC", str(text or "")).casefold())


_APPLICANT_HEADER = re.compile(
    r"(?:хто\s+може\s+(?:подаватись|подаватися|подати|брати\s+участь)|"
    r"хто\s+подає|хто\s+може\s+подат|заявники|учасники|"
    r"для\s+кого|eligible\s+applicants|who\s+can\s+apply)", re.I)
_NEXT_HEADER = re.compile(
    r"(?:що\s+(?:підтриму|фінансу)|які\s+проєкти|основн\w*\s+вимог|"
    r"як\s+подат|подання\s+заяв|документи|дедлайн|"
    r"фінансуван|географія|важливі\s+умови|"
    r"офіційні\s+(?:умови|посилання)|можливості\s+для\s+україни|"
    r"what\s+is\s+funded|how\s+to\s+apply)", re.I)

_NGO = re.compile(
    r"(?:\bго\b|\bогс\b|\bнго\b|\bngo\b|\bngos\b|"
    r"громадськ\w*\s+організаці|неурядов\w*\s+організаці|"
    r"неприбутков\w*\s+організаці|некомерційн\w*\s+організаці|"
    r"благодійн\w*\s+(?:фонд|організаці)|"
    r"організаці\w*\s+громадянськ\w*\s+суспільств|"
    r"non-?profit|civil society organi)", re.I)
_COMPANY = re.compile(
    r"(?:\bфоп\b|\bтов\b|\bмсб\b|"
    r"підприємц\w*|підприємств\w*|компані\w*|бізнес\w*|стартап\w*|"
    r"\bкомерційн\w*\s+організаці|"
    r"\bsme\b|\bsmes\b|\bstartup\w*\b|\bcompanies\b|"
    r"\bbusinesses\b|entrepreneur\w*)", re.I)
_PERSON = re.compile(
    r"(?:фізичн\w*\s+особ|індивідуальн\w*\s+(?:заявник|учасник)|"
    r"студент\w*|школяр\w*|учн\w*|журналіст\w*|"
    r"дослідник\w*|науковц\w*|митц\w*|художник\w*|"
    r"режисер\w*|автор\w*|фотограф\w*|"
    r"ветеран\w*|ветеранк\w*|individuals?\b|"
    r"artists?\b|students?\b|researchers?\b)", re.I)
_MUNICIPAL = re.compile(
    r"(?:територіальн\w*\s+громад|орган\w*\s+місцев\w*\s+самоврядуван|"
    r"муніципалітет\w*|міськ\w*\s+рад|сільськ\w*\s+рад|"
    r"\bmunicipalit\w*|local\s+authorit\w*)", re.I)
_PARTNER = re.compile(
    r"(?:партнер\w*|співзаявник\w*|консорціум\w*|"
    r"\bpartners?\b|co-applicant\w*|consortium)", re.I)
_NEGATIVE = re.compile(
    r"(?:не\s+допуска\w*|не\s+мож\w*\s+(?:пода\w*|брати)|"
    r"не\s+мають\s+права|виключа\w*|ineligible|"
    r"not\s+eligible|excluded)", re.I)


def applicant_evidence(post: str) -> str:
    """Read the applicants section only, never the organizer or sponsor name."""
    lines = _clean(post).splitlines()
    for i, line in enumerate(lines):
        if _APPLICANT_HEADER.search(line):
            captured = [line]
            for next_line in lines[i + 1:i + 16]:
                trimmed = next_line.strip(" \t*•-–:.!?")
                if _NEXT_HEADER.search(trimmed) and len(trimmed) < 115:
                    break
                captured.append(next_line)
            return "\n".join(captured)[:1600]
    # Old short archive posts can state the applicant in the introductory text.
    intro = "\n".join(lines[:7])
    return "\n".join(x for x in intro.splitlines() if
                     re.search(r"(?:заявк\w*|для|можуть|eligible|"
                               r"учасник\w*|запрош\w*)", x))[:750]


def funded_scope(post: str) -> str:
    """Capture grant purpose rather than qualifications, footers or exclusions."""
    lines = _clean(post).splitlines()
    focus = []
    in_eligibility = False
    in_negative = False
    for i, line in enumerate(lines):
        stripped = line.strip(" \t*•-–:.!?")
        if not stripped:
            continue
        if re.search(r"(?:не\s+підтримуються|не\s+фінансуються|"
                     r"не\s+допуска\w*|ineligible|not\s+supported)", stripped):
            in_negative = True
            continue
        if _APPLICANT_HEADER.search(stripped):
            in_eligibility = True
            continue
        if re.search(r"(?:що\s+підтриму|що\s+фінансу|"
                     r"напрями\s+підтримки|які\s+проєкти|"
                     r"мета\s+програми|funded\s+projects)", stripped):
            in_eligibility = False
            in_negative = False
        if re.search(r"(?:можливості\s+для\s+україни|"
                     r"як\s+подат|офіційн\w*\s+посилан|"
                     r"документи\s+для\s+подан)", stripped):
            break
        if not in_eligibility and not in_negative and i < 75:
            focus.append(line)
    return "\n".join(focus)[:5500]


def request_intent(facets: dict) -> str:
    """Independent, more specific goal beneath the broad sector selection."""
    detail = _clean(facets.get("detail") or facets.get("custom_sector") or "")
    selected = set(facets.get("sectors") or [])
    if (re.search(r"жіноч\w*|жін\w*|women|female", detail) and
            re.search(r"підприєм\w*|бізнес\w*|стартап\w*|business|entrepreneur", detail)):
        return "women_business"
    if (re.search(r"територіальн\w*\s+громад|для\s+громад|муніципал\w*",
                  detail) and not re.search(r"фізичн\w*\s+особ", detail)):
        return "municipal_development"
    if selected == {"rights"} and not detail:
        return "human_rights"
    return ""


def topic_supported(post: str, facets: dict) -> bool:
    """Strong positive evidence for narrow intents, not incidental mentions."""
    intent = request_intent(facets)
    if not intent:
        return True
    focus = funded_scope(post)
    if intent == "women_business":
        return bool(
            re.search(r"(?:жіноч\w*|жін\w*|women|female)", focus) and
            re.search(r"(?:підприєм\w*|бізнес\w*|стартап\w*|"
                      r"business|entrepreneur|startup)", focus))
    if intent == "municipal_development":
        return bool(re.search(
            r"(?:розвит\w*\s+громад|відновлен\w*\s+громад|"
            r"підтримк\w*\s+громад|для\s+громад|"
            r"територіальн\w*\s+громад|"
            r"муніципалітет\w*|місцев\w*\s+самоврядуван|"
            r"\bmunicipalit\w*|local\s+authorit\w*)", focus))
    if intent == "human_rights":
        return bool(re.search(
            r"(?:правозах\w*|права\s+людини|human\s+rights|"
            r"громадянськ\w*\s+свобод\w*|демократ\w*|"
            r"боротьб\w*\s+з\s+дискримінац\w*|"
            r"захист\w*\s+дітей\s+від\s+насильств\w*|"
            r"гендерно\s+зумовлен\w*\s+насильств\w*|"
            r"захист\w*\s+прав\w*|freedom\s+of\s+expression)", focus))
    return True


def applicant_status(post: str, facets: dict) -> str:
    """Return direct / conditional / reject; unverifiable roles are rejected."""
    category = facets.get("audience", "all")
    if category == "all":
        return "direct"
    eligible = applicant_evidence(post)
    if not eligible:
        return "reject"

    # Segment negative exclusions; do not count a disallowed type as eligible.
    sentences = re.split(r"[\n.;]+", eligible)
    positive = "\n".join(x for x in sentences if not _NEGATIVE.search(x))
    negative = "\n".join(x for x in sentences if _NEGATIVE.search(x))
    # Leaders/employees OF an NGO may apply personally; that is not the
    # NGO itself being allowed to be a project applicant.
    organization_as_job = re.compile(
        r"(?:керівник\w*|представник\w*|працівник\w*|співробітник\w*)"
        r"(?:\s+\w+){0,2}\s+"
        r"(?:громадськ\w*\s+організаці\w*|неприбутков\w*\s+організаці\w*)")
    applicant_entities = organization_as_job.sub("особистий учасник", positive)
    ngo = bool(_NGO.search(applicant_entities))
    business = bool(_COMPANY.search(positive))
    # "Фізична особа-підприємець" is a registered FOP, not an ordinary
    # individual applicant. Do not infer non-business eligibility from it.
    without_fop = re.sub(
        r"фізичн\w*\s+особ\w*[-– ]\s*підприємц\w*",
        " ", positive)
    human = bool(_PERSON.search(without_fop))
    muni = bool(_MUNICIPAL.search(positive))
    legal = bool(re.search(r"юридичн\w*\s+особ|legal\s+entit\w*", positive))
    no_ngo = bool(_NGO.search(negative))
    no_company = bool(_COMPANY.search(negative))
    no_human = bool(_PERSON.search(negative))

    if category == "nonprofit":
        # "Legal entities and FOP" in a jobs/business programme does not
        # establish that NGOs may submit, even if the term is legally broad.
        direct = (ngo or (legal and not business)) and not no_ngo
        restricted = no_ngo or not direct
    elif category == "commercial":
        direct = business and not no_company
        restricted = no_company or not direct
    elif category == "individual":
        direct = human and not no_human
        restricted = no_human or not direct
    elif category == "municipal":
        direct = muni
        restricted = not direct
    elif category == "institution":
        direct = bool(re.search(
            r"університет\w*|заклад\w*\s+освіт\w*|"
            r"освітн\w*\s+заклад\w*|школ\w*|"
            r"науков\w*\s+установ\w*|university|school", positive))
        restricted = not direct
    else:
        return "reject"

    role = facets.get("applicant_role", "lead")
    # The mere word "partners" in a broad call does not prove the chosen
    # applicant type can join as partner. Require category in the positive
    # applicant section and an explicit partnership mechanism.
    partner_eligible = (
        _PARTNER.search(eligible) is not None and
        (direct or (category == "nonprofit" and ngo) or
         (category == "commercial" and business) or
         (category == "individual" and human)))
    if role == "partner":
        return "conditional" if partner_eligible else "reject"
    if direct and not restricted:
        return "direct"
    if role == "either" and partner_eligible and not restricted:
        return "conditional"
    return "reject"


def quality_status(post: str, facets: dict | None) -> str:
    """Use for BOTH candidate retrieval and final acceptance after model review."""
    if facets is None:
        return "direct"
    if not topic_supported(post, facets):
        return "reject"
    status = applicant_status(post, facets)
    if status == "reject":
        return status
    if facets.get("funding_format") == "grant_only":
        # Restrict strictly individual stipends, fellowship-only, prizes and
        # loans when the user has explicitly chosen monetary project funding.
        scope = funded_scope(post)
        if re.search(r"(?:тільки\s+(?:стипенді|премі)|"
                     r"виключно\s+(?:резиденці|навчан)|"
                     r"не\s+грошов\w*\s+грант|"
                     r"not\s+a\s+(?:cash\s+)?grant)", scope):
            return "reject"
    return status


def clarification_questions(facets: dict) -> list[dict]:
    """Backend contract for the Cloudflare menu; no AI call is necessary."""
    questions = []
    audience = facets.get("audience")
    detail = _clean(facets.get("detail") or "")
    sectors = facets.get("sectors") or []
    if audience == "nonprofit" and request_intent(facets) == "municipal_development":
        questions.append({
            "field": "applicant_role",
            "question": "Хто має подавати заявку: ГО для роботи у громаді чи сама рада/муніципалітет?",
            "choices": ["Громадська організація", "Територіальна громада", "Не має значення"]
        })
    if audience == "individual" and set(sectors) & {"business", "agriculture"}:
        questions.append({
            "field": "audience",
            "question": "Ви подаєтесь як фізична особа без ФОП чи як зареєстрований ФОП?",
            "choices": ["Фізична особа", "ФОП"]
        })
    if request_intent(facets) == "women_business":
        questions.append({
            "field": "scope",
            "question": "Потрібні спеціальні програми для жінок чи також загальні бізнес-гранти?",
            "choices": ["Лише жіночі програми", "Усі бізнес-гранти, відкриті для жінок"]
        })
    if len(sectors) >= 3 and not detail:
        questions.append({
            "field": "detail",
            "question": "Уточніть конкретний проєкт або діяльність (до 180 символів).",
            "choices": []
        })
    return questions[:2]
