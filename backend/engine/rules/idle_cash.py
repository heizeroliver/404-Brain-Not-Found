"""Idle cash: savings above 6x monthly net income for more than 6 months and above €15,000."""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur

TYPE = "idle_cash"
CATEGORY = "sales"
REQUIRES_INSURANCE_DATA = False
MIN_BALANCE = 15000.0
MONTHS = 6


def detect(customer: Customer, today: date) -> list[Moment]:
    net = customer.employment.net_monthly_salary
    if net <= 0:
        return []
    history = customer.accounts.savings_history
    if len(history) < MONTHS:
        return []
    threshold = max(MIN_BALANCE, MONTHS * net)
    floor = min(b.balance for b in history[-MONTHS:])
    balance = customer.accounts.savings_balance
    if floor <= threshold or balance <= threshold:
        return []
    idle = balance - MONTHS * net
    evidence = [
        f"savings balance {eur(balance)} stayed above {eur(threshold)} for {MONTHS} months "
        f"({MONTHS} x net monthly income {eur(net)})",
        f"about {eur(idle)} above a {MONTHS}-month buffer",
    ]
    fidelity = customer.accounts.fidelity_date
    if fidelity and 0 <= (fidelity - today).days <= 60:
        evidence.append(f"fidelity premium date {fidelity.isoformat()}: moving money before it loses the premium")
    return [Moment(
        type=TYPE,
        window=(today, today + timedelta(days=30)),
        confidence=0.9,
        stakes="medium",
        evidence=evidence,
        actions=["compare_three_safe_options", "start_investment_plan", "keep_as_is"],
        channel_hint="in_app_card",
        legal_basis="legitimate_interest",
        human_review=False,
        source="life_calendar",
        category=CATEGORY,
        facts={"balance": round(balance), "idle": round(idle), "months": MONTHS,
               "fidelity_date": fidelity.isoformat() if fidelity else None},
    )]
