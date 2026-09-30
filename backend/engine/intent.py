"""Customer-stated intent: turn "I need to keep €8,000 for my renovation" into a goal proposal.

Deterministic first. If GEMINI_API_KEY is set, Gemini may be asked for the
parse only (strict JSON), and its answer is validated with the same limits:
the amount must be one the deterministic scan also found in the text. Any
error falls back to the deterministic parse. The proposal is never stored
here; the customer confirms it through POST /me/goals.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

import config

log = logging.getLogger("foresight.intent")

MAX_TEXT = 300
MAX_AMOUNT = 1_000_000.0
PURPOSES = ("renovation", "car", "travel", "education", "emergency_buffer", "house_purchase", "other")

# Order matters: "verbouwing van mijn huis" is a renovation, not a house purchase.
_PURPOSE_KEYWORDS: list[tuple[str, str]] = [
    ("renovation", r"\b(verbouw|renovat|renover|travaux|keuken|badkamer|kitchen|bathroom|cuisine|salle de bain|dak\b|toiture)"),
    ("house_purchase", r"\b(huis kopen|woning|eigen huis|appartement|house|home purchase|buy a home|flat\b|maison|achat immobilier|immobilier)"),
    ("car", r"\b(auto\b|auto's|wagen|car\b|cars\b|voiture|vehicle|vehicule)"),
    ("travel", r"\b(reis|vakantie|trip|travel|holiday|vacation|voyage|vacances)"),
    ("education", r"\b(studie|studeren|school|opleiding|universiteit|hogeschool|education|tuition|universit|college|etudes|ecole|formation)"),
    ("emergency_buffer", r"\b(buffer|noodfonds|nood|onvoorzien|emergency|rainy day|unexpected|urgence|imprevu|reserve)"),
]
_KEEP = re.compile(r"\b(beschikbaar|opzij|apart|achter de hand|available|keep|aside|set aside|disponible|garder|de cote)")
_LOCK = re.compile(r"\b(vastzetten|vast zetten|beleggen|investeren|invest|lock|bloquer|placer|investir)")

# 8.000 | 8,000 | 8 000 | 8000 | 8.000,50 | 8k
_AMOUNT = re.compile(
    r"(?P<cur1>€|eur\b|euro\b)?\s*"
    r"(?P<num>\d{1,3}(?:[.,\s  ]\d{3})+|\d+)"
    r"(?:[.,](?P<dec>\d{1,2})(?!\d))?"
    r"\s*(?P<k>k\b|duizend\b|mille\b|thousand\b)?"
    r"\s*(?P<cur2>€|eur\b|euro\b|euros\b)?",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    """Lowercase and strip accents so 'rénovation' matches 'renovation'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def amounts(text: str) -> list[tuple[float, bool]]:
    """Every amount in the text, with whether a currency marker was next to it."""
    out: list[tuple[float, bool]] = []
    for m in _AMOUNT.finditer(text):
        digits = re.sub(r"[.,\s  ]", "", m.group("num"))
        value = float(digits)
        if m.group("dec"):
            value += float("0." + m.group("dec"))
        if m.group("k"):
            value *= 1000
        out.append((value, bool(m.group("cur1") or m.group("cur2"))))
    return out


def _valid_amount(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < float(value) <= MAX_AMOUNT


def deterministic_parse(text: str) -> dict[str, Any] | None:
    found = amounts(text)
    if not found:
        return None
    with_currency = [v for v, cur in found if cur]
    amount = with_currency[0] if with_currency else found[0][0]
    if not _valid_amount(amount):
        return None
    folded = _fold(text)
    purpose = next((p for p, pattern in _PURPOSE_KEYWORDS if re.search(pattern, folded)), "other")
    keep = bool(_KEEP.search(folded)) or not _LOCK.search(folded)
    return {"purpose": purpose, "amount": round(float(amount), 2), "keep_accessible": keep,
            "parser": "deterministic"}


_SCHEMA = {
    "type": "object",
    "properties": {
        "purpose": {"type": "string", "enum": list(PURPOSES)},
        "amount": {"type": "number"},
        "keep_accessible": {"type": "boolean"},
    },
    "required": ["purpose", "amount", "keep_accessible"],
}

_PROMPT = ("Extract one savings goal from the customer's sentence. Return JSON only with purpose "
           "(one of: " + ", ".join(PURPOSES) + "), amount in euro (a number that appears in the "
           "sentence) and keep_accessible (true if the money must stay available). Do not advise.")


def _gemini_parse(text: str, lang: str) -> dict[str, Any] | None:
    from google.genai import types

    from engine.narrate import _client  # shared, lazily created Gemini client
    response = _client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=json.dumps({"language": lang, "sentence": text}, ensure_ascii=False),
        config=types.GenerateContentConfig(system_instruction=_PROMPT, response_mime_type="application/json",
                                           response_schema=_SCHEMA, temperature=0.0, max_output_tokens=100),
    )
    return _validate_llm(json.loads(response.text or ""), text)


def _validate_llm(data: Any, text: str) -> dict[str, Any] | None:
    if not isinstance(data, dict) or set(data) != {"purpose", "amount", "keep_accessible"}:
        return None
    purpose, amount, keep = data["purpose"], data["amount"], data["keep_accessible"]
    if purpose not in PURPOSES or not isinstance(keep, bool) or not _valid_amount(amount):
        return None
    if all(abs(float(amount) - v) > 0.005 for v, _ in amounts(text)):
        log.warning("LLM goal parse rejected: amount not in the customer's text")
        return None
    return {"purpose": purpose, "amount": round(float(amount), 2), "keep_accessible": keep, "parser": "gemini"}


def parse_goal(text: str, lang: str) -> dict[str, Any] | None:
    """Proposal {purpose, amount, keep_accessible, parser} or None when nothing usable was said."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        return None
    if config.GEMINI_API_KEY:
        try:
            result = _gemini_parse(text, lang)
            if result:
                return result
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the deterministic parse
            log.warning("Gemini goal parse failed (%s): falling back", type(exc).__name__)
    return deterministic_parse(text)
