"""A child turns 18 within 60 days: student account, Groeipakket rules, student job 650 h/year."""
from __future__ import annotations

from datetime import date

from engine.models import Customer, Moment
from engine.rules.common import add_years

TYPE = "child_turns_18"
CATEGORY = "info"
REQUIRES_INSURANCE_DATA = False
LOOKAHEAD_DAYS = 60


def detect(customer: Customer, today: date) -> list[Moment]:
    moments: list[Moment] = []
    for child in customer.household.children:
        eighteenth = add_years(child.birthdate, 18)
        days = (eighteenth - today).days
        if 0 <= days <= LOOKAHEAD_DAYS:
            moments.append(Moment(
                type=TYPE,
                window=(today, eighteenth),
                confidence=0.99,  # birthdate on file
                stakes="medium",
                evidence=[
                    f"{child.name} turns 18 on {eighteenth.isoformat()} (in {days} days)",
                    "Groeipakket rules change at 18; a student job is allowed up to 650 hours/year",
                ],
                actions=["open_student_account", "first_tax_return_help", "kot_budget_plan"],
                channel_hint="in_app_card",
                legal_basis="legitimate_interest",
                human_review=False,
                source="life_calendar",
                category=CATEGORY,
                facts={"child_name": child.name, "date": eighteenth.isoformat(), "days": days},
            ))
    return moments
