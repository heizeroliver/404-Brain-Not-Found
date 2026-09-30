"""Each rule fires on a crafted customer and stays silent on a control customer."""
from __future__ import annotations

from datetime import date, timedelta

from engine.rules import (child_turns_18, first_home_readiness, holiday_pay, idle_cash,
                          income_drop_care_mode, insurance_renewal_increase, rulebook, run_rules,
                          year_end_bonus_pension_topup)
from engine.rules.rulebook import RULEBOOK
from tests.factories import TODAY, history, make_customer, salaries


def types(moments):
    return [m.type for m in moments]


# ---------------------------------------------------------------- holiday pay

def test_holiday_pay_fires_within_45_days_of_may_payday():
    today = date(2026, 4, 20)
    c = make_customer(transactions=salaries(last=date(2026, 4, 25)) + [
        {"date": "2025-05-22", "amount": 2300.0, "payee": "Testco", "category": "holiday_pay"}])
    moments = holiday_pay.detect(c, today)
    assert len(moments) == 1
    m = moments[0]
    assert m.facts["amount"] == 2300 and m.facts["expected_date"] == "2026-05-22"
    assert m.window[1] == date(2026, 5, 22) and m.source == "life_calendar" and m.category == "sales"
    assert m.confidence == 0.9  # history-based


def test_holiday_pay_predicted_from_gross_when_no_history():
    c = make_customer(transactions=salaries(last=date(2026, 4, 25)))
    m = holiday_pay.detect(c, date(2026, 4, 20))[0]
    assert m.facts["amount"] == round(0.92 * 3000) and m.confidence == 0.7


def test_holiday_pay_silent_outside_window_and_for_pensioners():
    assert holiday_pay.detect(make_customer(), TODAY) == []  # September: May is far away
    pensioner = make_customer(employment={"employer": None, "contract_type": "pension", "gross_monthly_salary": 0},
                              transactions=[])
    assert holiday_pay.detect(pensioner, date(2026, 4, 20)) == []


# ---------------------------------------------------- year-end bonus / pension

def test_year_end_bonus_pension_topup_fires_in_november_with_room():
    today = date(2026, 11, 15)
    c = make_customer(transactions=salaries(last=date(2026, 11, 25)) + [
        {"date": "2025-12-20", "amount": 1900.0, "payee": "Testco", "category": "bonus"}],
        products={"pension_saving": {"contributions_ytd": 600.0, "ceiling": 1050, "monthly": 0.0}})
    moments = year_end_bonus_pension_topup.detect(c, today)
    assert len(moments) == 1
    assert moments[0].facts["room"] == 450 and moments[0].facts["relief_pct"] == 30
    assert moments[0].window[1] == date(2026, 12, 31)


def test_year_end_bonus_silent_when_ceiling_reached_or_wrong_month():
    full = make_customer(transactions=salaries(last=date(2026, 11, 25)),
                         products={"pension_saving": {"contributions_ytd": 1050.0, "ceiling": 1050, "monthly": 0.0}})
    assert year_end_bonus_pension_topup.detect(full, date(2026, 11, 15)) == []
    june = make_customer(transactions=salaries(last=date(2026, 6, 25)),
                         products={"pension_saving": {"contributions_ytd": 0.0, "ceiling": 1050, "monthly": 0.0}})
    assert year_end_bonus_pension_topup.detect(june, date(2026, 6, 15)) == []


# --------------------------------------------------------- insurance renewal

def test_insurance_renewal_increase_fires_above_5_percent_within_45_days():
    renewal = TODAY + timedelta(days=30)
    c = make_customer(policies=[{"kind": "home", "renewal_date": renewal.isoformat(), "premium": 500.0, "new_premium": 560.0}])
    moments = insurance_renewal_increase.detect(c, TODAY)
    assert len(moments) == 1
    assert moments[0].facts["pct"] == 12 and moments[0].legal_basis == "contract_performance"


def test_insurance_renewal_silent_for_small_increase_or_far_renewal():
    small = make_customer(policies=[{"kind": "home", "renewal_date": (TODAY + timedelta(days=30)).isoformat(),
                                     "premium": 500.0, "new_premium": 515.0}])
    assert insurance_renewal_increase.detect(small, TODAY) == []
    far = make_customer(policies=[{"kind": "car", "renewal_date": (TODAY + timedelta(days=120)).isoformat(),
                                   "premium": 500.0, "new_premium": 600.0}])
    assert insurance_renewal_increase.detect(far, TODAY) == []


