"""Arbitration: vulnerability guard, frequency cap, channel choice, feedback."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engine.arbitrate import arbitrate, choose_channel
from store import Store
from tests.factories import TODAY, make_customer, make_moment


@pytest.fixture
def fresh_store() -> Store:
    return Store(Path("/nonexistent/customers.json"), None)


def test_care_mode_suppresses_sales_moments_but_keeps_help_and_info(fresh_store):
    customer = make_customer()
    care = make_moment("income_drop_care_mode", stakes="high", category="care", source="protection", human_review=True)
    sales = make_moment("idle_cash", category="sales")
    info = make_moment("insurance_renewal_increase", category="info")
    result = arbitrate(customer, [sales, care, info], TODAY, fresh_store)
    assert result.care_mode is True
    assert [r.moment.type for r in result.ranked] == ["income_drop_care_mode", "insurance_renewal_increase"]
    assert result.ranked[0].channel == "advisor"
    dropped = [d for d in result.decisions if d["decision"] == "dropped"]
    assert dropped and dropped[0]["moment_type"] == "idle_cash" and "vulnerability guard" in dropped[0]["reason"]


def test_without_care_mode_sales_moments_stay(fresh_store):
    result = arbitrate(make_customer(), [make_moment("idle_cash", category="sales")], TODAY, fresh_store)
    assert result.care_mode is False and [r.moment.type for r in result.ranked] == ["idle_cash"]


def test_frequency_cap_pushes_one_non_high_moment_per_week(fresh_store):
    customer = make_customer()
    moments = [make_moment("idle_cash"), make_moment("first_home_readiness", confidence=0.8)]
    result = arbitrate(customer, moments, TODAY, fresh_store)
    deliveries = [r.delivery for r in result.ranked]
    assert deliveries == ["now", "queued"]
    assert fresh_store.recent_deliveries("test_cust", TODAY) == ["idle_cash"]
    # a second evaluation the same week keeps the same pushed moment
    again = arbitrate(customer, moments, TODAY + timedelta(days=2), fresh_store)
    assert [r.delivery for r in again.ranked] == ["now", "queued"]


def test_frequency_cap_does_not_apply_to_high_stakes(fresh_store):
    fresh_store.record_delivery("test_cust", "something_else", TODAY - timedelta(days=3))
    moments = [make_moment("idle_cash"), make_moment("company_car_deductibility", stakes="high", category="info")]
    result = arbitrate(make_customer(), moments, TODAY, fresh_store)
    by_type = {r.moment.type: r.delivery for r in result.ranked}
    assert by_type == {"company_car_deductibility": "now", "idle_cash": "queued"}


def test_cap_resets_after_seven_days(fresh_store):
    fresh_store.record_delivery("test_cust", "something_else", TODAY - timedelta(days=8))
    result = arbitrate(make_customer(), [make_moment("idle_cash")], TODAY, fresh_store)
    assert result.ranked[0].delivery == "now"


def test_score_formula_and_ordering(fresh_store):
    high = make_moment("a_high", stakes="high", confidence=0.5)      # 3 * 1 * 0.5 = 1.5
    medium = make_moment("b_medium", stakes="medium", confidence=0.9)  # 2 * 1 * 0.9 = 1.8
    future = make_moment("c_future", stakes="medium", confidence=1.0, start=TODAY + timedelta(days=30))  # urgency 0.5 -> 1.0
    result = arbitrate(make_customer(), [high, medium, future], TODAY, fresh_store)
    assert [r.moment.type for r in result.ranked] == ["b_medium", "a_high", "c_future"]
    assert [r.score for r in result.ranked] == [1.8, 1.5, 1.0]


def test_expired_moments_are_dropped(fresh_store):
    old = make_moment("old", start=TODAY - timedelta(days=40), end=TODAY - timedelta(days=1))
    result = arbitrate(make_customer(), [old], TODAY, fresh_store)
    assert result.ranked == [] and result.decisions[0]["reason"] == "window expired"


def test_feedback_never_and_not_now_suppress_and_helpful_boosts(fresh_store):
    customer = make_customer()
    fresh_store.add_feedback("test_cust", "idle_cash", "never")
    assert arbitrate(customer, [make_moment("idle_cash")], TODAY, fresh_store).ranked == []
    fresh_store.add_feedback("test_cust", "holiday_pay", "not_now",
                             when=datetime.now(timezone.utc) - timedelta(days=3))
    assert arbitrate(customer, [make_moment("holiday_pay")], TODAY, fresh_store).ranked == []
    fresh_store.add_feedback("test_cust", "first_home_readiness", "helpful")
    boosted = arbitrate(customer, [make_moment("first_home_readiness")], TODAY, fresh_store).ranked[0].score
    assert boosted == round(2 * 1 * 0.9 * 1.25, 3)


def test_marketing_consent_off_drops_sales_moments(fresh_store):
    customer = make_customer(consents={"marketing": False})
    result = arbitrate(customer, [make_moment("idle_cash", category="sales"), make_moment("child_turns_18", category="info")],
                       TODAY, fresh_store)
    assert [r.moment.type for r in result.ranked] == ["child_turns_18"]


def test_channel_choice():
    medium = make_moment("x", stakes="medium")
    assert choose_channel(medium, make_customer(digital_comfort=1)) == "advisor"
    assert choose_channel(medium, make_customer(age=71, digital_comfort=3)) == "voice"
    assert choose_channel(medium, make_customer(age=29, digital_comfort=5)) == "in_app_card"
    assert choose_channel(make_moment("y", stakes="high"), make_customer(age=29, digital_comfort=5)) == "advisor"
    assert choose_channel(make_moment("z", human_review=True), make_customer(age=29, digital_comfort=5)) == "advisor"


def test_decision_log_is_written(fresh_store, tmp_path):
    logged = Store(Path("/nonexistent/customers.json"), tmp_path / "log.jsonl")
    arbitrate(make_customer(), [make_moment("idle_cash")], TODAY, logged)
    lines = (tmp_path / "log.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1 and '"customer_id": "test_cust"' in lines[0]
    assert logged.decision_log_tail(5)[0]["decision"] == "ranked"
