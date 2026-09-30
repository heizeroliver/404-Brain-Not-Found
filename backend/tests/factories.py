"""Builders for crafted customers used by the rule and arbitration tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from engine.models import Customer, Moment

TODAY = date(2026, 9, 30)


def month_shift(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return date(y, m, min(d.day, 28))


def salaries(employer: str = "Testco", amount: float = 2000.0, last: date = date(2026, 9, 25),
             months: int = 12) -> list[dict[str, Any]]:
    return [{"date": month_shift(last, -i).isoformat(), "amount": amount, "payee": employer, "category": "salary"}
            for i in range(months)]


def history(balance: float, months: int = 12, end: date = TODAY) -> list[dict[str, Any]]:
    return [{"month": month_shift(end, -i).strftime("%Y-%m"), "balance": balance} for i in reversed(range(months))]


BASE: dict[str, Any] = {
    "id": "test_cust", "name": "Test Customer", "first_name": "Test", "language": "nl", "region": "flanders",
    "age": 35, "birthdate": "1991-05-05", "digital_comfort": 4,
    "household": {"partner": False, "children": []},
    "employment": {"employer": "Testco", "gross_monthly_salary": 3000.0, "net_monthly_salary": 2000.0,
                   "contract_type": "permanent", "self_employed": False, "company_car": None},
    "accounts": {"current_balance": 1000.0, "savings_balance": 5000.0, "savings_opened_on": "2020-01-01",
                 "fidelity_date": "2027-01-01", "savings_history": history(5000.0)},
    "housing": {"status": "owner", "rent_since": None, "monthly_rent": None, "landlord": None},
    "transactions": salaries(),
    "policies": [],
    "products": {"mortgage": None, "pension_saving": None, "bolero": None},
    "consents": {"use_insurance_data": True, "use_other_banks": False, "marketing": True},
}


def _merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def make_customer(**overrides: Any) -> Customer:
    return Customer.model_validate(_merge(BASE, overrides))


def make_moment(type_: str = "idle_cash", stakes: str = "medium", category: str = "sales",
                source: str = "life_calendar", confidence: float = 0.9, start: date = TODAY,
                end: date | None = None, human_review: bool = False) -> Moment:
    return Moment(type=type_, window=(start, end or start + timedelta(days=30)), confidence=confidence,
                  stakes=stakes, evidence=["crafted evidence"], actions=["do_something"],
                  channel_hint="in_app_card", legal_basis="legitimate_interest", human_review=human_review,
                  source=source, category=category, facts={})
