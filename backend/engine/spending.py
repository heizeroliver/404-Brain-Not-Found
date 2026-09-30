"""Spending summary over full calendar months (docs/TALK_CONTRACT.md, Spending semantics)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from engine.models import Customer

INCOME = {"salary", "pension", "bonus", "holiday_pay", "invoice_income", "benefit"}
SAVING = {"pension_saving"}

LABELS: dict[str, dict[str, str]] = {
    "groceries": {"nl": "Boodschappen", "en": "Groceries", "fr": "Courses"},
    "rent": {"nl": "Huur", "en": "Rent", "fr": "Loyer"},
    "mortgage": {"nl": "Woonkrediet", "en": "Mortgage", "fr": "Crédit hypothécaire"},
    "energy": {"nl": "Energie", "en": "Energy", "fr": "Énergie"},
    "telecom": {"nl": "Telecom", "en": "Telecom", "fr": "Télécom"},
    "transport": {"nl": "Vervoer", "en": "Transport", "fr": "Transport"},
    "insurance": {"nl": "Verzekeringen", "en": "Insurance", "fr": "Assurances"},
    "childcare": {"nl": "Kinderopvang", "en": "Childcare", "fr": "Garde d'enfants"},
    "notary": {"nl": "Notaris", "en": "Notary", "fr": "Notaire"},
}


def label(category: str, lang: str) -> str:
    t = LABELS.get(category)
    return (t.get(lang) or t["en"]) if t else category.replace("_", " ").capitalize()


def period(today: date, months: int = 3) -> tuple[date, date]:
    """The `months` full calendar months ending with today's month."""
    nxt = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    end = nxt - timedelta(days=1)
    y, m = today.year, today.month - (months - 1)
    while m < 1:
        m += 12
        y -= 1
    return date(y, m, 1), end


def summarize(customer: Customer, today: date, months: int = 3, lang: str = "en") -> dict[str, Any]:
    start, end = period(today, months)
    last_month = (end.year, end.month)
    cats: dict[str, float] = {}
    last: dict[str, float] = {}
    income = saving = 0.0
    for t in customer.transactions:
        if not (start <= t.date <= end):
            continue
        if t.category in INCOME:
            income += t.amount
        elif t.category in SAVING:
            saving += -t.amount
        elif t.amount < 0:
            cats[t.category] = cats.get(t.category, 0.0) - t.amount
            if (t.date.year, t.date.month) == last_month:
                last[t.category] = last.get(t.category, 0.0) - t.amount
    rows = [{"key": k, "label": label(k, lang), "value": round(v, 2)}
            for k, v in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))]
    spending = round(sum(r["value"] for r in rows), 2)
    rises = []
    for k, v in cats.items():
        avg = v / months
        lm = last.get(k, 0.0)
        if avg > 0 and lm > avg * 1.2:
            rises.append({"key": k, "last_month": round(lm, 2), "average": round(avg, 2),
                          "pct": round((lm / avg - 1) * 100)})
    rises.sort(key=lambda r: -r["pct"])
    return {
        "from": start, "to": end, "rows": rows, "spending": spending,
        "income": round(income, 2), "saving": round(saving, 2),
        "net": round(income - spending - saving, 2), "rises": rises,
        "largest": rows[0] if rows else None,
        "largest_share": round(rows[0]["value"] / spending * 100) if rows and spending else 0,
    }
