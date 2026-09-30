"""Kate Talk (docs/TALK_CONTRACT.md): deterministic intents, grounded numbers, token-scoped goals."""
from __future__ import annotations

from datetime import date

from api import store

ALLOWED_KINDS = {"deadline", "reminder_window", "expected_payment", "renewal", "effective_date", "estimate"}
ALLOWED_BASIS = {"contract", "legal", "estimate_from_history", "customer_goal"}
INCOME = {"salary", "pension", "bonus", "holiday_pay", "invoice_income", "benefit"}


def _talk(client, headers, text, lang="en", **extra):
    return client.post(f"/me/talk?lang={lang}", headers=headers, json={"text": text, **extra})


def _common(body):
    assert body["as_of"] == "2026-09-30" and body["synthetic"] is True
    assert 2 <= len(body["suggestions"]) <= 4
    assert "context" in body


def test_spending_reconciles_with_transactions(client, headers_for):
    r = _talk(client, headers_for("lien"), "Where did my money go?")
    assert r.status_code == 200
    body = r.json()
    _common(body)
    assert body["intent"] == "spending"
    assert body["period"]["from"] == "2026-07-01" and body["period"]["to"] == "2026-09-30"
    lien = store.get_customer("lien")
    raw = {}
    for t in lien.transactions:
        if date(2026, 7, 1) <= t.date <= date(2026, 9, 30) and t.amount < 0 \
                and t.category not in INCOME and t.category != "pension_saving":
            raw[t.category] = raw.get(t.category, 0.0) - t.amount
    rows = body["chart"]["rows"]
    assert body["chart"]["kind"] == "category_bars"
    assert {r["key"]: r["value"] for r in rows} == {k: round(v, 2) for k, v in raw.items()}
    assert [r["value"] for r in rows] == sorted((r["value"] for r in rows), reverse=True)
    assert round(sum(r["value"] for r in rows), 2) == body["chart"]["total"] == round(sum(raw.values()), 2)
    assert "pension_saving" not in {r["key"] for r in rows}
    labels = [f["label"] for f in body["facts"]]
    assert len(labels) == 3


def test_spending_nl_and_fr_keywords(client, headers_for):
    lien = headers_for("lien")
    assert _talk(client, lien, "Waar ging mijn geld naartoe?", "nl").json()["intent"] == "spending"
    assert _talk(client, lien, "Où est passé mon argent ?", "fr").json()["intent"] == "spending"


def test_upcoming_items_have_allowed_kinds_and_basis(client, headers_for):
    for who in ("lien", "marc"):
        body = _talk(client, headers_for(who), "What's coming up in the next 90 days?").json()
        _common(body)
        assert body["intent"] == "upcoming" and body["chart"]["kind"] == "timeline"
        for item in body["chart"]["items"]:
            assert item["kind"] in ALLOWED_KINDS and item["basis"] in ALLOWED_BASIS


def test_goal_proposal_saves_nothing_then_confirm_saves(client, headers_for):
    lien = headers_for("lien")
    body = _talk(client, lien, "Ik wil €8.000 beschikbaar houden voor mijn verbouwing", "nl").json()
    _common(body)
    assert body["intent"] == "goal_proposal"
    assert body["proposal"]["amount"] == 8000 and body["proposal"]["purpose"] == "renovation"
    assert client.get("/me/goals", headers=lien).json()["goals"] == []

    r = client.post("/me/talk/goal/confirm?lang=en", headers=lien,
                    json={"purpose": "renovation", "amount": 8000, "keep_accessible": True})
    assert r.status_code == 200
    saved = r.json()
    _common(saved)
    assert saved["intent"] == "goal_saved" and saved["chart"]["kind"] == "allocation"
    seg = {s["key"]: s["value"] for s in saved["chart"]["segments"]}
    assert seg["remaining"] == 5700
    assert "5,700" in saved["message"] and "No money was moved" in saved["message"]
    assert len(client.get("/me/goals", headers=lien).json()["goals"]) == 1

    marc = headers_for("marc")
    why = _talk(client, marc, "Why?").json()
    goal_id = client.get("/me/goals", headers=lien).json()["goals"][0]["id"]
    assert goal_id not in str(why) and "goals reserved_total 0.00" in why["evidence"]
    marc_why = _talk(client, marc, "Why?", context={"moment_type": "idle_cash"}).json()
    assert goal_id not in str(marc_why)
    confirm_bad = client.post("/me/talk/goal/confirm", headers=lien,
                              json={"purpose": "renovation", "amount": 8000, "customer_id": "marc"})
    assert confirm_bad.status_code == 422


def test_why_explains_priority_moment(client, headers_for):
    body = _talk(client, headers_for("lien"), "Why do you suggest this?", context={"moment_type": "idle_cash"}).json()
    _common(body)
    assert body["intent"] == "why" and body["context"]["moment_type"] == "idle_cash"
    assert any("6 x" in a for a in body["assumptions"])


def test_briefing(client, headers_for):
    r = client.get("/me/talk/briefing?lang=fr", headers=headers_for("lien"))
    assert r.status_code == 200
    body = r.json()
    _common(body)
    assert body["intent"] == "briefing" and body["message"]


def test_admin_forbidden_and_validation(client, headers_for):
    admin = headers_for("admin", "admin")
    assert client.get("/me/talk/briefing", headers=admin).status_code == 403
    assert _talk(client, admin, "Where did my money go?").status_code == 403
    lien = headers_for("lien")
    assert _talk(client, lien, "x" * 301).status_code == 422
    assert _talk(client, lien, "").status_code == 422
    assert _talk(client, lien, "hi", customer_id="marc").status_code == 422
    assert _talk(client, lien, "hi", context={"moment_type": "BAD TYPE"}).status_code == 422


def test_unsupported_text_clarifies(client, headers_for):
    body = _talk(client, headers_for("lien"), "tell me a joke").json()
    _common(body)
    assert body["intent"] == "clarify" and len(body["suggestions"]) == 4
