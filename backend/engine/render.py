"""Safe placeholder rendering for narration templates and rule texts.

Only `{name}` and `{name:spec}` with a whitelisted numeric spec are substituted,
looked up in a flat dict of primitives. No attribute access, no code, so a
template coming from an admin-added rule cannot reach into Python objects.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)(?::([0-9,.]*f|d))?\}")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

GROUP = {"nl": ".", "fr": " ", "en": ","}
DECIMAL = {"nl": ",", "fr": ",", "en": "."}
MONTHS = {
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}
YES_NO = {"nl": ("ja", "nee"), "fr": ("oui", "non"), "en": ("yes", "no")}


def fmt_date(value: str, lang: str) -> str:
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return value
    months = MONTHS.get(lang, MONTHS["en"])
    return f"{d.day} {months[d.month - 1]} {d.year}"


def fmt_number(value: float | int, spec: str | None, lang: str) -> str:
    if spec is None:
        spec = ",.0f" if float(value).is_integer() or abs(value) >= 100 else ",.2f"
    try:
        text = format(value, spec)
    except (ValueError, TypeError):
        text = str(value)
    # swap separators for Belgian NL / FR conventions
    text = text.replace(",", "\x00").replace(".", DECIMAL.get(lang, ".")).replace("\x00", GROUP.get(lang, ","))
    return text


def fmt_value(value: Any, spec: str | None, lang: str) -> str:
    if value is None:
        return "?"
    if isinstance(value, bool):
        yes, no = YES_NO.get(lang, YES_NO["en"])
        return yes if value else no
    if isinstance(value, (int, float)):
        return fmt_number(value, spec, lang)
    if isinstance(value, str) and ISO_DATE.match(value):
        return fmt_date(value, lang)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


def render(template: str, facts: dict[str, Any], lang: str = "en") -> str:
    def repl(m: re.Match[str]) -> str:
        return fmt_value(facts.get(m.group(1)), m.group(2), lang)
    return PLACEHOLDER.sub(repl, template)
