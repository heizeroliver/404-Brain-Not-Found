"""Customer-facing v2 routes (see docs/CONTRACT.md).

  GET  /me/overview?lang=           -> priority moment, others, upcoming, allocation, goals, advisor requests
  GET  /me/timeline2?days=90|365    -> truthful timeline items (kind + date from the rule's own window)
  GET  /me/money-calendar?lang=&category=  -> personal timeline (source "you") + Belgian calendar (source "belgium")
  POST /me/advisor-requests         -> 201 new / 200 existing open request; 404 if not in the feed; 429 above cap
  GET  /me/advisor-requests         -> the caller's requests

The customer id comes only from the token (auth.current_customer_id).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

import auth
import config
import requests_store
from engine import allocation, be_calendar
from engine.models import Customer, Moment

router = APIRouter()

Lang = Literal["nl", "en", "fr"]
LANG_QUERY = Query("nl")


def _api() -> Any:
    import api  # late import: api.py includes this router
    return api


# ------------------------------------------------------------------ texts --

TITLES: dict[str, dict[str, str]] = {
    "holiday_pay": {"nl": "Je vakantiegeld komt eraan", "en": "Your holiday pay is coming",
                    "fr": "Votre pécule de vacances arrive"},
    "year_end_bonus_pension_topup": {"nl": "Pensioensparen aanvullen voor het jaareinde",
                                     "en": "Top up your pension saving before year end",
                                     "fr": "Compléter votre épargne-pension avant la fin de l'année"},
    "insurance_renewal_increase": {"nl": "Je verzekeringspremie stijgt", "en": "Your insurance premium is going up",
                                   "fr": "Votre prime d'assurance augmente"},
    "idle_cash": {"nl": "Spaargeld dat niets doet", "en": "Savings sitting idle",
                  "fr": "Une épargne qui dort"},
    "first_home_readiness": {"nl": "Klaar voor een eerste woning?", "en": "Ready for a first home?",
                             "fr": "Prêt pour un premier logement ?"},
    "child_turns_18": {"nl": "Je kind wordt 18", "en": "Your child turns 18", "fr": "Votre enfant a bientôt 18 ans"},
    "income_drop_care_mode": {"nl": "Je inkomen is gedaald", "en": "Your income has dropped",
                              "fr": "Vos revenus ont baissé"},
    "term_account_maturity": {"nl": "Je termijnrekening vervalt", "en": "Your term account is maturing",
                              "fr": "Votre compte à terme arrive à échéance"},
    "energy_bill_spike": {"nl": "Je energiefactuur is gestegen", "en": "Your energy bill went up",
                          "fr": "Votre facture d'énergie a augmenté"},
    "payment_protection": {"nl": "We hielden een betaling tegen", "en": "We held a payment",
                           "fr": "Nous avons retenu un paiement"},
    "capital_gains_tax_2026": {"nl": "Meerwaardebelasting sinds 2026", "en": "Capital gains tax since 2026",
                               "fr": "Taxe sur les plus-values depuis 2026"},
    "insurance_tax_2026": {"nl": "Hogere taks op verzekeringen", "en": "Higher insurance tax",
                           "fr": "Taxe plus élevée sur les assurances"},
    "company_car_deductibility": {"nl": "Aftrekbaarheid van je bedrijfswagen", "en": "Company car deductibility",
                                  "fr": "Déductibilité de votre voiture de société"},
    "renovation_obligation_6y": {"nl": "Renovatieplicht voor je woning", "en": "Renovation obligation for your home",
                                 "fr": "Obligation de rénovation pour votre logement"},
}

LEGAL_BASIS: dict[str, dict[str, str]] = {
    "contract_performance": {"nl": "Uitvoering van je contract", "en": "Performance of your contract",
                             "fr": "Exécution de votre contrat"},
    "legitimate_interest": {"nl": "Gerechtvaardigd belang", "en": "Legitimate interest", "fr": "Intérêt légitime"},
    "legal_obligation": {"nl": "Wettelijke verplichting", "en": "Legal obligation", "fr": "Obligation légale"},
    "consent": {"nl": "Je toestemming", "en": "Your consent", "fr": "Votre consentement"},
}

ACTION_LABELS: dict[str, dict[str, str]] = {
    "advisor_request": {"nl": "Vraag een adviseur", "en": "Ask an adviser", "fr": "Demander un conseiller"},
    "open_plans": {"nl": "Plan je spaargeld", "en": "Plan my savings", "fr": "Planifier mon épargne"},
    "open_timeline": {"nl": "Bekijk in je tijdlijn", "en": "See it on my timeline",
                      "fr": "Voir dans ma chronologie"},
    "open_data": {"nl": "Bekijk je gegevens", "en": "See my data", "fr": "Voir mes données"},
    "none": {"nl": "", "en": "", "fr": ""},
}

DATE_REASON: dict[str, dict[str, str]] = {
    "deadline": {"nl": "Uiterste datum: {d}", "en": "Deadline: {d}", "fr": "Date limite : {d}"},
    "reminder_window": {"nl": "Relevant tot {d}", "en": "Relevant until {d}", "fr": "Pertinent jusqu'au {d}"},
    "expected_payment": {"nl": "Verwachte betaling op {d}", "en": "Payment expected on {d}",
                         "fr": "Paiement attendu le {d}"},
    "renewal": {"nl": "Vernieuwing op {d}", "en": "Renews on {d}", "fr": "Renouvellement le {d}"},
    "effective_date": {"nl": "Van kracht vanaf {d}", "en": "In effect from {d}", "fr": "En vigueur à partir du {d}"},
    "effective_since": {"nl": "Van kracht sinds {d}", "en": "In effect since {d}", "fr": "En vigueur depuis le {d}"},
}

REVIEW_REASON = {"nl": "Een adviseur bekijkt dit voordat er iets gebeurt.",
                 "en": "An adviser reviews this before anything happens.",
                 "fr": "Un conseiller examine ceci avant toute action."}
ESTIMATE_REASON = {"nl": "Dit is een schatting op basis van je gegevens.",
                   "en": "This is an estimate based on your data.",
                   "fr": "Il s'agit d'une estimation basée sur vos données."}

MONTHS = {
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
}

LIFE_KINDS = {
    "holiday_pay": "expected_payment",
    "year_end_bonus_pension_topup": "deadline",
    "insurance_renewal_increase": "renewal",
    "term_account_maturity": "deadline",
}
TIMELINE_TYPES = {"holiday_pay", "year_end_bonus_pension_topup", "insurance_renewal_increase",
                  "term_account_maturity", "child_turns_18"}


def _fmt_date(d: date, lang: str) -> str:
    month = MONTHS.get(lang, MONTHS["en"])[d.month - 1]
    return f"{month} {d.day}, {d.year}" if lang == "en" else f"{d.day} {month} {d.year}"


def _world_rule(moment_type: str) -> Any:
    from engine.rules.rulebook import RULEBOOK
    return RULEBOOK.get(moment_type)


def _title(moment: Moment, lang: str, message: str = "") -> str:
    t = TITLES.get(moment.type)
    if t:
        return t.get(lang) or t["en"]
    rule = _world_rule(moment.type) if moment.source == "world_rule" else None
    if rule is not None:
        return rule.title.get(lang) or rule.title["en"]
    first = message.split(". ")[0].strip()
    return first[:120] if first else moment.type.replace("_", " ")


def _card_date(m) -> str:
    """The one date the card shows: a world rule's effective date, otherwise the window end."""
    if m.source == "world_rule":
        from engine.rules.rulebook import RULEBOOK
        rule = RULEBOOK.get(m.type)
        if rule is not None:
            return rule.effective_date.isoformat()
    return m.window[1].isoformat()


