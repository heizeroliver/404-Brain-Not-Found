"""Security: token-bound customer scope (no IDOR), role checks, rate limit, validation, headers."""
from __future__ import annotations

import time

import jwt

import auth
from api import app, store

PASSWORD = "test-demo-password"


def login(client, customer_id, password=PASSWORD):
    return client.post("/login", json={"customer_id": customer_id, "password": password})


# ------------------------------------------------------------- IDOR / scope

def test_customer_scope_comes_only_from_the_token(client, headers_for):
    lien, marc = headers_for("lien"), headers_for("marc")
    assert client.get("/me", headers=lien).json()["id"] == "lien"
    assert client.get("/me", headers=marc).json()["id"] == "marc"
    # nothing in the URL, query, body or extra headers can point at another customer
    sneaky = {**lien, "X-Customer-Id": "marc"}
    assert client.get("/me?customer_id=marc", headers=sneaky).json()["id"] == "lien"
    assert client.get("/me/moments?customer_id=marc&id=marc", headers=sneaky).status_code == 200
    lien_feed = client.get("/me/moments", headers=lien).json()["moments"]
    marc_feed = client.get("/me/moments", headers=marc).json()["moments"]
    assert {m["type"] for m in lien_feed} != {m["type"] for m in marc_feed}
    assert all("Chloé" not in m["message"] for m in lien_feed)  # Marc's daughter never appears in Lien's feed


def test_login_returns_token_for_the_named_persona(client):
    r = login(client, "lien")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "customer" and body["profile"]["id"] == "lien"
    assert "transactions" not in body["profile"]
    principal = auth.decode_token(body["access_token"])
    assert principal.subject == "lien" and principal.role == "customer"


