"""Digital twin: a flat, typed view of one customer for the world rulebook (option D).

World rules are declarative (validated JSON, no code execution), so they can only
reference the keys produced here. Dates are ISO strings; money is in euro.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from engine.models import Customer

FOSSIL_FUELS = {"diesel", "petrol", "hybrid"}
NON_LIFE = {"home", "car", "family"}


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _months_between(d1: date, d2: date) -> int:
    return max(0, (d2.year - d1.year) * 12 + (d2.month - d1.month))


def build_twin(customer: Customer, today: date) -> dict[str, Any]:
    emp, acc, housing, prod = customer.employment, customer.accounts, customer.housing, customer.products
    car = emp.company_car
    mortgage = prod.mortgage
    bolero = prod.bolero
    ps = prod.pension_saving
    children = customer.household.children
    child_ages = [_years(c.birthdate, today) for c in children]
    policy_kinds = sorted({p.kind for p in customer.policies})
    nonlife_total = sum(p.premium for p in customer.policies if p.kind in NON_LIFE)
    renovation_deadline = _add_years(mortgage.deed_date, 6) if mortgage else None

    twin: dict[str, Any] = {
        "age": customer.age,
        "region": customer.region,
        "language": customer.language,
        "digital_comfort": customer.digital_comfort,
        "contract_type": emp.contract_type,
        "self_employed": emp.self_employed,
        "gross_monthly_salary": emp.gross_monthly_salary,
        "net_monthly_income": emp.net_monthly_salary,
        "has_company_car": car is not None,
        "company_car_fuel": car.fuel if car else None,
        "company_car_fossil": bool(car and car.fuel in FOSSIL_FUELS),
        "company_car_ordered_on": car.ordered_on.isoformat() if car else None,
        "company_car_lease_end": car.lease_end.isoformat() if car else None,
        "company_car_lease_end_days": (car.lease_end - today).days if car else None,
        "is_renting": housing.status == "renting",
        "is_owner": housing.status == "owner",
        "renting_years": _years(housing.rent_since, today) if housing.rent_since else 0,
        "has_mortgage": mortgage is not None,
        "mortgage_deed_date": mortgage.deed_date.isoformat() if mortgage else None,
        "mortgage_epc": mortgage.epc_label if mortgage else None,
        "renovation_deadline": renovation_deadline.isoformat() if renovation_deadline else None,
        "renovation_months_left": _months_between(today, renovation_deadline) if renovation_deadline else None,
        "savings_balance": acc.savings_balance,
        "current_balance": acc.current_balance,
        "policy_kinds": policy_kinds,
        "policy_kinds_text": ", ".join(policy_kinds) if policy_kinds else "no",
        "nonlife_premium_total": round(nonlife_total, 2),
        "has_hospitalisation": "hospitalisation" in policy_kinds,
        "has_bolero": bolero is not None,
        "bolero_value": bolero.portfolio_value if bolero else 0.0,
        "bolero_unrealised_gains": bolero.unrealised_gains if bolero else 0.0,
        "bolero_gains_realised_ytd": bolero.gains_realised_ytd if bolero else 0.0,
        "has_pension_saving": ps is not None,
        "pension_saving_ytd": ps.contributions_ytd if ps else 0.0,
        "pension_saving_ceiling": ps.ceiling if ps else None,
        "children_count": len(children),
        "youngest_child_age": min(child_ages) if child_ages else None,
        "oldest_child_age": max(child_ages) if child_ages else None,
        "use_insurance_data": customer.consents.use_insurance_data,
    }
    return twin


def _years(d1: date, d2: date) -> int:
    years = d2.year - d1.year
    if (d2.month, d2.day) < (d1.month, d1.day):
        years -= 1
    return years