def test_insurance_consent_off_disables_insurance_based_rules():
    c = make_customer(policies=[{"kind": "home", "renewal_date": (TODAY + timedelta(days=30)).isoformat(),
                                 "premium": 500.0, "new_premium": 560.0}],
                      consents={"use_insurance_data": False})
    assert "insurance_renewal_increase" not in types(run_rules(c, TODAY))
    assert "insurance_tax_2026" not in types(run_rules(c, TODAY))


# ------------------------------------------------------------------ idle cash

def test_idle_cash_fires_when_savings_exceed_buffer_for_six_months():
    c = make_customer(accounts={"savings_balance": 30000.0, "savings_history": history(30000.0)})
    moments = idle_cash.detect(c, TODAY)
    assert len(moments) == 1 and moments[0].facts["idle"] == 30000 - 6 * 2000


def test_idle_cash_silent_when_below_threshold_or_recently_dipped():
    assert idle_cash.detect(make_customer(), TODAY) == []  # 5,000 saved
    dipped = make_customer(accounts={"savings_balance": 30000.0,
                                     "savings_history": history(30000.0)[:-3] + history(9000.0)[-3:]})
    dipped.accounts.savings_balance = 30000.0
    assert idle_cash.detect(dipped, TODAY) == []


# -------------------------------------------------------------- first home

def test_first_home_readiness_fires_for_long_term_renter_with_savings():
    c = make_customer(age=30, housing={"status": "renting", "rent_since": "2022-09-01", "monthly_rent": 950.0,
                                       "landlord": "D. Peeters"},
                      accounts={"savings_balance": 26000.0})
    moments = first_home_readiness.detect(c, TODAY)
    assert len(moments) == 1
    assert moments[0].facts["years_renting"] == 4 and moments[0].facts["duty_pct"] == 2
    assert "2% registration duty" in " ".join(moments[0].evidence)


def test_first_home_readiness_region_and_controls():
    wallonia = make_customer(age=30, region="wallonia", language="fr",
                             housing={"status": "renting", "rent_since": "2021-01-01", "monthly_rent": 800.0, "landlord": "X"},
                             accounts={"savings_balance": 26000.0})
    assert first_home_readiness.detect(wallonia, TODAY)[0].facts["duty_pct"] == 3
    too_old = make_customer(age=45, housing={"status": "renting", "rent_since": "2021-01-01", "monthly_rent": 800.0, "landlord": "X"},
                            accounts={"savings_balance": 26000.0})
    assert first_home_readiness.detect(too_old, TODAY) == []
    too_poor = make_customer(age=30, housing={"status": "renting", "rent_since": "2021-01-01", "monthly_rent": 800.0, "landlord": "X"},
                             accounts={"savings_balance": 5000.0})
    assert first_home_readiness.detect(too_poor, TODAY) == []
    owner = make_customer(age=30, accounts={"savings_balance": 26000.0})
    assert first_home_readiness.detect(owner, TODAY) == []


# ------------------------------------------------------------ child turns 18

def test_child_turns_18_within_60_days():
    birthday = date(2008, 11, 12)  # 18 on 2026-11-12, 43 days after TODAY
    c = make_customer(household={"partner": True, "children": [{"name": "Chloé", "birthdate": birthday.isoformat()}]})
    moments = child_turns_18.detect(c, TODAY)
    assert len(moments) == 1 and moments[0].facts["days"] == 43 and moments[0].confidence == 0.99


def test_child_turns_18_silent_for_younger_or_older_children():
    c = make_customer(household={"partner": True, "children": [
        {"name": "Louis", "birthdate": "2012-03-05"}, {"name": "Anna", "birthdate": "2005-01-01"}]})
    assert child_turns_18.detect(c, TODAY) == []


# ------------------------------------------------------ income drop / care

def test_income_drop_care_mode_fires_when_salary_stopped_two_months():
    c = make_customer(transactions=salaries(last=date(2026, 7, 5)) + [
        {"date": "2026-08-08", "amount": 1200.0, "payee": "RVA", "category": "benefit"},
        {"date": "2026-09-01", "amount": -900.0, "payee": "Landlord", "category": "rent"}])
    moments = income_drop_care_mode.detect(c, TODAY)
    assert len(moments) == 1
    m = moments[0]
    assert m.stakes == "high" and m.human_review is True and m.source == "protection" and m.category == "care"
    assert m.facts["days"] == 87 and m.facts["benefit"] is True and m.channel_hint == "advisor"


