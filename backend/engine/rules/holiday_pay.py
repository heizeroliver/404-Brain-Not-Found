"""Dubbel vakantiegeld / double pécule de vacances: May, ~92% of a gross month.

Predicted from the employer salary pattern (last year's holiday-pay credit when
present, otherwise 92% of the gross monthly salary on 22 May).
"""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur, salary_alive, salary_transactions

TYPE = "holiday_pay"
CATEGORY = "sales"
REQUIRES_INSURANCE_DATA = False
LOOKAHEAD_DAYS = 45


def detect(customer: Customer, today: date) -> list[Moment]:
    if not salary_alive(customer, today):
        return []
    emp = customer.employment
    if emp.gross_monthly_salary <= 0:
        return []
    last_salary = max(t.date for t in salary_transactions(customer))
    history = [t for t in customer.transactions if t.category == "holiday_pay"]
    if history:
        ref = max(history, key=lambda t: t.date)
        pay_day, amount, confidence = ref.date.day, ref.amount, 0.9
        basis = f"last year's holiday pay of {eur(ref.amount)} on {ref.date.isoformat()}"
    else:
        pay_day, amount, confidence = 22, 0.92 * emp.gross_monthly_salary, 0.7
        basis = "about 92% of a gross month (no holiday-pay credit in the last 12 months)"
    expected = date(today.year, 5, min(pay_day, 31))
    if expected < today:
        expected = date(today.year + 1, 5, min(pay_day, 31))
    days = (expected - today).days
    if days > LOOKAHEAD_DAYS:
        return []
    return [Moment(
        type=TYPE,
        window=(max(today, expected - timedelta(days=14)), expected),
        confidence=confidence,
        stakes="medium",
        evidence=[
            f"monthly salary from {emp.employer} (last credit {last_salary.isoformat()})",
            f"holiday pay of ~{eur(amount)} expected on {expected.isoformat()}: {basis}",
        ],
        actions=["plan_holiday_pay", "move_to_savings", "start_investment_plan", "keep_on_current_account"],
        channel_hint="in_app_card",
        legal_basis="legitimate_interest",
        human_review=False,
        source="life_calendar",
        category=CATEGORY,
        facts={"amount": round(amount), "expected_date": expected.isoformat(), "days": days,
               "employer": emp.employer},
    )]
