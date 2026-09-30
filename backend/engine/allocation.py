"""Savings allocation: buffer, the customer's reserved goals, and what is left.

The same numbers feed the idle_cash rule and GET /me/overview (docs/CONTRACT.md, Allocation).
"""
from __future__ import annotations

from typing import Any

from engine.models import Customer

BUFFER_MONTHS = 6
ASSUMPTION = f"Buffer modeled as {BUFFER_MONTHS} x net monthly income (prototype assumption)"


def compute(customer: Customer) -> dict[str, Any]:
    savings = float(customer.accounts.savings_balance)
    net = max(float(customer.employment.net_monthly_salary), 0.0)
    buffer = BUFFER_MONTHS * net
    reserved = [{"goal_id": g.id, "purpose": g.purpose, "amount": float(g.amount)}
                for g in customer.goals if g.keep_accessible]
    reserved_total = sum(r["amount"] for r in reserved)
    above_buffer = max(savings - buffer, 0.0)
    return {
        "savings": round(savings, 2),
        "buffer": round(buffer, 2),
        "buffer_months": BUFFER_MONTHS,
        "net_monthly_income": round(net, 2),
        "reserved": reserved,
        "reserved_total": round(reserved_total, 2),
        "reserved_covered": round(min(reserved_total, above_buffer), 2),
        "shortfall": round(max(reserved_total - above_buffer, 0.0), 2),
        "remaining": round(max(savings - buffer - reserved_total, 0.0), 2),
        "assumption": ASSUMPTION,
    }
