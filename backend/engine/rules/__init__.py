"""Rule registry: one module per moment, each exposing detect(customer, today) -> list[Moment]."""
from __future__ import annotations

from datetime import date
from types import ModuleType

from engine.models import Customer, Moment
from engine.rules import (child_turns_18, energy_bill_spike, first_home_readiness, holiday_pay,
                          idle_cash, income_drop_care_mode, insurance_renewal_increase,
                          payment_protection, rulebook, term_account_maturity,
                          year_end_bonus_pension_topup)

LIFE_CALENDAR_RULES: list[ModuleType] = [
    holiday_pay,
    year_end_bonus_pension_topup,
    insurance_renewal_increase,
    idle_cash,
    first_home_readiness,
    child_turns_18,
    income_drop_care_mode,
    term_account_maturity,
    energy_bill_spike,
    payment_protection,
]
ALL_RULES: list[ModuleType] = [*LIFE_CALENDAR_RULES, rulebook]


def run_rules(customer: Customer, today: date, include_world: bool = True,
              projectable_only: bool = False) -> list[Moment]:
    """Run every rule the customer's consents allow.

    projectable_only=True keeps only calendar-anchored rules (used when `today`
    is a future date on the 12-month timeline); state-based rules such as
    idle cash or an income drop are only meaningful for the real today.
    """
    moments: list[Moment] = []
    for module in ALL_RULES if include_world else LIFE_CALENDAR_RULES:
        if getattr(module, "REQUIRES_INSURANCE_DATA", False) and not customer.consents.use_insurance_data:
            continue
        if projectable_only and not getattr(module, "PROJECTABLE", False):
            continue
        moments.extend(module.detect(customer, today))
    return moments
