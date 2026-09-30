"""Energy bill spike: the latest energy invoice is well above the customer's own earlier average."""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur

TYPE = "energy_bill_spike"
CATEGORY = "info"
REQUIRES_INSURANCE_DATA = False
PROJECTABLE = False
MIN_INCREASE = 0.25


def detect(customer: Customer, today: date) -> list[Moment]:
    energy = sorted((t for t in customer.transactions if t.category == "energy" and t.amount < 0
                     and t.date <= today), key=lambda t: t.date)
    if len(energy) < 6:
        return []
    last3 = energy[-3:]
    before = energy[:-3][-6:]
    recent = sum(-t.amount for t in last3) / len(last3)
    base = sum(-t.amount for t in before) / len(before)
    if base <= 0 or recent < base * (1 + MIN_INCREASE):
        return []
    pct = (recent / base - 1) * 100
    payee = last3[-1].payee
    return [Moment(
        type=TYPE,
        window=(today, today + timedelta(days=30)),
        confidence=0.85,
        stakes="medium",
        evidence=[f"average energy invoice last 3 months {eur(recent)} vs {eur(base)} before (+{pct:.0f}%)",
                  f"latest invoice via {payee} on {last3[-1].date.isoformat()}"],
        actions=["check_energy_contract", "adjust_monthly_budget", "energy_renovation_loan"],
        channel_hint="in_app_card",
        legal_basis="legitimate_interest",
        human_review=False,
        source="life_calendar",
        category=CATEGORY,
        facts={"recent": round(recent), "base": round(base), "pct": round(pct)},
    )]
