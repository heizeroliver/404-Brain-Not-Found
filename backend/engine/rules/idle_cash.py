"""Idle cash: savings above 6x monthly net income for more than 6 months and above €15,000."""
from __future__ import annotations

from datetime import date, timedelta

from engine import allocation
from engine.models import Customer, Moment
from engine.rules.common import eur

TYPE = "idle_cash"
CATEGORY = "sales"
REQUIRES_INSURANCE_DATA = False
PROJECTABLE = False  # state-based: only evaluated for today
MIN_BALANCE = 15000.0
MONTHS = allocation.BUFFER_MONTHS
MIN_IDLE = 2000.0  # below this, after the customer's reserved goals, there is nothing to say


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
    # The customer's own goals come first: money she said to keep available is not idle.
    # Same numbers as GET /me/overview's allocation (engine/allocation.py).
    alloc = allocation.compute(customer)
    reserved_goals = [g for g in customer.goals if g.keep_accessible]
    reserved = alloc["reserved_total"]
    idle = alloc["remaining"]
    if reserved and idle < MIN_IDLE:
        return []
    evidence = [
        f"savings balance {eur(balance)} stayed above {eur(threshold)} for {MONTHS} months "
        f"({MONTHS} x net monthly income {eur(net)})",
        *(f"{eur(g.amount)} reserved for your {g.purpose.replace('_', ' ')} "
          f"(your own goal, set {g.created.isoformat()})" for g in reserved_goals),
        f"about {eur(idle)} above a {MONTHS}-month buffer"
        + (f" and your reserved {eur(reserved)}" if reserved else ""),
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
