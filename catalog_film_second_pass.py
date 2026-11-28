"""Bounded second-pass retrieval for cinema and documentary project requests.

This is an archival *candidate* signal, not verification of applicant rights,
deadline, project financing or current official donor rules.
"""
from __future__ import annotations
import re

_FILM_DELIVERABLE = re.compile(
    r"(?:фільм\w*|кіно\w*|кінематограф\w*|"
    r"аудіовізуальн\w*|відеопродукц\w*|відеовиробництв\w*|"
    r"відеопроєкт\w*|відеопроект\w*|документаліст\w*|"
    r"documentar\w*|audiovisual|audio.visual|"
    r"filmmak\w*|film\s+(?:production|projects?|development|works?)|"
    r"cinema|screen\s+production|moving.image\s+projects?)", re.I
)
_FUNDING = re.compile(
    r"(?:грант\w*|фінансу\w*|фінансуванн\w*|"
    r"підтрим\w*\s+(?:проєкт\w*|проект\w*|ініціатив\w*|"
    r"виробництв\w*|створенн\w*)|"
    r"grants?\b|funding|funded\s+projects?|"
    r"support\s+(?:for\s+)?(?:projects?|production|creation))", re.I
)
_NEGATIVE = re.compile(
    r"(?:не\s+(?:фінанс\w*|підтрим\w*|допуска\w*)|"
    r"not\s+(?:funded|supported|eligible)|"
    r"ineligible|excluded\s+activities)", re.I
)
_SECTION_END = re.compile(
    r"^(?:хто\s+може|хто\s+пода|заявник\w*|учасник\w*|"
    r"географія|дедлайн|як\s+подат|посилання|"
    r"eligibility|who\s+can\s+apply|deadline|how\s+to\s+apply)", re.I
)
_FUNDING_HEAD = re.compile(
    r"(?:що\s+підтрим|що\s+фінансу|напрями\s+підтримки|"
    r"мета\s+програми|пріоритет\w*|"
    r"supported\s+projects?|eligible\s+activities|"
    r"funded\s+activities)", re.I
)


def broader_film_funding_evidence(post: str) -> bool:
    """Require a cinema/audio-visual output in the *positive funding scope*.

    Avoid applicant biographies, ineligibility lists, generic funding footers,
    URLs and hashtags. A genre-specific programme is preferred in the first
    pass; this merely widens the archived candidate pool in a zero-result run.
    """
    raw = re.sub(r"https?://\S+|#[^\s]+", " ", str(post or ""))
    lines = [re.sub(r"^[^\w]+", "", s).strip() for s in raw.splitlines()]
    positive: list[str] = []
    active = True
    for line in lines:
        if not line:
            continue
        if _NEGATIVE.search(line):
            active = False
            continue
        if _SECTION_END.match(line):
            active = False
            continue
        if _FUNDING_HEAD.search(line):
            active = True
        if active:
            positive.append(line)
    # Do not infer funding from a coincidental mention in the eligibility list.
    scope = "\n".join(positive)
    if not _FILM_DELIVERABLE.search(scope):
        return False
    if not _FUNDING.search(scope):
        return False
    for match in _FILM_DELIVERABLE.finditer(scope):
        if _FUNDING.search(scope[max(0, match.start()-280):match.end()+280]):
            return True
    return False
