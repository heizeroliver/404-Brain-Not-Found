"""Regression tests for the Aikido AI code audit findings."""
from datetime import date

import pytest
from pydantic import ValidationError

import api
from engine.rules.rulebook import WorldRule

BASE = {"id": "t_rule", "title": {"en": "T"}, "summary": {"en": "Balance {savings_balance}"},
        "effective_date": "2026-01-01", "level": "federal", "evidence": ["test"], "actions": ["talk_to_advisor"],
        "conditions": [{"field": "age", "op": "gte", "value": 0}]}


def test_rule_cannot_target_consent_or_unknown_fields():
    with pytest.raises(ValidationError):
        WorldRule.model_validate({**BASE, "conditions": [{"field": "use_insurance_data", "op": "eq", "value": True}]})
    with pytest.raises(ValidationError):
        WorldRule.model_validate({**BASE, "conditions": [{"field": "first_name", "op": "exists"}]})


def test_rule_facts_are_minimised():
    rule = WorldRule.model_validate({**BASE, "conditions": [{"field": "age", "op": "gte", "value": 18}]})
    lien = api.store.get_customer("lien")
    from engine.twin import build_twin
    facts = rule.impact_facts(build_twin(lien, date(2026, 9, 30)), date(2026, 9, 30))
    assert "savings_balance" in facts and "age" in facts
    assert "gross_monthly_salary" not in facts and "bolero_value" not in facts


def test_insurance_field_rule_respects_consent(client, headers_for):
    rule = WorldRule.model_validate({**BASE, "id": "ins_rule", "summary": {"en": "Premium {nonlife_premium_total}"},
                                     "conditions": [{"field": "nonlife_premium_total", "op": "gte", "value": 1}]})
    from engine.rules.rulebook import RULEBOOK, detect
    RULEBOOK.add(rule)
    marc = api.store.get_customer("marc")
    assert any(m.type == "ins_rule" for m in detect(marc, date(2026, 9, 30)))
    opted_out = marc.model_copy(update={"consents": marc.consents.model_copy(update={"use_insurance_data": False})})
    assert not any(m.type == "ins_rule" for m in detect(opted_out, date(2026, 9, 30)))


def test_protection_moment_cannot_be_hidden_by_feedback(client, headers_for):
    h = headers_for("rita")
    assert client.post("/me/feedback", json={"moment_type": "payment_protection", "action": "never"}, headers=h).status_code in (200, 201)
    types = {m["type"] for m in client.get("/me/moments", headers=h).json()["moments"]}
    assert "payment_protection" in types


def test_company_car_text_renders_fuel_label(client, headers_for):
    msgs = [m["message"] for m in client.get("/me/moments", headers=headers_for("marc")).json()["moments"]
            if m["type"] == "company_car_deductibility"]
    assert msgs and "(?" not in msgs[0]
