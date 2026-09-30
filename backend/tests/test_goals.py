"""Customer-stated goals: parse, store per customer (token-scoped), and change the idle-cash decision."""
from __future__ import annotations

import pytest

from api import store
from engine.intent import parse_goal


@pytest.mark.parametrize("text, lang", [
    ("Ik wil €8.000 beschikbaar houden voor mijn verbouwing", "nl"),
    ("I need to keep €8,000 available for my renovation", "en"),
    ("Je dois garder 8 000 € disponibles pour ma rénovation", "fr"),
])
def test_parse_nl_en_fr(text, lang):
    goal = parse_goal(text, lang)
    assert goal is not None
    assert goal["purpose"] == "renovation" and goal["amount"] == 8000 and goal["keep_accessible"] is True


def test_parse_amount_formats_and_limits():
    assert parse_goal("8000 voor een nieuwe auto", "nl")["purpose"] == "car"
    assert parse_goal("8k for travel", "en")["amount"] == 8000
    assert parse_goal("hallo Kate", "nl") is None
    assert parse_goal("€0 voor de vakantie", "nl") is None
    assert parse_goal("€2.000.000 voor een huis", "nl") is None
    assert parse_goal("x" * 301 + " €8.000", "nl") is None


def _idle_cash(client, headers):
    feed = client.get("/me/moments?lang=en", headers=headers).json()["moments"]
    return next((m for m in feed if m["type"] == "idle_cash"), None)


def test_goal_changes_the_idle_cash_moment(client, headers_for):
    lien = headers_for("lien")
    before = _idle_cash(client, lien)
    assert before is not None and before["facts"]["idle"] == 13700

    proposal = client.post("/me/goals/parse", headers=lien,
                           json={"text": "Ik wil €8.000 beschikbaar houden voor mijn verbouwing", "lang": "nl"}).json()
    body = {k: proposal["proposal"][k] for k in ("purpose", "amount", "keep_accessible")}
    assert client.get("/me/goals", headers=lien).json()["goals"] == []  # parsing stores nothing
    created = client.post("/me/goals", headers=lien, json=body)
    assert created.status_code == 201 and created.json()["source"] == "customer"

    after = _idle_cash(client, lien)
    assert after is not None and after["facts"]["idle"] == 5700
    assert any("€8,000 reserved for your renovation (your own goal, set 2026-09-30)" == e for e in after["evidence"])
    assert any(e["decision"] == "goal_set" and e["customer_id"] == "lien" for e in store.decision_log_tail(10))

    client.delete(f"/me/goals/{created.json()['id']}", headers=lien)
    client.post("/me/goals", headers=lien, json={"purpose": "house_purchase", "amount": 20000, "keep_accessible": True})
    assert _idle_cash(client, lien) is None  # nothing idle left once her own plans are counted


def test_goals_are_scoped_to_the_token(client, headers_for):
    lien, marc = headers_for("lien"), headers_for("marc")
    goal = client.post("/me/goals", headers=lien, json={"purpose": "car", "amount": 5000, "keep_accessible": True}).json()
    assert client.get("/me/goals", headers=marc).json()["goals"] == []
    assert client.delete(f"/me/goals/{goal['id']}", headers=marc).status_code == 404
    assert [g["id"] for g in client.get("/me/goals", headers=lien).json()["goals"]] == [goal["id"]]
    assert client.delete("/me/goals/not-an-id", headers=lien).status_code == 422
    assert client.delete(f"/me/goals/{goal['id']}", headers=lien).status_code == 200
    assert client.get("/me/goals", headers=headers_for("admin", "admin")).status_code == 403


def test_invalid_goals_are_rejected(client, headers_for):
    lien = headers_for("lien")
    for bad in ({"purpose": "renovation", "amount": 0, "keep_accessible": True},
                {"purpose": "renovation", "amount": 2_000_000, "keep_accessible": True},
                {"purpose": "yacht", "amount": 8000, "keep_accessible": True},
                {"purpose": "renovation", "amount": 8000, "keep_accessible": "yes"},
                {"purpose": "renovation", "amount": 8000, "customer_id": "marc"}):
        assert client.post("/me/goals", headers=lien, json=bad).status_code == 422
    assert client.post("/me/goals/parse", headers=lien, json={"text": "x" * 301, "lang": "nl"}).status_code == 422
