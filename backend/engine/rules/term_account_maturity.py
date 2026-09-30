"""Term account maturity: money is about to become free; offer the choice two weeks before."""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur

TYPE = "term_account_maturity"
CATEGORY = "sales"
REQUIRES_INSURANCE_DATA = False
PROJECTABLE = True
LOOKAHEAD_DAYS = 30


def detect(customer: Customer, today: date) -> list[Moment]:
    t = customer.products.term_account
    if t is None:
        return []
    days = (t.maturity_date - today).days
    if not 0 < days <= LOOKAHEAD_DAYS:
        return []
    return [Moment(
        type=TYPE,
        window=(today, t.maturity_date),
        confidence=0.99,  # contractual date
        stakes="medium",
        evidence=[f"term account of {eur(t.amount)} at {t.rate:.2f}% matures on {t.maturity_date.isoformat()} "
                  f"(in {days} days)",
                  "without instruction the money returns to the current account and earns nothing"],
        actions=["renew_term_account", "compare_three_safe_options", "talk_to_advisor"],
        channel_hint="in_app_card",
        legal_basis="contract_performance",
        human_review=False,
        source="life_calendar",
        category=CATEGORY,
        facts={"amount": round(t.amount), "maturity_date": t.maturity_date.isoformat(), "days": days},
    )]
