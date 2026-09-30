"""Eindejaarspremie in December: top up pension saving before 31 Dec.

Ceilings (2026): €1,050 at 30% tax relief or €1,350 at 25%.
"""
from __future__ import annotations

from datetime import date

from engine.models import Customer, Moment
from engine.rules.common import eur, salary_alive

TYPE = "year_end_bonus_pension_topup"
CATEGORY = "sales"
REQUIRES_INSURANCE_DATA = False
RELIEF = {1050: 30, 1350: 25}


def detect(customer: Customer, today: date) -> list[Moment]:
    if today.month not in (11, 12) or not salary_alive(customer, today):
        return []
    ps = customer.products.pension_saving
    if ps is None:
        return []
    room = ps.ceiling - ps.contributions_ytd - ps.monthly * (12 - today.month)
    if room <= 0:
        return []
    emp = customer.employment
    bonuses = [t for t in customer.transactions if t.category == "bonus"]
    if bonuses:
        ref = max(bonuses, key=lambda t: t.date)
        bonus, confidence = ref.amount, 0.85
        basis = f"paid by {emp.employer} on {ref.date.isoformat()} last year"
    else:
        bonus, confidence = 0.95 * emp.net_monthly_salary, 0.7
        basis = "estimated from the monthly salary"
    deadline = date(today.year, 12, 31)
    return [Moment(
        type=TYPE,
        window=(today, deadline),
        confidence=confidence,
        stakes="medium",
        evidence=[
            f"year-end bonus of ~{eur(bonus)} expected in December ({basis})",
            f"pension saving: {eur(ps.contributions_ytd)} of the {eur(ps.ceiling)} ceiling contributed this year, "
            f"{eur(room)} of room before 31 Dec",
            f"ceiling {eur(ps.ceiling)} gives {RELIEF[ps.ceiling]}% tax relief "
            f"(€1,050 at 30% or €1,350 at 25%)",
        ],
        actions=["top_up_pension_saving", "adjust_monthly_amount", "talk_to_advisor"],
        channel_hint="in_app_card",
        legal_basis="legitimate_interest",
        human_review=False,
        source="life_calendar",
        category=CATEGORY,
        facts={"bonus": round(bonus), "room": round(room), "ceiling": ps.ceiling,
               "ytd": round(ps.contributions_ytd), "relief_pct": RELIEF[ps.ceiling],
               "deadline": deadline.isoformat()},
    )]
