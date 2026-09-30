#!/usr/bin/env python3
"""Deterministic synthetic Belgian dataset for the Kate Foresight demo.

    python data/generate.py            -> backend/data/customers.json

Three hero personas (ACTION_PLAN.md 6.5) plus 200 generated customers. Every
number is synthetic. The generator is seeded, so the output is reproducible.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = 20260930
TODAY = date(2026, 9, 30)
OUT = Path(__file__).resolve().parent / "customers.json"

# Twelve months of history: Oct 2025 .. Sep 2026 (year-end bonus in Dec, holiday pay in May).
MONTHS = [(2025, m) for m in range(10, 13)] + [(2026, m) for m in range(1, 10)]

NL_FIRST = ["Lotte", "Jonas", "Emma", "Wout", "Sofie", "Bram", "Marie", "Lucas", "Nele", "Thomas",
            "Elise", "Seppe", "An", "Koen", "Ilse", "Pieter", "Greet", "Jan", "Femke", "Dries",
            "Karen", "Bart", "Els", "Tom", "Hilde", "Geert", "Lieve", "Dirk", "Mieke", "Luc"]
FR_FIRST = ["Camille", "Nicolas", "Léa", "Julien", "Manon", "Maxime", "Chloé", "Antoine", "Justine",
            "Simon", "Laura", "Thomas", "Pauline", "Mathieu", "Sophie", "Olivier", "Isabelle",
            "Vincent", "Nathalie", "Philippe", "Catherine", "Michel", "Christine", "Jean", "Monique"]
NL_LAST = ["Peeters", "Janssens", "Maes", "Jacobs", "Mertens", "Willems", "Claes", "Goossens",
           "Wouters", "De Smet", "Vermeulen", "Van Damme", "Declercq", "Vandenbroucke", "Desmet",
           "Lambrechts", "Verhoeven", "Hermans", "Van den Berghe", "Coppens"]
FR_LAST = ["Dubois", "Lambert", "Martin", "Dupont", "Simon", "Laurent", "Leroy", "Lejeune",
           "Renard", "Michel", "Bertrand", "Fontaine", "Dumont", "Gérard", "Petit", "Lemaire",
           "Charlier", "Denis", "Pirlot", "Jacques"]
EMPLOYERS = {
    "nl": ["UZ Leuven", "KU Leuven", "Colruyt Group", "Stad Gent", "Proximus", "AB InBev",
           "Bpost", "Telenet", "Barco", "Umicore", "Vlaamse Overheid", "Delhaize"],
    "fr": ["Solvay", "UCB", "SNCB", "Ville de Namur", "Proximus", "AGC Glass Europe",
           "Province de Liège", "Ethias", "SPW Wallonie", "Delhaize", "Bpost", "Engie"],
}
LANDLORDS = {"nl": ["D. Peeters (verhuurder)", "Immo Vastgoed Leuven", "M. Claes (verhuurder)",
                    "Woonpunt cvba"],
             "fr": ["SCI Immo Namur", "J. Dubois (propriétaire)", "Régie Fontaine",
                    "Mme Lejeune (propriétaire)"]}
PENSION_PAYER = {"nl": "Federale Pensioendienst", "fr": "Service fédéral des Pensions"}
BENEFIT_PAYER = {"nl": "RVA werkloosheidsuitkering", "fr": "ONEM allocation de chômage"}
ENERGY = ["Doccle - Engie", "Doccle - Luminus"]
TELECOM = {"nl": ["Proximus", "Telenet"], "fr": ["Proximus", "VOO"]}
PUBLIC_TRANSPORT = {"flanders": "De Lijn", "wallonia": "TEC", "brussels": "STIB-MIVB"}
CHILDCARE = {"nl": "Kinderopvang 't Nestje", "fr": "Crèche Les Petits Loups"}
NOTARY = {"nl": "Notaris Van den Berghe", "fr": "Notaire Dupont"}
PENSION_SAVING = {"nl": "KBC Pensioensparen", "fr": "CBC Épargne-pension"}
INSURER = {"nl": "KBC Verzekeringen", "fr": "CBC Assurances"}
MORTGAGE_PAYEE = {"nl": "KBC Woningkrediet", "fr": "CBC Crédit logement"}
CLIENT_NL = ["Klant Bouwbedrijf Aerts", "Klant Praktijk Van Hove", "Klant Studio Mertens"]
CLIENT_FR = ["Client Menuiserie Renard", "Client Cabinet Laurent", "Client Atelier Dumont"]


def iso(d: date) -> str:
    return d.isoformat()


def years_between(d1: date, d2: date) -> int:
    years = d2.year - d1.year
    if (d2.month, d2.day) < (d1.month, d1.day):
        years -= 1
    return years


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year + years, day=28)


def month_day(year: int, month: int, day: int) -> date:
    last = (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day, last))


def tx(d: date, amount: float, payee: str, category: str) -> dict:
    return {"date": iso(d), "amount": round(amount, 2), "payee": payee, "category": category}


# ----------------------------------------------------------------------------
# Transactions
# ----------------------------------------------------------------------------

def build_transactions(rng: random.Random, c: dict, opts: dict) -> list[dict]:
    """12 months of realistic Belgian payees for one customer."""
    lang, region = c["language"], c["region"]
    emp = c["employment"]
    out: list[dict] = []
    salary_day = opts.get("salary_day", rng.choice([24, 25, 26, 27, 28]))
    salary_stop = opts.get("salary_stop")  # date after which no salary is paid
    benefit_from = opts.get("benefit_from")
    holiday_pay_day = opts.get("holiday_pay_day", 22)
    energy_base = opts.get("energy_base", rng.uniform(90, 220))
    energy_spike_from = opts.get("energy_spike_from")
    pension_step_from = opts.get("pension_step_from")
    telecom = rng.choice(TELECOM[lang])
    transport = rng.choice(["NMBS-SNCB", PUBLIC_TRANSPORT[region]])
    energy = rng.choice(ENERGY)

    for (y, m) in MONTHS:
        first = date(y, m, 1)
        # Income
        if emp["contract_type"] in ("permanent", "temporary"):
            pay_date = month_day(y, m, salary_day)
            if salary_stop is None or pay_date <= salary_stop:
                out.append(tx(pay_date, emp["net_monthly_salary"], emp["employer"], "salary"))
                if m == 5:
                    out.append(tx(month_day(y, m, holiday_pay_day), 0.92 * emp["gross_monthly_salary"],
                                  emp["employer"], "holiday_pay"))
                if m == 12:
                    out.append(tx(month_day(y, m, 20), 0.95 * emp["net_monthly_salary"],
                                  emp["employer"], "bonus"))
            elif benefit_from is not None and pay_date >= benefit_from:
                out.append(tx(month_day(y, m, 8), 0.6 * emp["net_monthly_salary"], BENEFIT_PAYER[lang],
                              "benefit"))
        elif emp["contract_type"] == "pension":
            amount = emp["net_monthly_salary"]
            if pension_step_from is not None and first < pension_step_from:
                amount = amount / 1.02
            out.append(tx(first, amount, PENSION_PAYER[lang], "pension"))
        elif emp["contract_type"] == "self_employed":
            clients = CLIENT_NL if lang == "nl" else CLIENT_FR
            for _ in range(rng.randint(2, 3)):
                out.append(tx(month_day(y, m, rng.randint(2, 27)),
                              emp["gross_monthly_salary"] * rng.uniform(0.25, 0.55),
                              rng.choice(clients), "invoice_income"))
        # Housing
        if c["housing"]["status"] == "renting":
            out.append(tx(first, -c["housing"]["monthly_rent"], c["housing"]["landlord"], "rent"))
        mortgage = c["products"].get("mortgage")
        if mortgage:
            out.append(tx(month_day(y, m, 5), -mortgage["monthly_payment"], MORTGAGE_PAYEE[lang], "mortgage"))
            deed = date.fromisoformat(mortgage["deed_date"])
            if deed.year == y and deed.month == m:
                out.append(tx(deed, -rng.uniform(3000, 9000), NOTARY[lang], "notary"))
        # Daily life
        for day in (6, 20):
            out.append(tx(month_day(y, m, day), -rng.uniform(70, 160), "Colruyt", "groceries"))
        if rng.random() < 0.5:
            out.append(tx(month_day(y, m, 13), -rng.uniform(25, 60), "Delhaize", "groceries"))
        if emp["contract_type"] in ("permanent", "temporary", "self_employed"):
            out.append(tx(month_day(y, m, 2), -rng.uniform(35, 180), transport, "transport"))
        amount = energy_base
        if energy_spike_from is not None and first >= energy_spike_from:
            amount = energy_base * 1.30
        out.append(tx(month_day(y, m, 12), -amount * rng.uniform(0.97, 1.03), energy, "energy"))
        out.append(tx(month_day(y, m, 15), -rng.uniform(35, 90), telecom, "telecom"))
        for child in c["household"]["children"]:
            if years_between(date.fromisoformat(child["birthdate"]), first) < 3:
                out.append(tx(month_day(y, m, 3), -rng.uniform(350, 650), CHILDCARE[lang], "childcare"))
                break
        ps = c["products"].get("pension_saving")
        if ps and ps["monthly"] > 0:
            out.append(tx(month_day(y, m, 10), -ps["monthly"], PENSION_SAVING[lang], "pension_saving"))
        for p in c["policies"]:
            renewal = date.fromisoformat(p["renewal_date"])
            last_paid = add_years(renewal, -1)
            if last_paid.year == y and last_paid.month == m:
                out.append(tx(last_paid, -p["premium"], INSURER[lang], "insurance"))
    out.sort(key=lambda t: t["date"])
    return out


def savings_history(rng: random.Random, balance: float, pattern: str) -> list[dict]:
    hist = []
    for i, (y, m) in enumerate(MONTHS):
        if pattern == "flat":
            b = balance + rng.uniform(-250, 250)
        elif pattern == "growing":
            b = balance * (0.72 + 0.28 * (i + 1) / len(MONTHS)) + rng.uniform(-200, 200)
        else:  # volatile
            b = balance * rng.uniform(0.45, 1.05)
        hist.append({"month": f"{y:04d}-{m:02d}", "balance": round(max(0.0, b), 2)})
    hist[-1]["balance"] = round(balance, 2)
    return hist


# ----------------------------------------------------------------------------
# Hero personas (ACTION_PLAN.md 6.5)
# ----------------------------------------------------------------------------

def persona_lien(rng: random.Random) -> dict:
    birth = date(1997, 4, 14)
    c = {
        "id": "lien", "name": "Lien Vandenbroucke", "first_name": "Lien",
        "language": "nl", "region": "flanders", "birthdate": iso(birth),
        "age": years_between(birth, TODAY), "digital_comfort": 5,
        "household": {"partner": False, "children": []},
        "employment": {"employer": "UZ Leuven", "gross_monthly_salary": 2500.0,
                       "net_monthly_salary": 2050.0, "contract_type": "permanent",
                       "self_employed": False, "company_car": None},
        "accounts": {"current_balance": 2450.0, "savings_balance": 26000.0,
                     "savings_opened_on": "2019-10-01", "fidelity_date": "2027-03-15",
                     "savings_history": savings_history(rng, 26000.0, "flat")},
        "housing": {"status": "renting", "rent_since": "2022-09-01", "monthly_rent": 950.0,
                    "landlord": "D. Peeters (verhuurder)"},
        "policies": [
            {"kind": "family", "renewal_date": "2027-02-01", "premium": 95.0, "new_premium": 98.0},
            {"kind": "hospitalisation", "renewal_date": "2027-07-01", "premium": 310.0, "new_premium": 331.0},
        ],
        "products": {"mortgage": None,
                     "pension_saving": {"contributions_ytd": 540.0, "ceiling": 1050, "monthly": 60.0},
                     "bolero": {"portfolio_value": 8500.0, "unrealised_gains": 1400.0, "gains_realised_ytd": 0.0}},
        "consents": {"use_insurance_data": True, "use_other_banks": False, "marketing": True},
    }
    c["transactions"] = build_transactions(rng, c, {"salary_day": 25, "holiday_pay_day": 22,
                                                     "energy_base": 120.0})
    return c


def persona_marc(rng: random.Random) -> dict:
    birth = date(1979, 6, 3)
    c = {
        "id": "marc", "name": "Marc Lambert", "first_name": "Marc",
        "language": "fr", "region": "wallonia", "birthdate": iso(birth),
        "age": years_between(birth, TODAY), "digital_comfort": 3,
        "household": {"partner": True, "children": [
            {"name": "Chloé", "birthdate": "2008-11-12"},
            {"name": "Louis", "birthdate": "2012-03-05"}]},
        "employment": {"employer": "Solvay", "gross_monthly_salary": 5200.0,
                       "net_monthly_salary": 3300.0, "contract_type": "permanent",
                       "self_employed": False,
                       "company_car": {"fuel": "diesel", "ordered_on": "2024-01-15",
                                       "lease_end": "2027-01-31"}},
        "accounts": {"current_balance": 4100.0, "savings_balance": 18000.0,
                     "savings_opened_on": "2010-03-01", "fidelity_date": "2027-01-10",
                     "savings_history": savings_history(rng, 18000.0, "growing")},
        "housing": {"status": "owner", "rent_since": None, "monthly_rent": None, "landlord": None},
        "policies": [
            {"kind": "home", "renewal_date": "2026-11-11", "premium": 520.0, "new_premium": 562.0},
            {"kind": "car", "renewal_date": "2027-03-20", "premium": 740.0, "new_premium": 770.0},
            {"kind": "family", "renewal_date": "2027-05-02", "premium": 120.0, "new_premium": 124.0},
            {"kind": "hospitalisation", "renewal_date": "2027-07-01", "premium": 480.0, "new_premium": 528.0},
        ],
        "products": {"mortgage": {"deed_date": "2015-06-12", "epc_label": "C",
                                  "outstanding": 142000.0, "monthly_payment": 985.0},
                     "pension_saving": {"contributions_ytd": 720.0, "ceiling": 1050, "monthly": 80.0},
                     "bolero": None},
        "consents": {"use_insurance_data": True, "use_other_banks": False, "marketing": True},
    }
    c["transactions"] = build_transactions(rng, c, {"salary_day": 27, "energy_base": 210.0})
    return c


def persona_rita(rng: random.Random) -> dict:
    birth = date(1955, 2, 20)
    c = {
        "id": "rita", "name": "Rita Declercq", "first_name": "Rita",
        "language": "nl", "region": "flanders", "birthdate": iso(birth),
        "age": years_between(birth, TODAY), "digital_comfort": 1,
        "household": {"partner": False, "children": [
            {"name": "Katrien", "birthdate": "1982-05-30"},
            {"name": "Wim", "birthdate": "1985-09-14"}]},
        "employment": {"employer": None, "gross_monthly_salary": 0.0,
                       "net_monthly_salary": 1900.0, "contract_type": "pension",
                       "self_employed": False, "company_car": None},
        "accounts": {"current_balance": 3200.0, "savings_balance": 48000.0,
                     "savings_opened_on": "1998-05-01", "fidelity_date": "2026-10-14",
                     "savings_history": savings_history(rng, 48000.0, "flat")},
        "housing": {"status": "owner", "rent_since": None, "monthly_rent": None, "landlord": None},
        "policies": [
            {"kind": "home", "renewal_date": "2026-11-05", "premium": 410.0, "new_premium": 438.0},
            {"kind": "family", "renewal_date": "2027-04-10", "premium": 105.0, "new_premium": 109.0},
            {"kind": "hospitalisation", "renewal_date": "2027-07-01", "premium": 620.0, "new_premium": 690.0},
        ],
        "products": {"mortgage": None, "pension_saving": None, "bolero": None,
                     "term_account": {"amount": 25000.0, "maturity_date": "2026-10-20", "rate": 2.1}},
        "consents": {"use_insurance_data": True, "use_other_banks": False, "marketing": True},
        "security": {"guardian_angel_active": False,
                     "recent_alert": {"kind": "vop_close_match", "date": "2026-09-28", "amount": 900.0,
                                      "payee_shown": "KBC Veiligheidsdienst",
                                      "payee_registered": "J. Peeters"}},
    }
    c["transactions"] = build_transactions(rng, c, {"energy_base": 150.0,
                                                     "energy_spike_from": date(2026, 6, 1),
                                                     "pension_step_from": date(2026, 6, 1)})
    return c


# ----------------------------------------------------------------------------
# Generated customers
# ----------------------------------------------------------------------------

def _term_account(n: int) -> dict | None:
    """About one in six customers holds a term account; separate RNG keeps the main sequence stable."""
    r = random.Random(10_000 + n)
    if r.random() > 0.17:
        return None
    return {"amount": float(r.choice([5000, 10000, 15000, 20000, 30000, 50000])),
            "maturity_date": iso(TODAY + timedelta(days=r.randint(5, 330))),
            "rate": round(r.uniform(1.6, 2.4), 2)}


def generate_customer(rng: random.Random, n: int, special: str | None) -> dict:
    lang = "nl" if rng.random() < 0.6 else "fr"
    region = ("flanders" if lang == "nl" else "wallonia") if rng.random() < 0.85 else "brussels"
    first = rng.choice(NL_FIRST if lang == "nl" else FR_FIRST)
    last = rng.choice(NL_LAST if lang == "nl" else FR_LAST)
    age = rng.randint(22, 78)
    birth = add_years(TODAY, -age) - timedelta(days=rng.randint(0, 364))
    age = years_between(birth, TODAY)
    if age < 35:
        comfort = rng.randint(4, 5)
    elif age < 55:
        comfort = rng.randint(3, 5)
    elif age < 65:
        comfort = rng.randint(2, 4)
    else:
        comfort = rng.randint(1, 3)

    # Household
    partner = rng.random() < (0.35 if age < 30 else 0.65)
    children = []
    if age >= 27 and rng.random() < 0.55:
        for _ in range(rng.randint(1, 3)):
            child_age = rng.randint(0, min(25, age - 20))
            cb = add_years(TODAY, -child_age) - timedelta(days=rng.randint(0, 364))
            children.append({"name": rng.choice(NL_FIRST if lang == "nl" else FR_FIRST), "birthdate": iso(cb)})
    if special == "child_18":
        cb = add_years(TODAY, -18) + timedelta(days=rng.randint(5, 55))  # turns 18 within 60 days
        children.append({"name": rng.choice(NL_FIRST if lang == "nl" else FR_FIRST), "birthdate": iso(cb)})

    # Employment
    company_car = None
    if age >= 66:
        emp = {"employer": None, "gross_monthly_salary": 0.0,
               "net_monthly_salary": round(rng.uniform(1400, 2600), 2),
               "contract_type": "pension", "self_employed": False, "company_car": None}
    elif rng.random() < 0.08:
        gross = round(rng.uniform(3500, 9000), 2)
        emp = {"employer": None, "gross_monthly_salary": gross,
               "net_monthly_salary": round(gross * 0.55, 2), "contract_type": "self_employed",
               "self_employed": True, "company_car": None}
    elif rng.random() < 0.04:
        emp = {"employer": None, "gross_monthly_salary": 0.0, "net_monthly_salary": 0.0,
               "contract_type": "none", "self_employed": False, "company_car": None}
    else:
        gross = round(rng.uniform(2300, 4200 + (age - 22) * 90), 2)
        emp = {"employer": rng.choice(EMPLOYERS[lang]), "gross_monthly_salary": gross,
               "net_monthly_salary": round(gross * rng.uniform(0.58, 0.66), 2),
               "contract_type": "permanent" if rng.random() < 0.85 else "temporary",
               "self_employed": False, "company_car": None}
        if gross > 4000 and rng.random() < 0.3 or special == "company_car":
            fuel = rng.choice(["diesel", "petrol", "hybrid", "electric"])
            ordered = date(rng.randint(2022, 2026), rng.randint(1, 12), rng.randint(1, 28))
            if ordered > TODAY:
                ordered = TODAY - timedelta(days=30)
            lease_end = add_years(ordered, 4)
            if lease_end <= TODAY:
                lease_end = TODAY + timedelta(days=rng.randint(60, 400))
            company_car = {"fuel": fuel, "ordered_on": iso(ordered), "lease_end": iso(lease_end)}
            emp["company_car"] = company_car

    # Housing
    rent_prob = 0.65 if age < 32 else 0.4 if age < 45 else 0.2
    if special == "first_home":
        rent_prob = 1.0
    mortgage = None
    if rng.random() < rent_prob:
        since = TODAY - timedelta(days=rng.randint(200, 8 * 365))
        if special == "first_home":
            since = TODAY - timedelta(days=rng.randint(3 * 365 + 10, 6 * 365))
        housing = {"status": "renting", "rent_since": iso(since),
                   "monthly_rent": round(rng.uniform(600, 1300), 0), "landlord": rng.choice(LANDLORDS[lang])}
    else:
        housing = {"status": "owner", "rent_since": None, "monthly_rent": None, "landlord": None}
        if age < 62 and (rng.random() < 0.6 or special == "renovation"):
            deed = date(rng.randint(2012, 2026), rng.randint(1, 12), rng.randint(1, 28))
            if deed > TODAY:
                deed = TODAY - timedelta(days=40)
            epc = rng.choices(["A", "B", "C", "D", "E", "F"], weights=[10, 20, 30, 20, 12, 8])[0]
            if special == "renovation":
                deed = date(rng.randint(2023, 2025), rng.randint(1, 12), rng.randint(1, 28))
                epc = rng.choice(["E", "F"])
            mortgage = {"deed_date": iso(deed), "epc_label": epc,
                        "outstanding": round(rng.uniform(60000, 320000), 0),
                        "monthly_payment": round(rng.uniform(650, 1500), 0)}

    # Accounts
    net = emp["net_monthly_salary"]
    savings = round(rng.choice([rng.uniform(0, 8000), rng.uniform(5000, 30000), rng.uniform(15000, 90000)]), 2)
    if special == "first_home":
        savings = round(rng.uniform(22000, 60000), 2)
    if special == "idle_cash":
        savings = round(max(16000, net * 6 + rng.uniform(2000, 25000)), 2)
    pattern = rng.choices(["flat", "growing", "volatile"], weights=[45, 35, 20])[0]
    if special in ("idle_cash", "first_home"):
        pattern = "flat"
    opened = TODAY - timedelta(days=rng.randint(400, 25 * 365))
    accounts = {"current_balance": round(rng.uniform(300, 6000), 2), "savings_balance": savings,
                "savings_opened_on": iso(opened),
                "fidelity_date": iso(TODAY + timedelta(days=rng.randint(1, 365))),
                "savings_history": savings_history(rng, savings, pattern)}

    # Policies (KBC is the insurer)
    policies = []
    def policy(kind: str, lo: float, hi: float) -> None:
        premium = round(rng.uniform(lo, hi), 0)
        increase = rng.choice([0.0, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10])
        renewal = TODAY + timedelta(days=rng.randint(1, 365))
        policies.append({"kind": kind, "renewal_date": iso(renewal), "premium": premium,
                         "new_premium": round(premium * (1 + increase), 0)})
    if housing["status"] == "owner" or rng.random() < 0.6:
        policy("home", 300, 700)
    if company_car is None and rng.random() < 0.55:
        policy("car", 450, 1100)
    if rng.random() < 0.7:
        policy("family", 80, 150)
    if rng.random() < 0.6:
        policy("hospitalisation", 250, 700)

    # Products
    pension_saving = None
    if emp["contract_type"] in ("permanent", "temporary", "self_employed") and age < 64 and rng.random() < 0.55:
        ceiling = 1050 if rng.random() < 0.8 else 1350
        monthly = round(rng.choice([0.0, 40.0, 60.0, 80.0, ceiling / 12]), 2)
        pension_saving = {"contributions_ytd": round(monthly * 9, 2), "ceiling": ceiling, "monthly": monthly}
    bolero = None
    if rng.random() < 0.3 or special == "capital_gains":
        value = round(rng.uniform(3000, 120000), 0)
        gains = round(value * rng.uniform(-0.1, 0.35), 0)
        if special == "capital_gains":
            value = round(rng.uniform(80000, 200000), 0)
            gains = round(value * rng.uniform(0.12, 0.3), 0)
        bolero = {"portfolio_value": value, "unrealised_gains": gains,
                  "gains_realised_ytd": round(max(0.0, gains) * rng.choice([0.0, 0.0, 0.2, 0.5]), 0)}

    consents = {"use_insurance_data": rng.random() > 0.08, "use_other_banks": rng.random() < 0.25,
                "marketing": rng.random() > 0.1}

    c = {
        "id": f"cust_{n:04d}", "name": f"{first} {last}", "first_name": first,
        "language": lang, "region": region, "birthdate": iso(birth), "age": age,
        "digital_comfort": comfort,
        "household": {"partner": partner, "children": children},
        "employment": emp, "accounts": accounts, "housing": housing, "policies": policies,
        "products": {"mortgage": mortgage, "pension_saving": pension_saving, "bolero": bolero,
                     "term_account": _term_account(n)},
        "consents": consents,
    }
    opts: dict = {}
    if special == "income_drop" and emp["contract_type"] in ("permanent", "temporary"):
        stop = TODAY - timedelta(days=rng.randint(70, 140))
        opts = {"salary_stop": stop, "benefit_from": stop + timedelta(days=30)}
    c["transactions"] = build_transactions(rng, c, opts)
    return c


def main() -> None:
    rng = random.Random(SEED)
    customers = [persona_lien(rng), persona_marc(rng), persona_rita(rng)]
    specials = (["income_drop"] * 7 + ["child_18"] * 6 + ["first_home"] * 8 + ["idle_cash"] * 12 +
                ["capital_gains"] * 8 + ["renovation"] * 6 + ["company_car"] * 8)
    for n in range(1, 201):
        special = specials[n - 1] if n - 1 < len(specials) else None
        customers.append(generate_customer(rng, n, special))
    # income-drop customers must actually be employees; retry deterministically if not
    payload = {"generated_on": iso(TODAY), "seed": SEED, "customers": customers}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_tx = sum(len(c["transactions"]) for c in customers)
    print(f"wrote {OUT} ({len(customers)} customers, {n_tx} transactions, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
