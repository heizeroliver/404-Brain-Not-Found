"""Rent -> first home: renting for 3+ years, €20,000+ saved, age 25-40.

Registration duty: 2% in Flanders, 3% in Wallonia, €200,000 abattement in Brussels.
100% loan-to-value for first-time buyers. Average first buyer is 26-35.
"""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur, years_between

TYPE = "first_home_readiness"
CATEGORY = "sales"
REQUIRES_INSURANCE_DATA = False
DUTY = {"flanders": "2% registration duty", "wallonia": "3% registration duty",
        "brussels": "€200,000 abattement on registration duty"}
DUTY_PCT = {"flanders": 2, "wallonia": 3, "brussels": None}


def detect(customer: Customer, today: date) -> list[Moment]:
    h = customer.housing
    if h.status != "renting" or h.rent_since is None or customer.products.mortgage is not None:
        return []
    years = years_between(h.rent_since, today)
    savings = customer.accounts.savings_balance
    if years < 3 or savings < 20000 or not 25 <= customer.age <= 40:
        return []
    rent = h.monthly_rent or 0.0
    return [Moment(
        type=TYPE,
        window=(today, today + timedelta(days=90)),
        confidence=0.8,
        stakes="medium",
        evidence=[
            f"renting for {years} years ({eur(rent)}/month to {h.landlord} since {h.rent_since.isoformat()})",
            f"{eur(savings)} on the savings account",
            f"age {customer.age}: the average first-time buyer is 26-35",
            f"{customer.region}: {DUTY[customer.region]}; 100% loan-to-value for first-time buyers",
        ],
        actions=["first_home_readiness_check", "mortgage_simulation", "talk_to_advisor", "not_planning_to_buy"],
        channel_hint="in_app_card",
        legal_basis="legitimate_interest",
        human_review=False,
        source="life_calendar",
        category=CATEGORY,
        facts={"years_renting": years, "monthly_rent": round(rent), "savings": round(savings),
               "region": customer.region, "duty_text": DUTY[customer.region],
               "duty_pct": DUTY_PCT[customer.region]},
    )]
