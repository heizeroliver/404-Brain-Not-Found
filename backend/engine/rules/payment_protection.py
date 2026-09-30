"""Payment protection: the fraud engine held a suspicious payment; bring in a human and offer Guardian Angel."""
from __future__ import annotations

from datetime import date, timedelta

from engine.models import Customer, Moment
from engine.rules.common import eur

TYPE = "payment_protection"
CATEGORY = "care"  # protection first: no sales while this is open
REQUIRES_INSURANCE_DATA = False
PROJECTABLE = False
RECENT_DAYS = 14


def detect(customer: Customer, today: date) -> list[Moment]:
    alert = customer.security.recent_alert
    if alert is None:
        return []
    age_days = (today - alert.date).days
    if not 0 <= age_days <= RECENT_DAYS:
        return []
    evidence = [
        f"payment of {eur(alert.amount)} held on {alert.date.isoformat()}: the name shown "
        f"('{alert.payee_shown}') does not match the account holder ({alert.payee_registered}) "
        "(Verification of Payee)",
        "a bank never asks you to move money to a 'safe account'",
    ]
    if not customer.security.guardian_angel_active:
        evidence.append("Guardian Angel (a trusted person double-checks unusual payments) is not active yet")
    return [Moment(
        type=TYPE,
        window=(today, today + timedelta(days=3)),
        confidence=0.95,
        stakes="high",
        evidence=evidence,
        actions=["call_me_back", "activate_guardian_angel", "block_card"],
        channel_hint="advisor",
        legal_basis="legal_obligation",
        human_review=True,
        source="protection",
        category=CATEGORY,
        facts={"amount": round(alert.amount), "alert_date": alert.date.isoformat(),
               "payee_shown": alert.payee_shown,
               "guardian_angel_active": customer.security.guardian_angel_active},
    )]
