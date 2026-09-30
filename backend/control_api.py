"""Control room v2 (admin only), see docs/CONTRACT.md.

  GET   /admin/v2/overview
  GET   /admin/v2/moments
  GET   /admin/v2/advisor-requests, PATCH /admin/v2/advisor-requests/{id}
  GET   /admin/v2/rule-template
  POST  /admin/v2/rules/preview   (never mutates the rulebook)
  POST  /admin/v2/rules/activate
  GET   /admin/v2/audit

Everything is computed with record=False: looking at the control room never changes
what a customer sees (no deliveries recorded, no decision log entries from arbitration).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict

import auth
import config
import requests_store
from engine.arbitrate import ArbitrationResult, arbitrate
from engine.models import Customer, Moment
from engine.rules import run_rules
from engine.rules.rulebook import RULEBOOK, ConditionOp, WorldRule
from engine.twin import build_twin

router = APIRouter()

REQUEST_ID = r"^AR-[0-9A-F]{6}$"
SLUG = r"^[a-z0-9_]{1,60}$"


def _api() -> Any:
    import api  # late import: api.py includes this router
    return api


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(principal: auth.Principal, decision: str, reason: str, moment_type: str | None = None,
         source: str | None = None, stakes: str | None = None) -> None:
    _api().store.log_decisions([{
        "ts": _now(), "customer_id": principal.subject, "moment_type": moment_type, "source": source,
        "stakes": stakes, "decision": decision, "reason": reason[:200], "score": None, "channel": None,
        "delivery": None}])


# ------------------------------------------------------------ computation --

class _Feed:
    __slots__ = ("customer", "moments", "result")

    def __init__(self, customer: Customer, moments: list[Moment], result: ArbitrationResult) -> None:
        self.customer, self.moments, self.result = customer, moments, result


def _feeds(today: date) -> list[_Feed]:
    store = _api().store
    out: list[_Feed] = []
    for customer in store.customers.values():
        c = store.with_goals(customer)
        moments = run_rules(c, today)
        out.append(_Feed(c, moments, arbitrate(c, moments, today, store, record=False)))
    return out


def _channel_reason(moment: Moment, customer: Customer, channel: str) -> str:
    if channel == "advisor":
        if moment.stakes == "high":
            return "high stakes"
        if moment.human_review:
            return "human review required"
        return "low digital comfort"
    if channel == "voice":
        return "65+ and NL/FR speaker"
    return "default"


def _items(feed: _Feed) -> list[dict[str, Any]]:
    """One row per detected moment (shown, queued or suppressed) with its decision path."""
    c = feed.customer
    by_type = {m.type: m for m in feed.moments}
    ranked = {rm.moment.type: rm for rm in feed.result.ranked}
    rows: list[dict[str, Any]] = []
    for d in feed.result.decisions:
        m = by_type.get(d["moment_type"])
        if m is None:
            continue
        path = [f"detected ({m.source})"]
        if feed.result.care_mode:
            path.append("care mode active")
        if d["decision"] == "dropped":
            path.append(f"dropped: {d['reason']}")
            rows.append({"customer_id": c.id, "customer_name": c.name, "type": m.type, "source": m.source,
                         "stakes": m.stakes, "channel": None, "delivery": None, "status": "suppressed",
                         "reason": d["reason"], "window": [m.window[0].isoformat(), m.window[1].isoformat()],
                         "evidence": list(m.evidence), "decision_path": path})
            continue
        rm = ranked.get(m.type)
        if rm is None:
            continue
        path.append(f"ranked {rm.rank} (score {rm.score:g})")
        path.append(f"channel {rm.channel}: {_channel_reason(m, c, rm.channel)}")
        path.append(f"delivery {rm.delivery}: {d['reason']}")
        rows.append({"customer_id": c.id, "customer_name": c.name, "type": m.type, "source": m.source,
                     "stakes": m.stakes, "channel": rm.channel, "delivery": rm.delivery,
                     "status": "shown" if rm.delivery == "now" else "queued", "reason": d["reason"],
                     "window": [m.window[0].isoformat(), m.window[1].isoformat()],
                     "evidence": list(m.evidence), "decision_path": path})
    return rows


def _suppression_key(reason: str) -> str:
    if reason.startswith("customer feedback"):
        return "customer_feedback"
    return {"marketing consent off": "marketing_consent_off",
            "vulnerability guard: care mode active, no sales": "care_mode",
            "window expired": "window_expired"}.get(reason, reason.replace(" ", "_")[:40])


# ----------------------------------------------------------------- routes --

METRICS = [
    ("customers_with_moment", "customers", "Customers with at least one ranked moment today."),
    ("moments_total", "moments", "Ranked moments today across all customers (after arbitration)."),
    ("advisor_routing_recommended", "moments",
     "Ranked moments whose recommended channel is an advisor (a routing recommendation, not a request)."),
    ("advisor_requests_open", "requests", "Advisor requests customers created that are requested or in review."),
]


@router.get("/admin/v2/overview")
def overview(_: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    today = config.today()
    feeds = _feeds(today)
    by_type: Counter[str] = Counter()
    by_channel: Counter[str] = Counter()
    with_moment = care = suppressed = 0
    for f in feeds:
        if f.result.ranked:
            with_moment += 1
        if f.result.care_mode:
            care += 1
        suppressed += sum(1 for d in f.result.decisions if d["decision"] == "dropped")
        for rm in f.result.ranked:
            by_type[rm.moment.type] += 1
            by_channel[rm.channel] += 1
    open_requests = sum(1 for r in requests_store.all_requests() if r["status"] in requests_store.OPEN)
    values = {"customers_with_moment": with_moment, "moments_total": sum(by_type.values()),
              "advisor_routing_recommended": by_channel.get("advisor", 0), "advisor_requests_open": open_requests}
    return {
        "today": today.isoformat(),
        "cohort": {"customers": len(feeds)},
        "metrics": [{"key": k, "label_key": f"metric_{k}", "value": values[k], "unit": unit,
                     "definition_key": f"def_{k}", "definition": text} for k, unit, text in METRICS],
        "moments_by_type": [{"key": k, "value": v} for k, v in by_type.most_common()],
        "channel_recommendations": [{"key": k, "value": v} for k, v in by_channel.most_common()],
        "attention": [
            {"kind": "advisor_requests_open", "text_key": "att_advisor_requests_open", "count": open_requests},
            {"kind": "care_mode", "text_key": "att_care_mode", "count": care},
            {"kind": "suppressed", "text_key": "att_suppressed", "count": suppressed},
        ],
        "computed_at": _now(),
    }


@router.get("/admin/v2/moments")
def moments(_: auth.Principal = Depends(auth.require_admin),
            type: str | None = Query(None, pattern=SLUG),
            source: Literal["life_calendar", "world_rule", "protection"] | None = None,
            channel: Literal["in_app_card", "push", "voice", "advisor", "letter"] | None = None,
            status_: Literal["shown", "queued", "suppressed"] | None = Query(None, alias="status"),
            q: str | None = Query(None, max_length=60),
            page: int = Query(1, ge=1, le=10_000),
            page_size: int = Query(25, ge=10, le=100)) -> dict[str, Any]:
    rows = [row for f in _feeds(config.today()) for row in _items(f)]
    needle = (q or "").strip().lower()
    rows = [r for r in rows
            if (not type or r["type"] == type) and (not source or r["source"] == source)
            and (not channel or r["channel"] == channel) and (not status_ or r["status"] == status_)
            and (not needle or needle in r["customer_id"].lower() or needle in r["customer_name"].lower()
                 or needle in r["type"])]
    start = (page - 1) * page_size
    return {"total_moments": len(rows), "total_customers": len({r["customer_id"] for r in rows}),
            "page": page, "page_size": page_size, "items": rows[start:start + page_size]}


def _with_customer(r: dict[str, Any]) -> dict[str, Any]:
    c = _api().store.get_customer(r["customer_id"])
    return {**r, "customer_name": c.name if c else None}


@router.get("/admin/v2/advisor-requests")
def advisor_requests(_: auth.Principal = Depends(auth.require_admin),
                     status_: Literal["", "requested", "in_review", "resolved"] = Query("", alias="status")
                     ) -> dict[str, Any]:
    items = sorted(requests_store.all_requests(status_ or None), key=lambda r: r["created"], reverse=True)
    return {"items": [_with_customer(r) for r in items]}


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["in_review", "resolved"]


@router.patch("/admin/v2/advisor-requests/{request_id}")
def update_request(body: StatusUpdate, request_id: str = Path(pattern=REQUEST_ID),
                   principal: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    updated = requests_store.set_status(request_id, body.status)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown advisor request")
    _log(principal, "advisor_request_status", f"{request_id} ({updated['customer_id']}) -> {body.status}",
         moment_type=updated["moment_type"])
    return _with_customer(updated)


CONDITION_OPS: list[str] = list(ConditionOp.__args__)  # type: ignore[attr-defined]


def _condition_fields() -> list[str]:
    store = _api().store
    customer = next(iter(store.customers.values()), None)
    if customer is None:
        return []
    twin = build_twin(customer, config.today())
    return sorted(k for k, v in twin.items() if not isinstance(v, (list, dict)))


EXAMPLE_RULE: dict[str, Any] = {
    "id": "savings_exemption_2027",
    "title": {"en": "Savings-account interest exemption replaced by a €6,000 investment-income exemption",
              "nl": "Spaarvrijstelling vervangen door een vrijstelling van €6.000 op beleggingsinkomsten",
              "fr": "L'exonération de l'épargne remplacée par une exonération de 6 000 € sur les revenus d'investissement"},
    "summary": {"en": "From 1 January 2027 the savings-account exemption is replaced by a €6,000 investment-income "
                      "exemption. Your savings of €{savings_balance} are affected.",
                "nl": "Vanaf 1 januari 2027 vervangt een vrijstelling van €6.000 op beleggingsinkomsten de "
                      "spaarvrijstelling. Je spaargeld van €{savings_balance} valt eronder.",
                "fr": "Dès le 1er janvier 2027, une exonération de 6 000 € sur les revenus d'investissement remplace "
                      "l'exonération de l'épargne. Votre épargne de {savings_balance} € est concernée."},
    "cta": {"en": "Explain it to me", "nl": "Leg het me uit", "fr": "Expliquez-moi"},
    "effective_date": "2027-01-01",
    "level": "federal",
    "conditions": [{"field": "savings_balance", "op": "gt", "value": 20000}],
    "impact": {"kind": "none", "direction": "neutral"},
    "evidence": ["savings balance €{savings_balance} above €20,000",
                 "budget agreement (illustrative headline for the demo)"],
    "actions": ["explain_change", "talk_to_advisor"],
    "stakes": "medium",
    "source_url": None,
}


@router.get("/admin/v2/rule-template")
def rule_template(_: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    return {
        "illustrative": True,
        "note": "Illustrative example for the demo, not an adopted law.",
        "rule": EXAMPLE_RULE,
        "form_fields": ["id", "title", "effective_date", "level", "conditions", "impact", "source_url"],
        "levels": ["eu", "federal", "regional", "kbc"],
        "stakes": ["low", "medium", "high"],
        "impact_kinds": ["none", "pct_above_exemption", "pct_of_field", "yearly_schedule"],
        "condition_fields": _condition_fields(),
        "condition_ops": CONDITION_OPS,
    }


class RuleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: WorldRule


def _visible(rule: WorldRule, today: date) -> bool:
    return (rule.visible_from or rule.effective_date) <= today <= (rule.visible_until or today)


@router.post("/admin/v2/rules/preview")
def preview(body: RuleBody, _: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    rule = body.rule
    store = _api().store
    today = config.today()
    visible = _visible(rule, today)
    affected: list[str] = []
    total_impact = 0.0
    suppressed: Counter[str] = Counter()
    for customer in store.customers.values():
        if rule.requires_insurance_data and not customer.consents.use_insurance_data:
            continue
        c = store.with_goals(customer)
        twin = build_twin(c, today)
        if not rule.affected(twin):
            continue
        affected.append(customer.id)
        amount = rule.impact.compute(twin, today).get("amount")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            total_impact += float(amount)
        if visible:  # would it survive arbitration today? (record=False: nothing is stored)
            existing = [m for m in run_rules(c, today) if m.type != rule.id]
            result = arbitrate(c, [*existing, rule.to_moment(twin, today)], today, store, record=False)
            for d in result.decisions:
                if d["moment_type"] != rule.id:
                    continue
                if d["decision"] == "dropped":
                    suppressed[_suppression_key(d["reason"])] += 1
                elif d.get("delivery") == "queued":
                    suppressed["frequency_cap"] += 1
    total = len(store.customers)
    when = ("visible today" if visible else
            f"visible from {(rule.visible_from or rule.effective_date).isoformat()}")
    summary = (f"'{rule.title['en']}' would apply to {len(affected)} of {total} customers "
               f"(effective {rule.effective_date.isoformat()}, {when}).")
    if total_impact:
        summary += f" Estimated total impact €{total_impact:,.0f} ({rule.impact.direction})."
    if RULEBOOK.get(rule.id) is not None:
        summary += " Note: a rule with this id already exists; activation would be refused."
    return {"affected": len(affected), "total": total, "sample": affected[:8], "changes_summary": summary,
            "total_impact": round(total_impact, 2), "visible_today": visible, "suppressed": dict(suppressed)}


@router.post("/admin/v2/rules/activate", status_code=status.HTTP_201_CREATED)
def activate(body: RuleBody, principal: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    rule = body.rule
    try:
        RULEBOOK.add(rule)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    store = _api().store
    today = config.today()
    affected: list[str] = []
    total_impact = 0.0
    for customer in store.customers.values():
        if rule.requires_insurance_data and not customer.consents.use_insurance_data:
            continue
        twin = build_twin(customer, today)
        if rule.affected(twin):
            affected.append(customer.id)
            amount = rule.impact.compute(twin, today).get("amount")
            if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                total_impact += float(amount)
    _log(principal, "rule_activated", f"{len(affected)} customers affected", moment_type=rule.id,
         source="world_rule", stakes=rule.stakes)
    return {"rule": rule.model_dump(mode="json"), "affected_customers": len(affected),
            "sample_customer_ids": affected[:8], "total_impact": round(total_impact, 2),
            "customers_total": len(store.customers)}


@router.get("/admin/v2/audit")
def audit(_: auth.Principal = Depends(auth.require_admin),
          q: str | None = Query(None, max_length=60),
          decision: str | None = Query(None, pattern=SLUG),
          page: int = Query(1, ge=1, le=10_000),
          page_size: int = Query(25, ge=10, le=100)) -> dict[str, Any]:
    store = _api().store
    customers = list(store.customers.values())
    consents: dict[str, dict[str, int]] = {}
    for c in customers:
        for k, v in c.consents.model_dump().items():
            slot = consents.setdefault(k, {"on": 0, "off": 0})
            slot["on" if v else "off"] += 1
    feedback = dict(Counter(fb["action"] for fb in store.feedback))
    reasons: Counter[str] = Counter()
    for f in _feeds(config.today()):
        for d in f.result.decisions:
            if d["decision"] == "dropped":
                reasons[_suppression_key(d["reason"])] += 1
            elif d.get("delivery") == "queued":
                reasons["frequency_cap"] += 1
    needle = (q or "").strip().lower()
    log = [e for e in reversed(store.decision_log)
           if (not decision or e.get("decision") == decision)
           and (not needle or any(needle in str(e.get(k) or "").lower()
                                  for k in ("customer_id", "moment_type", "reason", "decision")))]
    start = (page - 1) * page_size
    return {"consents": consents, "feedback": feedback,
            "suppressed_by_reason": [{"key": k, "value": v} for k, v in reasons.most_common()],
            "log": {"total": len(log), "page": page, "page_size": page_size, "items": log[start:start + page_size]}}
