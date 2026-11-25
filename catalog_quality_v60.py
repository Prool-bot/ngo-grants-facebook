"""Deterministic, offline quality checks for NGO Grants catalogues (issue #96).

Archived posts are evidence, not live donor verification. All checks are
conservative; no external AI calls, personal profiles, or publication effects.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
import re
from zoneinfo import ZoneInfo

from catalog_guard_v57 import applicant_evidence

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_DATE_NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")
_DATE_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_DATE_NAME = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b", re.I
)
_STAGE = re.compile(
    r"(?:дедлайн|deadline|кінцев\w*\s+термін)\s*"
    r"(?:[:—–-]\s*)?(?:перш\w*\s+етап\w*|етап\w*\s*1|"
    r"loi\b|letter\s+of\s+intent|concept\s+note|"
    r"попередн\w*\s+(?:заяв\w*|поданн\w*))|"
    r"(?:перш\w*\s+етап\w*|loi\b|letter\s+of\s+intent|"
    r"concept\s+note)\s*(?:[:—–-]\s*)?"
    r"(?:deadline|дедлайн)", re.I
)
_OPTIONAL_PRELIM = re.compile(
    r"(?:необов.язков\w*|optional|not\s+(?:mandatory|required))"
    r".{0,100}(?:етап|loi|попередн\w*|concept\s+note)|"
    r"(?:етап|loi|попередн\w*|concept\s+note)"
    r".{0,100}(?:необов.язков\w*|optional|not\s+(?:mandatory|required))", re.I
)
_INVITE_ONLY = re.compile(
    r"(?:лише|тільки)\s+за\s+запрошенням|"
    r"invitation\s+only|only\s+(?:by\s+)?invitation|"
    r"за\s+результатами\s+loi|"
    r"loi\s+є\s+обов.язков\w*", re.I
)


def _dates(fragment: str) -> list[date]:
    values: set[date] = set()
    for m in _DATE_NUM.finditer(fragment):
        try:
            values.add(date(int(m[3]), int(m[2]), int(m[1])))
        except ValueError:
            pass
    for m in _DATE_ISO.finditer(fragment):
        try:
            values.add(date(int(m[1]), int(m[2]), int(m[3])))
        except ValueError:
            pass
    for m in _DATE_NAME.finditer(fragment):
        try:
            values.add(date(int(m[3]), MONTHS[m[2].casefold()], int(m[1])))
        except ValueError:
            pass
    return sorted(values)


def first_mandatory_stage_deadline(post: str) -> date | None:
    """Return the first required entry gateway, not an invite-only full round.

    Never infer that an optional preliminary application blocks later entry.
    Limit detection to explicitly labelled early-stage deadlines to prevent
    event dates and ordinary documentation dates from excluding live calls.
    """
    lines = str(post or "").splitlines()
    optional = bool(_OPTIONAL_PRELIM.search(str(post or "")))
    invitation = bool(_INVITE_ONLY.search(str(post or "")))
    candidates: list[date] = []
    for index, line in enumerate(lines):
        stage_on_line = _STAGE.search(line)
        # The heading may be just "ДЕДЛАЙН"; the next bullet then names
        # an obligatory pre-proposal. Never interpret invite-only FULL
        # proposal in the next bullet as an open application gateway.
        is_stage_bullet = bool(
            _dates(line) and
            re.search(r"(?:pre[- ]?proposal|concept\s+note|"
                      r"попередн\w*\s+(?:проєктн\w*\s+)?пропозиці\w*|"
                      r"(?:обов.язков\w*\s+)?loi\b|"
                      r"попередн\w*\s+заяв\w*)", line, re.I)
            and any(re.search(r"дедлайн|deadline|кінцев\w*\s+термін",
                              previous, re.I)
                    for previous in lines[max(0,index-2):index])
        )
        if not stage_on_line and not is_stage_bullet:
            continue
        if _OPTIONAL_PRELIM.search(line):
            continue
        # Some sources put the date on the next line under a heading.
        snippet = line + " " + (lines[index + 1] if index + 1 < len(lines) else "")
        stage_dates = _dates(snippet)
        if not stage_dates:
            continue
        # LOI/preliminary may be optional; a clearly first required phase is
        # mandatory unless the source explicitly says it is optional.
        if optional and re.search(r"loi|попередн|перш\w*\s+етап|pre[- ]?proposal", line, re.I):
            continue
        # An unqualified LOI deadline by itself is not necessarily mandatory:
        # invitation-only progression is explicit evidence of a hard gateway.
        if re.search(r"\bloi\b|letter\s+of\s+intent|попередн\w*|pre[- ]?proposal", line, re.I):
            if not invitation and not is_stage_bullet and not re.search(r"обов.язков|required|mandatory", snippet, re.I):
                continue
        candidates.append(min(stage_dates))
    return min(candidates) if candidates else None


def effective_entry_deadline(post: str, displayed: date | None) -> date | None:
    """The first required gateway takes precedence over a later invitation date."""
    first = first_mandatory_stage_deadline(post)
    if first is None:
        return displayed
    return min(first, displayed) if displayed is not None else first


def same_day_deadline_expired(post: str, deadline: date | None,
                              as_of_dt: datetime | None) -> bool:
    """Exclude a completed same-day donor-local cutoff only when unambiguous.

    If a post does not give both a clock time and time zone, date-level checks
    remain unchanged instead of inventing a closing hour.
    """
    if deadline is None or as_of_dt is None:
        return False
    if as_of_dt.tzinfo is None:
        raise ValueError("as_of_dt must be offset-aware")
    zones = {
        "EST": timezone(timedelta(hours=-5)),
        "EDT": timezone(timedelta(hours=-4)),
        "ET": ZoneInfo("America/New_York"),
        "PST": timezone(timedelta(hours=-8)),
        "PDT": timezone(timedelta(hours=-7)),
        "PT": ZoneInfo("America/Los_Angeles"),
        "UTC": timezone.utc,
        "GMT": timezone.utc,
        "CET": timezone(timedelta(hours=1)),
        "CEST": timezone(timedelta(hours=2)),
        "EET": timezone(timedelta(hours=2)),
        "EEST": timezone(timedelta(hours=3)),
    }
    lines = str(post or "").splitlines()
    for idx, line in enumerate(lines):
        if deadline not in _dates(line):
            continue
        if not re.search(r"дедлайн|deadline|close|закінчу|до\s+\d{1,2}", line, re.I):
            continue
        # A time printed on a following "ЧАС" line still belongs to the
        # exact deadline above. Do not search unrelated time mentions.
        # Include up to two spacing/heading lines before an adjacent clock label.
        context = " ".join(lines[idx:idx+4])
        match = re.search(
            r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d).{0,75}?"
            r"\b(EST|EDT|ET|PST|PDT|PT|UTC|GMT|EEST|EET|CET|CEST)\b",
            context, re.I
        )
        if match:
            h, minute, abbreviation = match.groups()
            closing = datetime.combine(deadline, time(int(h), int(minute)), zones[abbreviation.upper()])
            if as_of_dt >= closing:
                return True
    return False


def qualification_warnings(post: str, facets: dict | None) -> tuple[str, ...]:
    """Identify qualifications an unspecified individual has not confirmed.

    These are not claims of ineligibility. For a broad individual filter they
    demote apparent 'direct' matches to conditional with explicit warnings.
    """
    if not facets or facets.get("audience") != "individual":
        return ()
    evidence = applicant_evidence(post)
    if not evidence:
        return ()
    issues: list[str] = []
    if re.search(r"\bphd\b|\babd\b|postdoc|докторант\w*|аспірант\w*|"
                 r"магістрант\w*|ступен\w*|master.s|дослідник\w*|"
                 r"науковц\w*|викладач\w*|senior\s+(?:faculty|scientist)|"
                 r"faculty\s+member", evidence, re.I):
        issues.append("Академічна кваліфікація або дослідницький статус заявника не перевірені.")
    if re.search(r"(?:обов.язков\w*|required|must\s+have|necessary).{0,90}"
                 r"(?:членств\w*|member(ship)?)|"
                 r"(?:членств\w*|member(ship)?).{0,90}"
                 r"(?:обов.язков\w*|required|must\s+have)", evidence, re.I):
        issues.append("Обов'язкове професійне членство не підтверджене.")
    if re.search(r"(?:full.time|повн\w*\s+ставк\w*|штатн\w*|"
                 r"афілійован\w*|інституційн\w*|приймаюч\w*\s+організаці\w*|"
                 r"universit\w*|університет\w*|академічн\w*\s+установ\w*)", evidence, re.I):
        issues.append("Вимоги до місця роботи або установи заявника потребують перевірки.")
    if re.search(r"(?:художник\w*|митц\w*|журналіст\w*|режисер\w*|"
                 r"письменник\w*|фахівц\w*|інженер\w*|"
                 r"artist\w*|journalist\w*|filmmaker\w*|engineer\w*)", evidence, re.I):
        issues.append("Професійна спеціалізація заявника не підтверджена.")
    if re.search(r"готов\w*\s+переїх\w*|must\s+relocate|"
                 r"обов.язков\w*\s+очн\w*|required\s+in.person", evidence, re.I):
        issues.append("Обов'язкова очна участь або переїзд потребує підтвердження.")
    return tuple(issues)



def funding_profile(post: str) -> tuple[str, str, tuple[str, ...]]:
    """Evidence-based description of the support, separate from applicant tier.

    This never claims donor eligibility or live funding. In particular,
    a paid exhibition application is not relabelled as a cash grant.
    """
    source = re.sub(r"https?://\S+|#[^\s]+", " ", str(post or "")).casefold()
    opening = "\n".join(source.splitlines()[:12])
    grant = bool(re.search(
        r"(?:мікрогрант\w*|грант(?:и|у|ів|ом|ова|овий)?\b|"
        r"grant(?:s| funding)?\b)", opening))
    award = bool(re.search(
        r"\b(?:award|prize)\b|премі\w*|нагород\w*", opening))
    fellowship = bool(re.search(r"fellowship|феллоушип", opening))
    scholarship = bool(re.search(r"scholarship|стипенді\w*", opening))
    residency = bool(re.search(r"residen(?:cy|cies)|резиденці\w*", opening))
    exhibition = bool(re.search(
        r"\bopen call\b|виставк\w*|експозиці\w*|артбук|"
        r"галере\w*|фестивал\w*", opening))
    explicit_cash = bool(re.search(
        r"(?:\bgrant\b|мікрогрант\w*|грошов\w*\s+грант|"
        r"фінансуван\w*\s+(?:проєкт|проект)|"
        r"\b(?:usd|eur)\s*[\d,]+|[$€£]\s*[\d,.]+)",
        source[:2600]))
    paid = bool(re.search(
        r"(?:внесок\s+за\s+(?:подач|поданн|участ)|"
        r"реєстраційн\w*\s+внесок|вартіст\w*\s+участ|"
        r"плата\s+за\s+(?:подач|поданн)|"
        r"application\s+fee|submission\s+fee|entry\s+fee|"
        r"membership\s+fee)", source))
    warnings = []
    if paid:
        warnings.append("Участь або подання платні: перевірте суму внеску.")
    if award:
        kind, label = "award", "Мистецька чи наукова премія / нагорода"
    elif fellowship:
        kind, label = "fellowship", "Стипендіальна / дослідницька програма (fellowship)"
    elif scholarship:
        kind, label = "scholarship", "Стипендія на навчання чи дослідження"
    elif residency:
        kind, label = "residency", "Мистецька або професійна резиденція"
    elif grant:
        kind, label = "grant", "Грантова підтримка"
    elif exhibition:
        kind, label = "open_call", "Виставка / конкурс / open call; грошовий грант не підтверджено"
        if not explicit_cash:
            warnings.append("Грошовий грант за умовами цього конкурсу не підтверджено.")
    else:
        kind, label = "other", "Інша можливість; формат фінансування потребує перевірки"
    return kind, label, tuple(warnings)


def institutional_application_dependency(post: str) -> str:
    """A compulsory institutional PI or host is not an ordinary personal CV criterion."""
    text = str(post or "").casefold()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(r"\b(?:pi|principal\s+investigator)\b|інституційн\w*\s+керівник", line, re.I):
            context = " ".join(lines[max(0, index - 1):index + 2])
            if re.search(r"інституційн\w*|\binstitutional\b|університет\w*", context, re.I) and re.search(
                    r"має\s+виступити|необхідн\w*|обов.язков\w*|потрібн\w*|"
                    r"must|required|mandatory", context, re.I):
                return "Потрібен обов'язковий інституційний PI або приймаюча установа."
    return ""


def missing_actionable_source(post: str) -> bool:
    """Only flag an explicit link placeholder with no usable link or domain."""
    text = str(post or "")
    if re.search(r"https?://\S+|\b(?:[a-z0-9-]+\.)+(?:org|com|gov|edu|net|ua|eu|int)\b",
                 text, re.I):
        return False
    return bool(re.search(
        r"(?:🔗\s*(?:деталі\s+гранту|офіційна\s+сторінка|"
        r"подати\s+заявку|подати\s+заявку\s+та\s+дізнатися)|"
        r"офіційн\w*\s+сторінк\w*\s+програм\w*\s+та\s+подач\w*)",
        text, re.I))


def open_for_new_applicants(post: str, as_of: date) -> bool:
    """Fail closed for a plainly unannounced/upcoming submission window.

    Without a verified opening date, archived text stating 'not yet open'
    must NEVER be promoted to a currently available grant. The channel can
    publish a new, explicitly open announcement later.
    """
    clean = str(post or "").casefold()
    if re.search(
        r"(?:прийом|поданн\w*\s+заяв\w*|конкурс).{0,45}"
        r"(?:ще\s+не\s+розпочат\w*|ще\s+не\s+відкрит\w*|"
        r"почнеться\s+(?:пізніше|у\s+20\d\d))|"
        r"applications?\s+(?:are\s+)?not\s+(?:yet\s+)?open|"
        r"call\s+not\s+yet\s+open", clean
    ):
        return False
    return True


def opportunity_kind(post: str) -> tuple[str, str]:
    """Machine-safe descriptive label; never infer guaranteed funding."""
    text = str(post or "").casefold()
    conference = bool(re.search(r"конференц\w*|conference|symposium|congress", text))
    papers = bool(re.search(r"call\s+for\s+(?:papers?|proposals?)|"
                            r"technical\s+(?:paper|proposal)|"
                            r"abstract|manuscript|доповід\w*|тез\w*", text))
    if conference and papers and re.search(
            r"не\s+покрива\w*|не\s+фінансу\w*|оплачує\s+учасник|"
            r"borne\s+by\s+(?:the\s+)?(?:participants?|authors?)|"
            r"at\s+their\s+own\s+expense", text):
        return ("conference_cfp", "Конференційний конкурс: грантове фінансування не підтверджене.")
    if conference and papers and not re.search(r"грант\w*\s+(?:до|на)|"
                                                r"(?:grant|stipend)\s+(?:of|up\s+to)", text):
        return ("conference_cfp", "Конференційний конкурс: фінансування необхідно уточнити.")
    if re.search(r"fellowship|феллоушип|дослідницьк\w*\s+стажуванн", text):
        return ("fellowship", "Дослідницька програма / fellowship.")
    if re.search(r"резиденц\w*|residency", text):
        return ("residency", "Резиденція.")
    if re.search(r"стипенді\w*|scholarship", text):
        return ("scholarship", "Стипендія.")
    if re.search(r"премі\w*|award|prize", text):
        return ("award", "Премія або конкурс нагород.")
    if re.search(r"навчанн\w*|training\s+program", text) and not re.search(r"грант\w*|grant", text):
        return ("training", "Освітня / навчальна програма.")
    return ("grant_or_other", "Грантова або інша можливість: перевірте умови фінансування.")
