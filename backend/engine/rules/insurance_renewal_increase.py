"""Insurance renewal within 45 days with a premium increase above 5% (Appendix A)."""
from __future__ import annotations

from datetime import date

from engine.models import Customer, Moment
from engine.rules.common import eur

TYPE = "insurance_renewal_increase"
CATEGORY = "info"
REQUIRES_INSURANCE_DATA = True
PROJECTABLE = True  # calendar-anchored: can be projected on the 12-month timeline
LOOKAHEAD_DAYS = 45


def detect(customer: Customer, today: date) -> list[Moment]:
    moments: list[Moment] = []
    for p in customer.policies:
        days = (p.renewal_date - today).days
        if 0 < days <= LOOKAHEAD_DAYS and p.new_premium > p.premium * 1.05:
            moments.append(Moment(
                type=TYPE,
                window=(today, p.renewal_date),
                confidence=0.98,  # contractual date, deterministic
                stakes="medium",
                evidence=[
                    f"{p.kind} policy renews in {days} days ({p.renewal_date.isoformat()})",
                    f"premium {eur(p.premium)} → {eur(p.new_premium)} (+{p.pct_increase:.0f}%)",
                ],
                actions=["compare_two_options", "talk_to_advisor", "keep_as_is"],
                channel_hint="in_app_card",
                legal_basis="contract_performance",
                human_review=False,
                source="life_calendar",
                category=CATEGORY,
                facts={"kind": p.kind, "days": days, "renewal_date": p.renewal_date.isoformat(),
                       "premium": round(p.premium), "new_premium": round(p.new_premium),
                       "pct": round(p.pct_increase)},
            ))
    return moments
