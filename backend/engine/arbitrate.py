"""Arbitration: which moments a customer sees today, in which order, on which channel.

score = stakes_weight x urgency x confidence x affinity
then: consent filter, vulnerability guard (care mode drops every sales moment),
feedback suppression, frequency cap (one pushed moment per week unless stakes are
high), channel choice (advisor / voice / in-app card) and an append-only decision log.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel

from engine.models import Channel, Customer, Moment
from store import Store

STAKES_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 3.0}
CAP_DAYS = 7


class RankedMoment(BaseModel):
    rank: int
    score: float
    channel: Channel
    delivery: Literal["now", "queued"]
    moment: Moment


class ArbitrationResult(BaseModel):
    care_mode: bool
    ranked: list[RankedMoment]
    decisions: list[dict]


def urgency(moment: Moment, today: date) -> float:
    start, end = moment.window
    if end < today:
        return 0.0
    if start <= today:
        return 1.0
    return 1.0 / (1.0 + (start - today).days / 30.0)


def choose_channel(moment: Moment, customer: Customer) -> Channel:
    if moment.stakes == "high" or moment.human_review or customer.digital_comfort < 2:
        return "advisor"
    if customer.age >= 65 and customer.language in ("nl", "fr"):
        return "voice"
    return "in_app_card"


def arbitrate(customer: Customer, moments: list[Moment], today: date, store: Store,
              record: bool = True) -> ArbitrationResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    decisions: list[dict] = []

    def log(moment: Moment, decision: str, reason: str, score: float | None = None,
            channel: str | None = None, delivery: str | None = None) -> None:
        decisions.append({"ts": now, "customer_id": customer.id, "moment_type": moment.type,
                          "source": moment.source, "stakes": moment.stakes, "decision": decision,
                          "reason": reason, "score": None if score is None else round(score, 3),
                          "channel": channel, "delivery": delivery})

    care_mode = any(m.category == "care" for m in moments)
    scored: list[tuple[float, Moment]] = []
    for m in moments:
        if m.category == "sales" and not customer.consents.marketing:
            log(m, "dropped", "marketing consent off")
            continue
        if care_mode and m.category == "sales":
            log(m, "dropped", "vulnerability guard: care mode active, no sales")
            continue
        # protection and care moments cannot be switched off through feedback
        suppressed = None if m.category == "care" else store.is_suppressed(customer.id, m.type, today)
        if suppressed:
            log(m, "dropped", f"customer feedback: {suppressed}")
            continue
        u = urgency(m, today)
        if u == 0.0:
            log(m, "dropped", "window expired")
            continue
        score = STAKES_WEIGHT[m.stakes] * u * m.confidence * store.affinity(customer.id, m.type)
        scored.append((score, m))
    scored.sort(key=lambda s: (-s[0], s[1].type))

    recent = set(store.recent_deliveries(customer.id, today, CAP_DAYS))
    push_used = bool(recent)
    ranked: list[RankedMoment] = []
    for i, (score, m) in enumerate(scored, start=1):
        channel = choose_channel(m, customer)
        if m.stakes == "high":
            delivery, reason = "now", "high stakes: cap does not apply"
        elif m.type in recent:
            delivery, reason = "now", "already this week's pushed moment"
        elif not push_used:
            delivery, reason = "now", "this week's pushed moment"
            push_used = True
            if record:
                store.record_delivery(customer.id, m.type, today)
        else:
            delivery, reason = "queued", "frequency cap: one pushed moment per week"
        ranked.append(RankedMoment(rank=i, score=round(score, 3), channel=channel, delivery=delivery, moment=m))
        log(m, "ranked", reason, score, channel, delivery)
    if record:
        store.log_decisions(decisions)
    return ArbitrationResult(care_mode=care_mode, ranked=ranked, decisions=decisions)
