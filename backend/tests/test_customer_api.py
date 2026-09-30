"""Customer v2 routes: overview allocation, advisor requests, timeline2 (docs/CONTRACT.md)."""
from __future__ import annotations

from api import store


def _overview(client, headers, lang="en"):
    r = client.get(f"/me/overview?lang={lang}", headers=headers)
    assert r.status_code == 200
    return r.json()


def _idle(ov):
    return next((m for m in [ov["priority"], *ov["others"]] if m and m["type"] == "idle_cash"), None)


def test_allocation_before_and_after_goals(client, headers_for):
    lien = headers_for("lien")
    a = _overview(client, lien)["allocation"]
    assert (a["savings"], a["buffer"], a["remaining"], a["reserved_total"], a["shortfall"]) == (26000, 12300, 13700, 0, 0)
    assert a["buffer_months"] == 6 and a["assumption"]

    g = client.post("/me/goals", headers=lien, json={"purpose": "renovation", "amount": 8000, "keep_accessible": True})
    ov = _overview(client, lien)
    a = ov["allocation"]
    assert (a["reserved_total"], a["reserved_covered"], a["remaining"], a["shortfall"]) == (8000, 8000, 5700, 0)
    assert a["reserved"][0]["goal_id"] == g.json()["id"] and len(ov["goals"]) == 1
    idle = _idle(ov)
    assert idle is not None and "€5,700" in idle["evidence"][-1]

    client.delete(f"/me/goals/{g.json()['id']}", headers=lien)
    client.post("/me/goals", headers=lien, json={"purpose": "house_purchase", "amount": 20000, "keep_accessible": True})
    a = _overview(client, lien)["allocation"]
    assert a["remaining"] == 0 and a["reserved_covered"] == 13700 and a["shortfall"] == 6300
    assert all(v >= 0 for k, v in a.items() if isinstance(v, (int, float)))


def test_idle_cash_moment_equals_allocation(client, headers_for):
    lien = headers_for("lien")
    client.post("/me/goals", headers=lien, json={"purpose": "renovation", "amount": 8000, "keep_accessible": True})
    alloc = _overview(client, lien)["allocation"]
    moment = next(m for m in client.get("/me/moments?lang=en", headers=lien).json()["moments"] if m["type"] == "idle_cash")
    assert moment["facts"]["idle"] == alloc["remaining"] == 5700


def test_overview_moment_shape(client, headers_for):
    ov = _overview(client, headers_for("lien"), "nl")
    m = ov["priority"]
    assert m is not None and m["delivery"] == "now"
    for key in ("type", "title", "message", "why_reasons", "why", "source", "category", "stakes", "channel", "delivery",
                "window", "date_label_kind", "confidence", "human_review_required", "legal_basis_label", "evidence",
                "action", "requested"):
        assert key in m
    assert 1 <= len(m["why_reasons"]) <= 3 and m["legal_basis_label"] == "Gerechtvaardigd belang"
    assert m["action"] == {"kind": "open_plans", "label": "Plan je spaargeld"}


def test_advisor_request_created_then_duplicate(client, headers_for):
    lien = headers_for("lien")
    r1 = client.post("/me/advisor-requests", headers=lien, json={"moment_type": "idle_cash", "note": "call me"})
    assert r1.status_code == 201 and r1.json()["created"] is True
    r2 = client.post("/me/advisor-requests", headers=lien, json={"moment_type": "idle_cash"})
    assert r2.status_code == 200 and r2.json()["created"] is False
    assert r2.json()["request"]["id"] == r1.json()["request"]["id"]
    assert set(r1.json()["request"]) == {"id", "moment_type", "status", "created", "updated", "reason"}
    assert _idle(_overview(client, lien))["requested"]["id"] == r1.json()["request"]["id"]
    assert any(e["decision"] == "advisor_requested" and e["customer_id"] == "lien" for e in store.decision_log_tail(10))


def test_advisor_request_validation(client, headers_for):
    lien = headers_for("lien")
    assert client.post("/me/advisor-requests", headers=lien, json={"moment_type": "not_in_feed"}).status_code == 404
    assert client.post("/me/advisor-requests", headers=lien, json={"moment_type": "Bad!"}).status_code == 422
    assert client.post("/me/advisor-requests", headers=lien,
                       json={"moment_type": "idle_cash", "customer_id": "marc"}).status_code == 422


def test_requests_are_customer_isolated(client, headers_for):
    lien, marc = headers_for("lien"), headers_for("marc")
    client.post("/me/advisor-requests", headers=lien, json={"moment_type": "idle_cash"})
    assert len(client.get("/me/advisor-requests", headers=lien).json()["items"]) == 1
    assert client.get("/me/advisor-requests", headers=marc).json()["items"] == []
    assert _overview(client, marc)["advisor_requests"] == []


def test_admin_token_forbidden(client, headers_for):
    admin = headers_for("admin", "admin")
    assert client.get("/me/overview", headers=admin).status_code == 403
    assert client.get("/me/timeline2", headers=admin).status_code == 403
    assert client.get("/me/advisor-requests", headers=admin).status_code == 403


def test_timeline2_days_and_metadata(client, headers_for):
    lien = headers_for("lien")
    assert client.get("/me/timeline2?days=30", headers=lien).status_code == 422
    for days in (90, 365):
        body = client.get(f"/me/timeline2?days={days}&lang=en", headers=lien).json()
        assert body["days"] == days
        for item in body["items"]:
            assert item["kind"] in ("reminder_window", "deadline", "expected_payment", "effective_date", "renewal")
            assert isinstance(item["confidence"], float) and 0 < item["confidence"] <= 1
            assert isinstance(item["human_review_required"], bool)
            assert item["date"] >= body["today"] and item["title"]
            if item["type"] == "holiday_pay":
                assert item["kind"] == "expected_payment"
    long = client.get("/me/timeline2?days=365", headers=lien).json()["items"]
    assert len(long) >= len(client.get("/me/timeline2?days=90", headers=lien).json()["items"])