def test_income_drop_silent_when_salary_keeps_coming():
    assert income_drop_care_mode.detect(make_customer(), TODAY) == []


# ------------------------------------------------------------- world rules

def test_capital_gains_rule_affects_bolero_holders_above_exemption():
    c = make_customer(products={"bolero": {"portfolio_value": 90000.0, "unrealised_gains": 25000.0, "gains_realised_ytd": 0.0}})
    moments = [m for m in rulebook.detect(c, TODAY) if m.type == "capital_gains_tax_2026"]
    assert len(moments) == 1
    assert moments[0].facts["amount"] == 1500  # 10% of (25,000 - 10,000)
    assert moments[0].source == "world_rule"
    assert rulebook.detect(make_customer(), TODAY) == [] or "capital_gains_tax_2026" not in types(rulebook.detect(make_customer(), TODAY))


def test_insurance_tax_rule_needs_non_life_policies():
    c = make_customer(policies=[{"kind": "car", "renewal_date": "2027-03-01", "premium": 700.0, "new_premium": 700.0}])
    moments = [m for m in rulebook.detect(c, TODAY) if m.type == "insurance_tax_2026"]
    assert len(moments) == 1 and moments[0].facts["amount"] >= 1 and moments[0].stakes == "low"
    hospitalisation_only = make_customer(policies=[{"kind": "hospitalisation", "renewal_date": "2027-07-01",
                                                    "premium": 500.0, "new_premium": 550.0}])
    assert "insurance_tax_2026" not in types(rulebook.detect(hospitalisation_only, TODAY))


def test_company_car_rule_only_for_fossil_cars_ordered_from_july_2023():
    diesel = make_customer(employment={"company_car": {"fuel": "diesel", "ordered_on": "2024-01-15", "lease_end": "2027-01-31"}})
    moments = [m for m in rulebook.detect(diesel, TODAY) if m.type == "company_car_deductibility"]
    assert len(moments) == 1
    assert moments[0].facts["pct_this_year"] == 50 and moments[0].facts["pct_next_year"] == 25
    assert moments[0].stakes == "high"
    electric = make_customer(employment={"company_car": {"fuel": "electric", "ordered_on": "2024-01-15", "lease_end": "2027-01-31"}})
    assert "company_car_deductibility" not in types(rulebook.detect(electric, TODAY))
    early = make_customer(employment={"company_car": {"fuel": "diesel", "ordered_on": "2023-03-01", "lease_end": "2027-03-01"}})
    assert "company_car_deductibility" not in types(rulebook.detect(early, TODAY))


def test_renovation_obligation_is_flemish_and_needs_epc_e_or_f_after_2023():
    flemish = make_customer(products={"mortgage": {"deed_date": "2024-03-10", "epc_label": "F", "outstanding": 200000.0,
                                                   "monthly_payment": 900.0}})
    moments = [m for m in rulebook.detect(flemish, TODAY) if m.type == "renovation_obligation_6y"]
    assert len(moments) == 1 and moments[0].facts["renovation_deadline"] == "2030-03-10"
    walloon = make_customer(region="wallonia", language="fr",
                            products={"mortgage": {"deed_date": "2024-03-10", "epc_label": "F", "outstanding": 200000.0,
                                                   "monthly_payment": 900.0}})
    assert "renovation_obligation_6y" not in types(rulebook.detect(walloon, TODAY))
    good_epc = make_customer(products={"mortgage": {"deed_date": "2024-03-10", "epc_label": "C", "outstanding": 200000.0,
                                                    "monthly_payment": 900.0}})
    assert "renovation_obligation_6y" not in types(rulebook.detect(good_epc, TODAY))


def test_world_rule_future_effective_date_only_visible_from_90_days_before():
    rule = RULEBOOK.get("capital_gains_tax_2026").model_copy(update={"id": "future_rule", "effective_date": date(2027, 6, 1),
                                                                     "visible_from": None, "visible_until": None})
    rule = rule.model_validate(rule.model_dump())  # re-run defaults for visible_from/until
    RULEBOOK.add(rule)
    c = make_customer(products={"bolero": {"portfolio_value": 9000.0, "unrealised_gains": 100.0, "gains_realised_ytd": 0.0}})
    assert "future_rule" not in types(rulebook.detect(c, TODAY))
    assert "future_rule" in types(rulebook.detect(c, date(2027, 4, 1)))
