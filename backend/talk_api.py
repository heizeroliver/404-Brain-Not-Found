"""Kate Talk: deterministic intent routing + templates (docs/TALK_CONTRACT.md).

  GET  /me/talk/briefing       -> TalkResponse (intent briefing)
  POST /me/talk                -> TalkResponse (spending|upcoming|goal_proposal|why|save_more|clarify)
  POST /me/talk/goal/confirm   -> TalkResponse (goal_saved), stored like POST /me/goals

The customer id comes only from the token; chat text never selects a customer.
Numbers come only from backend calculations. Nothing here moves money.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

import auth
import config
from engine import allocation, spending
from engine.intent import _fold, amounts, parse_goal
from engine.models import Customer, Goal, GoalPurpose

router = APIRouter()

Lang = Literal["nl", "en", "fr"]
LANG_QUERY = Query("nl")


def _api() -> Any:
    import api  # late import: api.py includes this router
    return api


def _capi() -> Any:
    import customer_api
    return customer_api


# ----------------------------------------------------------------- models --

class TalkContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moment_type: str | None = Field(default=None, pattern=r"^[a-z0-9_]{3,60}$")
    period_days: Literal[90] | None = 90


class TalkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    context: TalkContext | None = None


class GoalConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: GoalPurpose
    amount: float = Field(gt=0, le=1_000_000)
    keep_accessible: bool = Field(default=True, strict=True)


class Period(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: str
    model_config = ConfigDict(populate_by_name=True)


class Suggestion(BaseModel):
    label: str
    text: str


class Fact(BaseModel):
    label: str
    value: float
    unit: str = "eur"


class Proposal(BaseModel):
    purpose: str
    amount: float
    keep_accessible: bool
    summary: str


class TalkResponse(BaseModel):
    intent: Literal["spending", "upcoming", "goal_proposal", "goal_saved", "why", "save_more", "briefing", "clarify"]
    message: str
    as_of: str
    period: dict[str, str] | None = None
    chart: dict[str, Any] | None = None
    facts: list[Fact] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    proposal: Proposal | None = None
    suggestions: list[Suggestion] = Field(min_length=2, max_length=4)
    context: dict[str, Any]
    synthetic: bool = True


# ------------------------------------------------------------------ texts --

Q = {
    "spending": {"nl": "Waar ging mijn geld naartoe?", "en": "Where did my money go?",
                 "fr": "Où est passé mon argent ?"},
    "upcoming": {"nl": "Wat komt eraan?", "en": "What's coming up?", "fr": "Qu'est-ce qui est à venir ?"},
    "why": {"nl": "Waarom raad je dit aan?", "en": "Why do you suggest this?", "fr": "Pourquoi me conseilles-tu ceci ?"},
    "goal": {"nl": "Ik wil €8.000 beschikbaar houden voor mijn verbouwing",
             "en": "I want to keep €8,000 available for my renovation",
             "fr": "Je veux garder 8 000 € disponibles pour ma rénovation"},
    "save_more": {"nl": "Hoe kan ik meer sparen?", "en": "How can I save more?",
                  "fr": "Comment épargner davantage ?"},
}

KEYWORDS: dict[str, list[str]] = {
    "spending": ["waar ging mijn geld", "waar is mijn geld", "uitgaven", "uitgegeven", "where did my money",
                 "spent", "spending", "expenses", "depenses", "ou est passe", "ou va mon argent"],
    "upcoming": ["komt eraan", "komende", "binnenkort", "coming up", "upcoming", "next 90 days", "a venir",
                 "prochains", "prochaines"],
    "why": ["waarom", "why", "pourquoi"],
    "save_more": ["meer sparen", "besparen", "save more", "saving more", "cut costs", "epargner plus",
                  "epargner davantage", "economiser"],
}

PURPOSE = {
    "renovation": {"nl": "Verbouwing", "en": "Renovation", "fr": "Rénovation"},
    "car": {"nl": "Auto", "en": "Car", "fr": "Voiture"},
    "travel": {"nl": "Reis", "en": "Travel", "fr": "Voyage"},
    "education": {"nl": "Studies", "en": "Education", "fr": "Études"},
    "emergency_buffer": {"nl": "Noodbuffer", "en": "Emergency buffer", "fr": "Réserve d'urgence"},
    "house_purchase": {"nl": "Woning kopen", "en": "Buying a home", "fr": "Achat d'un logement"},
    "other": {"nl": "Ander doel", "en": "Other goal", "fr": "Autre objectif"},
}
KEEP = {"nl": "beschikbaar houden", "en": "keep available", "fr": "garder disponible"}
LOCKED = {"nl": "mag vastgezet worden", "en": "can be tied up", "fr": "peut être bloqué"}

L = {
    "income": {"nl": "Inkomsten", "en": "Income", "fr": "Revenus"},
    "spending": {"nl": "Uitgaven", "en": "Spending", "fr": "Dépenses"},
    "saving": {"nl": "Gespaard (pensioensparen)", "en": "Saved (pension saving)", "fr": "Épargné (épargne-pension)"},
    "buffer": {"nl": "Buffer", "en": "Buffer", "fr": "Réserve"},
    "remaining": {"nl": "Vrij", "en": "Remaining", "fr": "Disponible"},
    "reserved": {"nl": "Gereserveerd voor je doelen", "en": "Reserved for your goals", "fr": "Réservé à vos objectifs"},
}
BUFFER_ASSUMPTION = {"nl": "Buffer = 6 x je netto maandinkomen (prototype-aanname).",
                     "en": "Buffer = 6 x your net monthly income (prototype assumption).",
                     "fr": "Réserve = 6 x votre revenu net mensuel (hypothèse du prototype)."}
SYNTH = {"nl": "Synthetische demogegevens.", "en": "Synthetic demo data.", "fr": "Données de démo synthétiques."}
SCENARIO = {"nl": "Scenario op basis van gemeten uitgaven, geen advies.",
            "en": "Scenario based on measured spending, not advice.",
            "fr": "Scénario basé sur les dépenses mesurées, pas un conseil."}

BASIS_BY_TYPE = {
    "insurance_renewal_increase": "contract", "term_account_maturity": "contract",
    "holiday_pay": "estimate_from_history", "year_end_bonus_pension_topup": "estimate_from_history",
}


def _eur(v: float, lang: str) -> str:
    whole = f"{abs(v):,.0f}"
    sign = "-" if v < 0 else ""
    if lang == "nl":
        return f"{sign}€{whole.replace(',', '.')}"
    if lang == "fr":
        return f"{sign}{whole.replace(',', ' ')} €"
    return f"{sign}€{whole}"


def _fmt(d: date, lang: str) -> str:
    return _capi()._fmt_date(d, lang)


def _period_label(a: date, b: date, lang: str) -> str:
    months = _capi().MONTHS[lang]
    return f"{a.day} {months[a.month - 1][:3].lower()} – {b.day} {months[b.month - 1][:3].lower()} {b.year}"


def _sugg(lang: str, *keys: str) -> list[Suggestion]:
    return [Suggestion(label=Q[k][lang], text=Q[k][lang]) for k in keys]


def _ctx(ctx: TalkContext | None, moment_type: str | None = None) -> dict[str, Any]:
    mt = moment_type or (ctx.moment_type if ctx else None)
    return {"moment_type": mt, "period_days": 90}


def _resp(intent: str, message: str, lang: str, context: dict[str, Any], suggestions: list[Suggestion],
          **kw: Any) -> TalkResponse:
    return TalkResponse(intent=intent, message=message, as_of=config.today().isoformat(), context=context,
                        suggestions=suggestions, **kw)


def _load(customer_id: str, lang: str) -> Customer:
    api = _api()
    return api._in_language(api._customer(customer_id), lang)


def _priority(customer: Customer, lang: str, moment_type: str | None = None) -> dict[str, Any] | None:
    api, capi = _api(), _capi()
    result = api._feed(customer, config.today(), record=False)
    moments = [capi._moment_out(rm, customer, lang, []) for rm in result.ranked]
    if moment_type:
        hit = next((m for m in moments if m["type"] == moment_type), None)
        if hit:
            return hit
    return next((m for m in moments if m["delivery"] == "now"), moments[0] if moments else None)


# ---------------------------------------------------------------- intents --

def _detect(text: str) -> str:
    folded = _fold(text)
    if any(cur for _, cur in amounts(text)):
        return "goal"
    for intent in ("spending", "upcoming", "save_more", "why"):
        if any(k in folded for k in KEYWORDS[intent]):
            return intent
    return "goal" if re.search(r"\d", text) else "clarify"


def _spending(customer: Customer, lang: str, ctx: TalkContext | None) -> TalkResponse:
    today = config.today()
    s = spending.summarize(customer, today, 3, lang)
    a, b = s["from"], s["to"]
    if s["largest"]:
        big = s["largest"]
        msg = {"nl": f"Je gaf {_eur(s['spending'], lang)} uit. Grootste post: {big['label']} ({s['largest_share']}%).",
               "en": f"You spent {_eur(s['spending'], lang)}. Largest: {big['label']} ({s['largest_share']}%).",
               "fr": f"Vous avez dépensé {_eur(s['spending'], lang)}. Premier poste : {big['label']} ({s['largest_share']} %)."}[lang]
    else:
        msg = {"nl": "Geen uitgaven in deze periode.", "en": "No spending in this period.",
               "fr": "Aucune dépense sur cette période."}[lang]
    if s["rises"]:
        r = s["rises"][0]
        lab = spending.label(r["key"], lang)
        msg += " " + {
            "nl": f"{lab} was in {_capi().MONTHS[lang][b.month - 1]} {_eur(r['last_month'], lang)}, {r['pct']}% boven je gemiddelde van {_eur(r['average'], lang)}.",
            "en": f"{lab} was {_eur(r['last_month'], lang)} in {_capi().MONTHS[lang][b.month - 1]}, {r['pct']}% above your {_eur(r['average'], lang)} average.",
            "fr": f"{lab} : {_eur(r['last_month'], lang)} en {_capi().MONTHS[lang][b.month - 1]}, {r['pct']} % au-dessus de votre moyenne de {_eur(r['average'], lang)}."}[lang]
    return _resp(
        "spending", msg, lang, _ctx(ctx), _sugg(lang, "save_more", "upcoming", "why"),
        period={"from": a.isoformat(), "to": b.isoformat(), "label": _period_label(a, b, lang)},
        chart={"kind": "category_bars", "unit": "eur", "rows": s["rows"], "total": s["spending"]},
        facts=[Fact(label=L["income"][lang], value=s["income"]), Fact(label=L["spending"][lang], value=s["spending"]),
               Fact(label=L["saving"][lang], value=s["saving"])],
        evidence=[f"transactions {a.isoformat()}..{b.isoformat()}: spending = amount<0 excluding income categories "
                  f"and pension_saving; net {s['net']:.2f}"],
        assumptions=[SYNTH[lang]])


def _item(i: dict[str, Any]) -> dict[str, Any]:
    if i["type"].startswith("goal"):
        basis = "customer_goal"
    elif i["source"] == "world_rule":
        basis = "legal"
    else:
        basis = BASIS_BY_TYPE.get(i["type"], "estimate_from_history")
    return {"date": i["date"], "end": i.get("end"), "kind": i["kind"], "type": i["type"], "title": i["title"],
            "basis": basis}


def _upcoming(customer: Customer, lang: str, ctx: TalkContext | None) -> TalkResponse:
    today = config.today()
    all_items = _capi()._timeline_items(customer, today, lang, 365)
    limit = (today + timedelta(days=90)).isoformat()
    items = [_item(i) for i in all_items if i["date"] <= limit]
    later = [_item(i) for i in all_items if i["date"] > limit]
    end = today + timedelta(days=90)
    if items:
        first = items[0]
        d = _fmt(date.fromisoformat(first["date"]), lang)
        what = {"reminder_window": {"nl": f"relevant vanaf {d}", "en": f"relevant from {d}", "fr": f"pertinent dès le {d}"}}
        when = what.get(first["kind"], {"nl": d, "en": d, "fr": d})[lang]
        msg = {"nl": f"{len(items)} dingen in de komende 90 dagen. Eerst: {first['title']} ({when}).",
               "en": f"{len(items)} things in the next 90 days. First: {first['title']} ({when}).",
               "fr": f"{len(items)} éléments dans les 90 prochains jours. D'abord : {first['title']} ({when})."}[lang]
        chart_items = items
    elif later:
        nxt = later[0]
        d = _fmt(date.fromisoformat(nxt["date"]), lang)
        msg = {"nl": f"Niets in de komende 90 dagen. Daarna: {nxt['title']} ({d}).",
               "en": f"Nothing in the next 90 days. After that: {nxt['title']} ({d}).",
               "fr": f"Rien dans les 90 prochains jours. Ensuite : {nxt['title']} ({d})."}[lang]
        chart_items = [nxt]
    else:
        msg = {"nl": "Niets gepland in het komende jaar.", "en": "Nothing known in the coming year.",
               "fr": "Rien de prévu dans l'année à venir."}[lang]
        chart_items = []
    return _resp("upcoming", msg, lang, _ctx(ctx), _sugg(lang, "why", "spending", "goal"),
                 period={"from": today.isoformat(), "to": end.isoformat(), "label": _period_label(today, end, lang)},
                 chart={"kind": "timeline", "items": chart_items},
                 evidence=["same items as GET /me/timeline2?days=90"], assumptions=[SYNTH[lang]])


def _summary(p: dict[str, Any], lang: str) -> str:
    return f"{PURPOSE[p['purpose']][lang]} · {_eur(p['amount'], lang)} · {(KEEP if p['keep_accessible'] else LOCKED)[lang]}"


def _goal(customer: Customer, text: str, lang: str, ctx: TalkContext | None) -> TalkResponse:
    p = parse_goal(text, lang)
    if not p:
        return _clarify(lang, ctx)
    prop = Proposal(purpose=p["purpose"], amount=p["amount"], keep_accessible=p["keep_accessible"],
                    summary=_summary(p, lang))
    msg = {"nl": f"Zal ik dit als doel bewaren? {prop.summary}. Er wordt geen geld verplaatst.",
           "en": f"Shall I save this as a goal? {prop.summary}. No money is moved.",
           "fr": f"J'enregistre cet objectif ? {prop.summary}. Aucun argent n'est déplacé."}[lang]
    return _resp("goal_proposal", msg, lang, _ctx(ctx), _sugg(lang, "why", "upcoming"), proposal=prop)


def _alloc_chart(alloc: dict[str, Any], lang: str) -> dict[str, Any]:
    segs = [{"key": "buffer", "label": L["buffer"][lang], "value": round(min(alloc["buffer"], alloc["savings"]), 2)}]
    for r in alloc["reserved"]:
        segs.append({"key": f"goal:{r['goal_id']}", "label": PURPOSE.get(r["purpose"], PURPOSE["other"])[lang],
                     "value": r["amount"]})
    segs.append({"key": "remaining", "label": L["remaining"][lang], "value": alloc["remaining"]})
    return {"kind": "allocation", "segments": segs, "total": alloc["savings"]}


def _why(customer: Customer, lang: str, ctx: TalkContext | None) -> TalkResponse:
    m = _priority(customer, lang, ctx.moment_type if ctx else None)
    if m is None:
        msg = {"nl": "Er is nu niets dat ik je aanraad.", "en": "There is nothing I'm suggesting right now.",
               "fr": "Je ne vous suggère rien pour le moment."}[lang]
        return _resp("why", msg, lang, _ctx(ctx), _sugg(lang, "spending", "upcoming"))
    alloc = allocation.compute(customer)
    msg = (m["why"] or m["message"]).strip()
    words = msg.split()
    if len(words) > 45:
        msg = " ".join(words[:45]) + "…"
    facts, chart = [], None
    if m["type"] == "idle_cash":
        facts = [Fact(label=L["buffer"][lang], value=alloc["buffer"]),
                 Fact(label=L["reserved"][lang], value=alloc["reserved_total"]),
                 Fact(label=L["remaining"][lang], value=alloc["remaining"])]
        chart = _alloc_chart(alloc, lang)
    return _resp("why", msg, lang, _ctx(ctx, m["type"]), _sugg(lang, "upcoming", "spending", "goal"),
                 chart=chart, facts=facts,
                 evidence=list(m["evidence"]) + [f"goals reserved_total {alloc['reserved_total']:.2f}"],
                 assumptions=list(m["why_reasons"]) + [BUFFER_ASSUMPTION[lang]])


def _save_more(customer: Customer, lang: str, ctx: TalkContext | None) -> TalkResponse:
    s = spending.summarize(customer, config.today(), 3, lang)
    obs = []
    for r in s["rows"][:3]:
        monthly = r["value"] / 3
        obs.append({"nl": f"{r['label']}: gemiddeld {_eur(monthly, lang)}/maand; 10% minder = {_eur(monthly * 0.1, lang)}/maand.",
                    "en": f"{r['label']}: {_eur(monthly, lang)}/month on average; 10% less = {_eur(monthly * 0.1, lang)}/month.",
                    "fr": f"{r['label']} : {_eur(monthly, lang)}/mois en moyenne ; 10 % de moins = {_eur(monthly * 0.1, lang)}/mois."}[lang])
    msg = {"nl": "Drie scenario's op basis van je grootste uitgaven.", "en": "Three scenarios from your largest spending.",
           "fr": "Trois scénarios basés sur vos plus grosses dépenses."}[lang] if obs else \
        {"nl": "Geen uitgaven gemeten.", "en": "No spending measured.", "fr": "Aucune dépense mesurée."}[lang]
    a, b = s["from"], s["to"]
    return _resp("save_more", msg, lang, _ctx(ctx), _sugg(lang, "spending", "goal", "upcoming"),
                 period={"from": a.isoformat(), "to": b.isoformat(), "label": _period_label(a, b, lang)},
                 chart={"kind": "category_bars", "unit": "eur", "rows": s["rows"][:3],
                        "total": round(sum(r["value"] for r in s["rows"][:3]), 2)},
                 evidence=obs, assumptions=[SCENARIO[lang], SYNTH[lang]])


def _clarify(lang: str, ctx: TalkContext | None) -> TalkResponse:
    msg = {"nl": "Dat begrijp ik niet. Je kunt me dit vragen:", "en": "I didn't get that. You can ask me:",
           "fr": "Je n'ai pas compris. Vous pouvez me demander :"}[lang]
    return _resp("clarify", msg, lang, _ctx(ctx), _sugg(lang, "spending", "upcoming", "goal", "why"))


# ----------------------------------------------------------------- routes --

@router.get("/me/talk/briefing", response_model=TalkResponse)
def briefing(customer_id: str = Depends(auth.current_customer_id), lang: Lang = LANG_QUERY) -> TalkResponse:
    customer = _load(customer_id, lang)
    m = _priority(customer, lang)
    if m is None:
        msg = {"nl": "Alles rustig vandaag.", "en": "All quiet today.", "fr": "Tout est calme aujourd'hui."}[lang]
        return _resp("briefing", msg, lang, {"moment_type": None, "period_days": 90}, _sugg(lang, "spending", "upcoming"))
    msg = f"{m['title']}. {m['message']}".strip()
    sentences = re.split(r"(?<=[.!?])\s+", msg)
    msg = " ".join(sentences[:2])
    return _resp("briefing", msg, lang, {"moment_type": m["type"], "period_days": 90},
                 _sugg(lang, "why", "upcoming", "spending"), evidence=list(m["evidence"]))


@router.post("/me/talk", response_model=TalkResponse)
def talk(body: TalkRequest, customer_id: str = Depends(auth.current_customer_id),
         lang: Lang = LANG_QUERY) -> TalkResponse:
    customer = _load(customer_id, lang)
    intent = _detect(body.text)
    if intent == "spending":
        return _spending(customer, lang, body.context)
    if intent == "upcoming":
        return _upcoming(customer, lang, body.context)
    if intent == "goal":
        return _goal(customer, body.text, lang, body.context)
    if intent == "why":
        return _why(customer, lang, body.context)
    if intent == "save_more":
        return _save_more(customer, lang, body.context)
    return _clarify(lang, body.context)


@router.post("/me/talk/goal/confirm", response_model=TalkResponse)
def confirm_goal(body: GoalConfirm, customer_id: str = Depends(auth.current_customer_id),
                 lang: Lang = LANG_QUERY) -> TalkResponse:
    import goals_api
    api = _api()
    api._customer(customer_id)
    goal = Goal(id="g_" + secrets.token_hex(6), purpose=body.purpose, amount=body.amount,
                keep_accessible=body.keep_accessible, created=config.today())
    try:
        api.store.add_goal(customer_id, goal)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    goals_api._log(customer_id, "goal_set", goal)
    customer = _load(customer_id, lang)
    alloc = allocation.compute(customer)
    rem = _eur(alloc["remaining"], lang)
    msg = {"nl": f"Doel bewaard. Vrij spaargeld is nu {rem}. Er is geen geld verplaatst.",
           "en": f"Goal saved. Remaining savings are now {rem}. No money was moved.",
           "fr": f"Objectif enregistré. L'épargne disponible est maintenant de {rem}. Aucun argent n'a été déplacé."}[lang]
    if alloc["shortfall"] > 0:
        msg += " " + {"nl": f"Je komt {_eur(alloc['shortfall'], lang)} tekort boven je buffer.",
                      "en": f"You are {_eur(alloc['shortfall'], lang)} short above your buffer.",
                      "fr": f"Il manque {_eur(alloc['shortfall'], lang)} au-delà de votre réserve."}[lang]
    return _resp("goal_saved", msg, lang, {"moment_type": "idle_cash", "period_days": 90},
                 _sugg(lang, "why", "upcoming", "spending"), chart=_alloc_chart(alloc, lang),
                 facts=[Fact(label=L["remaining"][lang], value=alloc["remaining"])],
                 evidence=[f"goal {goal.id} stored; allocation recomputed"],
                 assumptions=[BUFFER_ASSUMPTION[lang]])
