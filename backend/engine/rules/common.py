"""Small helpers shared by the life-calendar rules."""
from __future__ import annotations

from datetime import date

from engine.models import Customer, Transaction


def eur(amount: float) -> str:
    return f"€{amount:,.0f}"


def salary_transactions(customer: Customer, today: date | None = None) -> list[Transaction]:
    """Salary credits, ignoring anything dated after `today`."""
    return [t for t in customer.transactions
            if t.category == "salary" and (today is None or t.date <= today)]


def as_of(customer: Customer, today: date) -> date:
    """The date the transaction data is current to: never later than the last transaction.

    Lets calendar rules be projected into the future (timeline) without reading
    the end of the dataset as "income stopped".
    """
    known = [t.date for t in customer.transactions if t.date <= today]
    if not known:
        return today
    return max(known)


def salary_alive(customer: Customer, today: date, max_gap_days: int = 45) -> bool:
    """True when the customer is an employee whose salary landed recently (as of the data horizon)."""
    emp = customer.employment
    if emp.contract_type not in ("permanent", "temporary") or not emp.employer:
        return False
    salaries = salary_transactions(customer, today)
    if not salaries:
        return False
    last = max(t.date for t in salaries)
    return 0 <= (as_of(customer, today) - last).days <= max_gap_days


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