def test_wrong_password_and_unknown_user_are_indistinguishable(client):
    wrong = login(client, "lien", "nope")
    unknown = login(client, "nobody_here", PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_forged_tampered_and_expired_tokens_are_rejected(client):
    forged = jwt.encode({"sub": "admin", "role": "admin", "iat": int(time.time()), "exp": int(time.time()) + 600,
                         "iss": "kate-foresight"}, "wrong-secret-that-is-long-enough-0123456789abcdef", algorithm="HS256")
    assert client.get("/admin/overview", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired = jwt.encode({"sub": "lien", "role": "customer", "iat": int(time.time()) - 7200,
                          "exp": int(time.time()) - 3600, "iss": "kate-foresight"}, auth._SECRET, algorithm="HS256")
    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    no_role = jwt.encode({"sub": "lien", "iat": int(time.time()), "exp": int(time.time()) + 600,
                          "iss": "kate-foresight"}, auth._SECRET, algorithm="HS256")
    assert client.get("/me", headers={"Authorization": f"Bearer {no_role}"}).status_code == 401
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Basic abc"}).status_code == 401


# ------------------------------------------------------------------- admin

def test_admin_routes_reject_customer_tokens(client, headers_for):
    customer = headers_for("lien")
    assert client.get("/admin/overview", headers=customer).status_code == 403
    assert client.get("/admin/rules", headers=customer).status_code == 403
    assert client.post("/admin/rules", json={}, headers=customer).status_code == 403
    assert client.get("/admin/overview").status_code == 401


def test_admin_overview_has_aggregates_only(client, headers_for):
    r = client.get("/admin/overview", headers=headers_for("admin", "admin"))
    assert r.status_code == 200
    body = r.json()
    assert body["customers_total"] == len(store.customers) and body["care_mode_count"] >= 1
    assert set(body["moments_by_channel"]) <= {"in_app_card", "voice", "advisor", "push", "letter"}
    for entry in body["decision_log_tail"]:
        assert set(entry) <= {"ts", "customer_id", "moment_type", "source", "stakes", "decision", "reason",
                              "score", "channel", "delivery"}
    text = r.text
    assert "Vandenbroucke" not in text and "Lambert" not in text  # no names, ids only


def test_admin_token_cannot_use_customer_routes(client, headers_for):
    assert client.get("/me", headers=headers_for("admin", "admin")).status_code == 403


def test_admin_rules_are_validated_not_executed(client, headers_for):
    admin = headers_for("admin", "admin")
    assert client.post("/admin/rules", json={"id": "x"}, headers=admin).status_code == 422
    evil = {"id": "evil_rule", "title": {"en": "x"}, "summary": {"en": "{__class__} {savings_balance.__class__}"},
            "effective_date": "2026-10-01", "level": "kbc",
            "conditions": [{"field": "savings_balance", "op": "gt", "value": 0}],
            "evidence": ["{savings_balance}"], "actions": ["talk_to_advisor"]}
    r = client.post("/admin/rules", json=evil, headers=admin)
    assert r.status_code == 201 and r.json()["affected_customers"] > 0
    feed = client.get("/me/moments", headers=headers_for("lien")).json()["moments"]
    msg = next(m["message"] for m in feed if m["type"] == "evil_rule")
    assert "<class" not in msg and "float" not in msg  # placeholders never reach Python attributes
    assert client.post("/admin/rules", json=evil, headers=admin).status_code == 409  # duplicate id


# ---------------------------------------------------------------- rate limit

def test_login_rate_limit_blocks_sixth_attempt_per_minute(client):
    app.state.limiter.reset()
    try:
        for _ in range(5):
            assert login(client, "lien", "wrong").status_code == 401
        blocked = login(client, "lien", "wrong")
        assert blocked.status_code == 429
    finally:
        app.state.limiter.reset()


# ----------------------------------------------------------------- inputs

def test_feedback_accepts_only_the_enum(client, headers_for):
    lien = headers_for("lien")
    assert client.post("/me/feedback", json={"moment_type": "idle_cash", "action": "delete_all"}, headers=lien).status_code == 422
    assert client.post("/me/feedback", json={"moment_type": "idle cash; drop", "action": "helpful"}, headers=lien).status_code == 422
    assert client.post("/me/feedback", json={"moment_type": "idle_cash", "action": "helpful", "customer_id": "marc"},
                       headers=lien).status_code == 422  # unknown fields are rejected, not silently ignored
    assert client.post("/me/feedback", json={"moment_type": "idle_cash", "action": "helpful"}, headers=lien).status_code == 201
    r = client.post("/me/feedback", json={"moment_type": "idle_cash", "action": "not_relevant"}, headers=lien)
    assert r.status_code == 201
    assert "idle_cash" not in {m["type"] for m in client.get("/me/moments", headers=lien).json()["moments"]}


def test_consents_are_validated_and_change_the_feed(client, headers_for):
    marc = headers_for("marc")
    assert client.put("/me/consents", json={"use_insurance_data": "yes"}, headers=marc).status_code == 422
    original = client.get("/me/consents", headers=marc).json()
    try:
        r = client.put("/me/consents", json={**original, "use_insurance_data": False}, headers=marc)
        assert r.status_code == 200 and r.json()["use_insurance_data"] is False
        types = {m["type"] for m in client.get("/me/moments", headers=marc).json()["moments"]}
        assert "insurance_renewal_increase" not in types and "insurance_tax_2026" not in types
    finally:
        client.put("/me/consents", json=original, headers=marc)


def test_validation_errors_do_not_echo_the_input(client):
    r = client.post("/login", json={"password": "super-secret-value"})
    assert r.status_code == 422 and "super-secret-value" not in r.text


def test_voice_returns_404_without_a_configured_key(client, headers_for):
    lien = headers_for("lien")
    assert client.get("/me/voice/idle_cash", headers=lien).status_code == 404
    assert client.get("/me/voice/not_a_moment", headers=lien).status_code == 404
    assert client.get("/me/voice/DROP%20TABLE", headers=lien).status_code == 422


# ---------------------------------------------------------- headers / CORS

def test_security_headers_and_cors_restriction(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    evil = client.options("/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil.headers
    ok = client.options("/me", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_no_debug_surfaces(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


# ------------------------------------------------------- pre-audit hardening

def test_customer_demo_password_does_not_grant_admin(client):
    app.state.limiter.reset()
    try:
        assert login(client, "admin", PASSWORD).status_code == 401
        r = login(client, "admin", "test-admin-password")
        assert r.status_code == 200 and r.json()["role"] == "admin"
        assert login(client, "lien", "test-admin-password").status_code == 401
    finally:
        app.state.limiter.reset()


def test_token_without_role_claim_is_rejected(client):
    now = int(time.time())
    token = jwt.encode({"sub": "lien", "iat": now, "exp": now + 600, "iss": "kate-foresight"},
                       auth._SECRET, algorithm="HS256")
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    none_alg = jwt.encode({"sub": "admin", "role": "admin", "iat": now, "exp": now + 600,
                           "iss": "kate-foresight"}, None, algorithm="none")
    assert client.get("/admin/overview", headers={"Authorization": f"Bearer {none_alg}"}).status_code == 401


def test_feedback_only_for_known_moment_types(client, headers_for):
    lien = headers_for("lien")
    r = client.post("/me/feedback", json={"moment_type": "made_up_type", "action": "never"}, headers=lien)
    assert r.status_code == 404
    assert not store.feedback


def test_oversized_body_is_refused(client, headers_for):
    big = {"customer_id": "lien", "password": "x" * (70 * 1024)}
    assert client.post("/login", json=big).status_code == 413


def _rule(**over):
    base = {"id": "dos_rule", "title": {"en": "x"}, "summary": {"en": "{amount:999999999d}"},
            "effective_date": "2026-10-01", "level": "kbc",
            "conditions": [{"field": "savings_balance", "op": "gt", "value": 0}],
            "impact": {"kind": "pct_of_field", "field": "savings_balance", "pct": 1},
            "evidence": ["{savings_balance:.99999999f}"], "actions": ["talk_to_advisor"]}
    base.update(over)
    return base


def test_admin_rule_templates_cannot_blow_up_formatting(client, headers_for):
    admin = headers_for("admin", "admin")
    assert client.post("/admin/rules", json=_rule(), headers=admin).status_code == 201
    feed = client.get("/me/moments", headers=headers_for("lien")).json()["moments"]
    m = next(m for m in feed if m["type"] == "dos_rule")
    assert len(m["message"]) < 200 and all(len(e) < 200 for e in m["evidence"])


def test_admin_rule_size_limits(client, headers_for):
    admin = headers_for("admin", "admin")
    many = [{"field": "region", "op": "eq", "value": "flanders"}] * 13
    assert client.post("/admin/rules", json=_rule(conditions=many), headers=admin).status_code == 422
    long_list = [{"field": "region", "op": "in", "value": ["a"] * 21}]
    assert client.post("/admin/rules", json=_rule(conditions=long_list), headers=admin).status_code == 422
    long_str = [{"field": "region", "op": "eq", "value": "a" * 101}]
    assert client.post("/admin/rules", json=_rule(conditions=long_str), headers=admin).status_code == 422
    sched = {"kind": "yearly_schedule", "schedule": {str(2000 + i): 1 for i in range(21)}}
    assert client.post("/admin/rules", json=_rule(impact=sched), headers=admin).status_code == 422
    for url in ("javascript:alert(1)", "http://x.example", "file:///etc/passwd"):
        assert client.post("/admin/rules", json=_rule(source_url=url), headers=admin).status_code == 422
    assert client.post("/admin/rules", json=_rule(id="Bad-Id"), headers=admin).status_code == 422
    assert client.post("/admin/rules", json=_rule(field_x=1), headers=admin).status_code == 422
