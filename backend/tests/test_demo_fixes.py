"""Regression tests for the final demo fixes: money questions, allocation reconciliation, goal preview."""
from __future__ import annotations

from api import store


def _talk(client, headers, text, lang="en"):
    r = client.post(f"/me/talk?lang={lang}", headers=headers, json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _segsum(chart):
    return round(sum(s["value"] for s in chart["segments"]), 2)


def test_money_questions_are_not_goals(client, headers_for):
    lien = headers_for("lien")
    for text, lang in [("Why is €5,700 available?", "en"), ("Waarom is €5.700 beschikbaar?", "nl"),
                       ("Pourquoi 5 700 € sont disponibles ?", "fr")]:
        body = _talk(client, lien, text, lang)
        assert body["intent"] == "why" and body["proposal"] is None, text
    for text, lang in [("Did I spend €100 on groceries?", "en"), ("Heb ik €100 uitgegeven aan boodschappen?", "nl"),
                       ("Ai-je dépensé 100 € en courses ?", "fr")]:
        body = _talk(client, lien, text, lang)
        assert body["intent"] == "spending" and body["proposal"] is None, text
        assert "single payment" in body["message"] or "afzonderlijke" in body["message"] or "paiement" in body["message"]
    assert _talk(client, lien, "How much is €5,700 in dollars?")["intent"] == "clarify"
    amb = _talk(client, lien, "Keep €8,000 for renovation and €5,000 for a car")
    assert amb["intent"] == "clarify" and amb["proposal"] is None
    assert client.get("/me/goals", headers=lien).json()["goals"] == []


def test_goal_statements_still_propose(client, headers_for):
    lien = headers_for("lien")
    for text, lang in [("Keep €8,000 available for renovation.", "en"),
                       ("Ik wil €8.000 beschikbaar houden voor mijn verbouwing", "nl"),
                       ("Je veux garder 8 000 € disponibles pour ma rénovation", "fr")]:
        body = _talk(client, lien, text, lang)
        assert body["intent"] == "goal_proposal" and body["proposal"]["amount"] == 8000, text


def test_preview_values_and_non_mutation(client, headers_for):
    lien = headers_for("lien")
    body = _talk(client, lien, "Keep €8,000 available for my renovation")
    pv = body["preview"]
    cur, new = pv["current"], pv["proposed"]
    assert (cur["savings"], cur["buffer"], cur["reserved_total"], cur["remaining"]) == (26000, 12300, 0, 13700)
    assert (new["buffer"], new["reserved_covered"], new["remaining"]) == (12300, 8000, 5700)
    assert _segsum(cur["chart"]) == 26000 and _segsum(new["chart"]) == 26000
    assert pv["saved"] is False
    assert client.get("/me/goals", headers=lien).json()["goals"] == []
    ov = client.get("/me/overview?lang=en", headers=lien).json()
    assert ov["allocation"]["remaining"] == 13700
    r = client.post("/me/talk/goal/preview?lang=en", headers=lien,
                    json={"purpose": "renovation", "amount": 9000, "keep_accessible": True})
    assert r.status_code == 200 and r.json()["proposed"]["remaining"] == 4700
    assert client.get("/me/goals", headers=lien).json()["goals"] == []


def test_oversized_goal_shows_shortfall_and_reconciles(client, headers_for):
    lien = headers_for("lien")
    r = client.post("/me/talk/goal/preview?lang=en", headers=lien,
                    json={"purpose": "renovation", "amount": 20000, "keep_accessible": True}).json()
    new = r["proposed"]
    assert new["reserved_covered"] == 13700 and new["shortfall"] == 6300 and new["remaining"] == 0
    assert _segsum(new["chart"]) == 26000
    assert new["chart"]["unfunded"] == [{"label": "Renovation", "requested": 20000, "shortfall": 6300}]
    saved = client.post("/me/talk/goal/confirm?lang=en", headers=lien,
                        json={"purpose": "renovation", "amount": 20000, "keep_accessible": True}).json()
    assert _segsum(saved["chart"]) == 26000 and "6,300" in saved["message"]


def test_multiple_goals_and_insufficient_buffer(client, headers_for):
    from engine import allocation
    lien = headers_for("lien")
    for amount, purpose in [(8000, "renovation"), (5000, "car")]:
        assert client.post("/me/talk/goal/confirm", headers=lien,
                           json={"purpose": purpose, "amount": amount, "keep_accessible": True}).status_code == 200
    a = client.get("/me/overview", headers=lien).json()["allocation"]
    assert [g["covered"] for g in a["reserved"]] == [8000, 5000] and a["remaining"] == 700
    cust = store.get_customer("lien")
    poor = cust.model_copy(update={"accounts": cust.accounts.model_copy(update={"savings_balance": 5000})})
    b = allocation.compute(poor)
    assert b["buffer_covered"] == 5000 and b["buffer_shortfall"] == 7300 and b["remaining"] == 0
    assert all(g["covered"] == 0 for g in b["reserved"])


def test_quick_login_is_off_by_default(client):
    assert client.get("/demo/quick-login").json() == {"enabled": False}
    assert client.post("/demo/quick-login", json={"customer_id": "lien"}).status_code == 404


def test_quick_login_when_enabled(client, monkeypatch):
    import config
    monkeypatch.setattr(config, "DEMO_QUICK_LOGIN", True)
    r = client.post("/demo/quick-login", json={"customer_id": "lien"})
    assert r.status_code == 200 and r.json()["role"] == "customer"
    assert client.post("/demo/quick-login", json={"customer_id": "somebody"}).status_code == 422
