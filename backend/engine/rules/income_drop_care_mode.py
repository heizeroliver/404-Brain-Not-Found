"""Income drop: salary stopped for 2+ months -> care mode (option C, protection).

High stakes, human review, no sales. Unemployment benefits are capped at
24 months since 1 Mar 2026; CCD2 forbearance duties apply from 20 Nov 2026.
"""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur, salary_transactions

TYPE = "income_drop_care_mode"
CATEGORY = "care"
REQUIRES_INSURANCE_DATA = False
MIN_GAP_DAYS = 60
FIXED_COSTS = {"rent", "mortgage", "energy", "telecom", "childcare", "insurance"}


def detect(customer: Customer, today: date) -> list[Moment]:
    emp = customer.employment
    if emp.contract_type not in ("permanent", "temporary") or not emp.employer:
        return []
    salaries = salary_transactions(customer)
    if not salaries:
        return []
    last = max(t.date for t in salaries)
    days = (today - last).days
    if days < MIN_GAP_DAYS:
        return []
    benefits = [t for t in customer.transactions if t.category == "benefit" and t.date > last]
    since = today - timedelta(days=90)
    fixed = sum(-t.amount for t in customer.transactions
                if t.category in FIXED_COSTS and t.amount < 0 and t.date >= since) / 3.0
    if benefits:
        replacement = f"unemployment benefit received since {min(t.date for t in benefits).isoformat()}"
    else:
        replacement = "no replacement income detected"
    return [Moment(
        type=TYPE,
        window=(today, today + timedelta(days=90)),
        confidence=0.85,
        stakes="high",
        evidence=[
            f"last salary from {emp.employer} on {last.isoformat()} ({days} days ago)",
            replacement,
            f"fixed costs of about {eur(fixed)}/month (housing, energy, telecom, childcare, insurance)",
            "unemployment benefits are capped at 24 months since 1 Mar 2026",
        ],
        actions=["budget_coach", "payment_plan", "talk_to_advisor"],
        channel_hint="advisor",
        legal_basis="legal_obligation_ccd2_forbearance",
        human_review=True,
        source="protection",
        category=CATEGORY,
        facts={"employer": emp.employer, "last_salary_date": last.isoformat(), "days": days,
               "fixed_costs": round(fixed), "benefit": bool(benefits)},
    )]
