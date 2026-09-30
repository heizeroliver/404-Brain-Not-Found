"""Savings allocation: buffer, the customer's reserved goals, and what is left.

The same numbers feed the idle_cash rule, GET /me/overview, Kate Talk and the goal preview
(docs/CONTRACT.md, Allocation). Funding order: buffer first, then goals in the order they were
set. Every funded amount comes out of actual savings, so buffer_covered + sum(covered) + remaining
always equals savings; what a goal asks for beyond that is its shortfall, shown separately.
"""
from __future__ import annotations

from typing import Any

from engine.models import Customer, Goal

BUFFER_MONTHS = 6
ASSUMPTION = f"Buffer modeled as {BUFFER_MONTHS} x net monthly income (prototype assumption)"


def compute(customer: Customer, extra_goals: list[Goal] | None = None) -> dict[str, Any]:
    """extra_goals: a temporary what-if (preview); nothing is stored."""
    savings = max(float(customer.accounts.savings_balance), 0.0)
    net = max(float(customer.employment.net_monthly_salary), 0.0)
    buffer = BUFFER_MONTHS * net
    buffer_covered = min(buffer, savings)
    left = savings - buffer_covered
    reserved = []
    for g in list(customer.goals) + list(extra_goals or []):
        if not g.keep_accessible:
            continue
        amount = float(g.amount)
        covered = min(amount, left)
        left -= covered
        reserved.append({"goal_id": g.id, "purpose": g.purpose, "amount": round(amount, 2),
                         "covered": round(covered, 2), "shortfall": round(amount - covered, 2)})
    reserved_total = sum(r["amount"] for r in reserved)
    reserved_covered = sum(r["covered"] for r in reserved)
    return {
        "savings": round(savings, 2),
        "buffer": round(buffer, 2),
        "buffer_covered": round(buffer_covered, 2),
        "buffer_shortfall": round(buffer - buffer_covered, 2),
        "buffer_months": BUFFER_MONTHS,
        "net_monthly_income": round(net, 2),
        "reserved": reserved,
        "reserved_total": round(reserved_total, 2),
        "reserved_covered": round(reserved_covered, 2),
        "shortfall": round(reserved_total - reserved_covered, 2),
        "remaining": round(max(left, 0.0), 2),
        "assumption": ASSUMPTION,
    }
