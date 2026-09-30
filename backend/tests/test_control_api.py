"""Control room v2 (/admin/v2/*): admin-only, filters, preview never mutates, activation, request flow."""
from __future__ import annotations

import pytest

import requests_store
from api import store
from engine.rules.rulebook import RULEBOOK


@pytest.fixture
def admin(headers_for):
    return headers_for("admin", "admin")


ROUTES = [("get", "/admin/v2/overview"), ("get", "/admin/v2/moments"), ("get", "/admin/v2/advisor-requests"),
          ("get", "/admin/v2/rule-template"), ("get", "/admin/v2/audit")]


@pytest.mark.parametrize("method, path", ROUTES)
def test_admin_only(client, headers_for, method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers=headers_for("lien")).status_code == 403


def test_admin_only_writes(client, headers_for):
    lien = headers_for("lien")
    assert client.post("/admin/v2/rules/preview", headers=lien, json={"rule": {}}).status_code == 403
    assert client.post("/admin/v2/rules/activate", headers=lien, json={"rule": {}}).status_code == 403
    assert client.patch("/admin/v2/advisor-requests/AR-ABCDEF", headers=lien,
                        json={"status": "resolved"}).status_code == 403


def test_overview_metrics(client, admin):
    d = client.get("/admin/v2/overview", headers=admin).json()
    keys = [m["key"] for m in d["metrics"]]
    assert keys == ["customers_with_moment", "moments_total", "advisor_routing_recommended", "advisor_requests_open"]
    assert all(m["definition_key"].startswith("def_") and m["definition"] for m in d["metrics"])
    values = {m["key"]: m["value"] for m in d["metrics"]}
    assert sum(r["value"] for r in d["channel_recommendations"]) == values["moments_total"]
    assert sum(r["value"] for r in d["moments_by_type"]) == values["moments_total"]
    assert d["cohort"]["customers"] == len(store.customers)
    assert {a["kind"] for a in d["attention"]} >= {"advisor_requests_open", "care_mode", "suppressed"}


def test_moments_filters_and_pagination(client, admin):
    all_ = client.get("/admin/v2/moments?page_size=100", headers=admin).json()
    assert all_["page"] == 1 and len(all_["items"]) == min(100, all_["total_moments"])
    item = all_["items"][0]
    assert item["customer_name"] and item["decision_path"][0].startswith("detected")
    p2 = client.get("/admin/v2/moments?page=2&page_size=10", headers=admin).json()
    assert p2["total_moments"] == all_["total_moments"] and len(p2["items"]) == 10
    adv = client.get("/admin/v2/moments?channel=advisor&page_size=100", headers=admin).json()
    assert adv["total_moments"] > 0 and all(i["channel"] == "advisor" for i in adv["items"])
    assert any(p.startswith("channel advisor:") for p in adv["items"][0]["decision_path"])
    sup = client.get("/admin/v2/moments?status=suppressed&page_size=100", headers=admin).json()
    assert all(i["status"] == "suppressed" and i["decision_path"][-1].startswith("dropped:") for i in sup["items"])
    lien = client.get("/admin/v2/moments?q=lien", headers=admin).json()
    assert lien["total_customers"] >= 1
    assert client.get("/admin/v2/moments?page_size=5", headers=admin).status_code == 422
    assert client.get("/admin/v2/moments?status=bogus", headers=admin).status_code == 422
    assert client.get("/admin/v2/moments?q=" + "x" * 61, headers=admin).status_code == 422


def test_preview_does_not_mutate_and_activate(client, admin):
    template = client.get("/admin/v2/rule-template", headers=admin).json()
    assert template["illustrative"] is True and "savings_balance" in template["condition_fields"]
    rule = template["rule"]
    before = [r.id for r in RULEBOOK.rules()]
    res = client.post("/admin/v2/rules/preview", headers=admin, json={"rule": rule})
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["total"] == len(store.customers) and 0 < d["affected"] <= d["total"]
    assert len(d["sample"]) <= 8 and isinstance(d["suppressed"], dict) and d["changes_summary"]
    assert [r.id for r in RULEBOOK.rules()] == before
    assert client.post("/admin/v2/rules/preview", headers=admin,
                       json={"rule": {**rule, "evil": 1}}).status_code == 422

    created = client.post("/admin/v2/rules/activate", headers=admin, json={"rule": rule})
    assert created.status_code == 201 and RULEBOOK.get(rule["id"]) is not None
    assert created.json()["affected_customers"] == d["affected"]
    assert any(e["decision"] == "rule_activated" for e in store.decision_log_tail(5))
    assert client.post("/admin/v2/rules/activate", headers=admin, json={"rule": rule}).status_code == 409


def test_advisor_request_status_flow(client, admin):
    req, _ = requests_store.create("lien", "idle_cash", "test", {})
    listed = client.get("/admin/v2/advisor-requests?status=requested", headers=admin).json()["items"]
    assert any(r["id"] == req["id"] and r["customer_name"] for r in listed)
    assert client.get("/admin/v2/advisor-requests?status=bogus", headers=admin).status_code == 422
    url = f"/admin/v2/advisor-requests/{req['id']}"
    r = client.patch(url, headers=admin, json={"status": "in_review"})
    assert r.status_code == 200 and r.json()["status"] == "in_review"
    assert client.patch(url, headers=admin, json={"status": "resolved"}).json()["status"] == "resolved"
    assert client.patch(url, headers=admin, json={"status": "requested"}).status_code == 422
    assert client.patch(url, headers=admin, json={"status": "resolved", "x": 1}).status_code == 422
    assert client.patch("/admin/v2/advisor-requests/AR-000000", headers=admin,
                        json={"status": "resolved"}).status_code == 404
    assert client.patch("/admin/v2/advisor-requests/bad", headers=admin,
                        json={"status": "resolved"}).status_code == 422
    audit = client.get("/admin/v2/audit?decision=advisor_request_status", headers=admin).json()
    assert audit["log"]["total"] >= 2 and all(e["decision"] == "advisor_request_status" for e in audit["log"]["items"])


def test_audit_shape(client, admin):
    d = client.get("/admin/v2/audit", headers=admin).json()
    assert set(d["consents"]) == {"use_insurance_data", "use_other_banks", "marketing"}
    assert sum(d["consents"]["marketing"].values()) == len(store.customers)
    assert isinstance(d["feedback"], dict) and isinstance(d["suppressed_by_reason"], list)
    assert d["log"]["page"] == 1 and len(d["log"]["items"]) <= 25