def _kind(moment: Moment) -> str:
    if moment.source == "world_rule":
        return "effective_date"
    return LIFE_KINDS.get(moment.type, "reminder_window")


def _key_date(moment: Moment, kind: str) -> tuple[date, date | None]:
    """(date, end) as the rule models it; an evaluation date is never presented as a payment date."""
    start, end = moment.window
    if kind == "effective_date":
        eff = moment.facts.get("effective_date")
        try:
            d = date.fromisoformat(str(eff)) if eff else start
        except ValueError:
            d = start
        return d, None
    if kind == "expected_payment":
        return end, None
    if kind in ("deadline", "renewal"):
        return end, None
    return start, end  # reminder window: from start until end


def _legal_label(basis: str, lang: str) -> str:
    key = "legal_obligation" if basis.startswith("legal_obligation") else basis
    labels = LEGAL_BASIS.get(key)
    if labels:
        return labels.get(lang) or labels["en"]
    return basis.replace("_", " ").capitalize()


def _action(moment: Moment, channel: str, lang: str) -> dict[str, str]:
    if channel == "advisor" or moment.type in ("payment_protection", "income_drop_care_mode"):
        kind = "advisor_request"
    elif moment.type in ("idle_cash", "first_home_readiness"):
        kind = "open_plans"
    elif moment.type in TIMELINE_TYPES or moment.source == "world_rule":
        kind = "open_timeline"
    else:
        kind = "none"
    return {"kind": kind, "label": ACTION_LABELS[kind][lang]}


