"""Small helpers shared by the life-calendar rules."""
from __future__ import annotations

from datetime import date

from engine.models import Customer, Transaction


def eur(amount: float) -> str:
    return f"€{amount:,.0f}"


def salary_transactions(customer: Customer) -> list[Transaction]:
    return [t for t in customer.transactions if t.category == "salary"]


def salary_alive(customer: Customer, today: date, max_gap_days: int = 45) -> bool:
    """True when the customer is an employee whose salary landed recently."""
    emp = customer.employment
    if emp.contract_type not in ("permanent", "temporary") or not emp.employer:
        return False
    salaries = salary_transactions(customer)
    if not salaries:
        return False
    last = max(t.date for t in salaries)
    return 0 <= (today - last).days <= max_gap_days


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def years_between(d1: date, d2: date) -> int:
    years = d2.year - d1.year
    if (d2.month, d2.day) < (d1.month, d1.day):
        years -= 1
    return years