def _public_request(r: dict | None) -> dict | None:
    if r is None:
        return None
    return {k: r[k] for k in ("id", "moment_type", "status", "created", "updated", "reason")}


def _open_request(requests: list[dict], moment_type: str) -> dict | None:
    for r in requests:
        if r["moment_type"] == moment_type and r["status"] in requests_store.OPEN:
            return _public_request(r)
    return None


def _why_reasons(moment: Moment, why: str, kind: str, lang: str) -> list[str]:
    reasons: list[str] = []
    if why:
        reasons.append(why.strip())
    d, end = _key_date(moment, kind)
    label = "effective_since" if kind == "effective_date" and d <= moment.window[0] else kind
    reasons.append(DATE_REASON[label][lang].format(d=_fmt_date(end or d, lang)))
    if moment.human_review:
        reasons.append(REVIEW_REASON[lang])
    elif moment.confidence < 0.8:
        reasons.append(ESTIMATE_REASON[lang])
    return reasons[:3]


def _moment_out(rm: Any, customer: Customer, lang: str, requests: list[dict]) -> dict[str, Any]:
    from engine.narrate import narrate
    m: Moment = rm.moment
    text = narrate(m, customer)
    kind = _kind(m)
    return {
        "type": m.type,
        "title": _title(m, lang, text.get("message", "")),
        "message": text.get("message", ""),
        "why_reasons": _why_reasons(m, text.get("why", ""), kind, lang),
        "why": text.get("why", ""),
        "source": m.source,
        "category": m.category,
        "stakes": m.stakes,
        "channel": rm.channel,
        "delivery": rm.delivery,
        "window": [m.window[0].isoformat(), m.window[1].isoformat()],
        "date_label_kind": kind,
        "key_date": _card_date(m),
        "confidence": m.confidence,
        "human_review_required": bool(m.human_review),
        "legal_basis_label": _legal_label(m.legal_basis, lang),
        "evidence": list(m.evidence),
        "action": _action(m, rm.channel, lang),
        "requested": _open_request(requests, m.type),
    }


def _timeline_items(customer: Customer, today: date, lang: str, horizon_days: int) -> list[dict[str, Any]]:
    """All dated items from today up to today + horizon_days, sorted by date."""
    api = _api()
    from engine.arbitrate import arbitrate
    from engine.rules import run_rules
    seen: dict[tuple[str, date], Moment] = {}
    for i, step in enumerate(api._month_steps(today, 13)):
        if (step - today).days > horizon_days:
            break
        for m in run_rules(customer, step, projectable_only=i > 0):
            seen.setdefault((m.type, m.window[1]), m)
    result = arbitrate(customer, list(seen.values()), today, api.store, record=False)
    limit = today + timedelta(days=horizon_days)
    items = []
    for rm in result.ranked:
        m = rm.moment
        kind = _kind(m)
        d, end = _key_date(m, kind)
        if d < today or d > limit:
            continue
        items.append({
            "date": d.isoformat(), "end": end.isoformat() if end else None, "kind": kind, "type": m.type,
            "title": _title(m, lang), "source": m.source, "channel": rm.channel,
            "human_review_required": bool(m.human_review), "confidence": m.confidence,
        })
    items.sort(key=lambda x: (x["date"], x["type"]))
    return items


# ----------------------------------------------------------------- routes --

@router.get("/me/overview")
def overview(customer_id: str = Depends(auth.current_customer_id), lang: Lang = LANG_QUERY) -> dict[str, Any]:
    api = _api()
    customer = api._in_language(api._customer(customer_id), lang)
    today = config.today()
    result = api._feed(customer, today, record=True)
    requests = requests_store.for_customer(customer_id)
    moments = [_moment_out(rm, customer, lang, requests) for rm in result.ranked]
    idx = next((i for i, m in enumerate(moments) if m["delivery"] == "now"), 0 if moments else None)
    priority = moments[idx] if idx is not None else None
    others = [m for i, m in enumerate(moments) if i != idx]
    upcoming = _timeline_items(customer, today, lang, 90)[:5]
    return {
        "today": today.isoformat(),
        "care_mode": result.care_mode,
        "priority": priority,
        "others": others,
        "upcoming": upcoming,
        "allocation": allocation.compute(customer),
        "goals": [g.model_dump(mode="json") for g in api.store.list_goals(customer_id)],
        "advisor_requests": [_public_request(r) for r in requests],
    }


@router.get("/me/timeline2")
def timeline2(customer_id: str = Depends(auth.current_customer_id), lang: Lang = LANG_QUERY,
              days: int = Query(90)) -> dict[str, Any]:
    if days not in (90, 365):
        raise HTTPException(422, "days must be 90 or 365")
    api = _api()
    customer = api._in_language(api._customer(customer_id), lang)
    today = config.today()
    all_items = _timeline_items(customer, today, lang, 365)
    limit = (today + timedelta(days=days)).isoformat()
    items = [i for i in all_items if i["date"] <= limit]
    later = [i for i in all_items if i["date"] > limit]
    return {"today": today.isoformat(), "days": days, "items": items,
            "next_after_horizon": later[0] if not items and later else None}


CalCategory = Literal["tax", "savings", "pension", "insurance", "loan", "home", "car", "income"]


@router.get("/me/money-calendar")
def money_calendar(customer_id: str = Depends(auth.current_customer_id), lang: Lang = LANG_QUERY,
                   category: CalCategory | None = Query(None)) -> dict[str, Any]:
    api = _api()
    customer = api._in_language(api._customer(customer_id), lang)
    today = config.today()
    personal = [{
        "id": f"you_{i['type']}_{i['date']}", "source": "you",
        "category": be_calendar.personal_category(i["type"]),
        "date": i["date"], "end": i["end"], "title": i["title"], "what": None, "tip": None,
        "basis": None, "kind": i["kind"], "type": i["type"], "source_hint": None, "recurrence": None,
        "for_you": True,
    } for i in _timeline_items(customer, today, lang, 365)]
    all_items = personal + be_calendar.calendar(customer, today, lang)
    all_items.sort(key=lambda x: (x["date"], x["source"] != "you", x["id"]))
    counts: dict[str, int] = {}
    for it in all_items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1
    items = [it for it in all_items if category is None or it["category"] == category]
    return {
        "as_of": today.isoformat(),
        "items": items,
        "categories": [{"key": k, "label": be_calendar.CATEGORY_LABELS[k][lang], "count": counts.get(k, 0)}
                       for k in be_calendar.CATEGORIES],
        "disclaimer": be_calendar.DISCLAIMER[lang],
    }


class AdvisorRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moment_type: str = Field(pattern=r"^[a-z0-9_]{3,60}$")
    note: str | None = Field(default=None, max_length=200)


@router.post("/me/advisor-requests")
def create_advisor_request(body: AdvisorRequestBody, response: Response,
                           customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    api = _api()
    customer = api._in_language(api._customer(customer_id), "en")
    today = config.today()
    result = api._feed(customer, today, record=False)
    rm = next((r for r in result.ranked if r.moment.type == body.moment_type), None)
    if rm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such moment in your feed")
    m = rm.moment
    reason = _title(m, "en")
    context = {"channel": rm.channel, "stakes": m.stakes,
               "window": [m.window[0].isoformat(), m.window[1].isoformat()]}
    try:
        req, created = requests_store.create(customer_id, body.moment_type, reason=reason, context=context)
    except OverflowError:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many advisor requests") from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    if created:
        api.store.log_decisions([{
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "customer_id": customer_id,
            "moment_type": body.moment_type, "source": "customer", "stakes": m.stakes,
            "decision": "advisor_requested", "reason": f"{req['id']}: {reason}", "score": None,
            "channel": rm.channel, "delivery": None}])
    return {"request": _public_request(req), "created": created}


@router.get("/me/advisor-requests")
def list_advisor_requests(customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    _api()._customer(customer_id)
    return {"items": [_public_request(r) for r in requests_store.for_customer(customer_id)]}
