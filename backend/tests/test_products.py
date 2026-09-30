from __future__ import annotations

from datetime import date

import pytest

from engine import allocation, products
from engine.models import Goal
from tests.factories import make_customer


def _cust(**kw):
    return make_customer(**kw)


def _ans(text, c, lang="en"):
    return products.answer(text, c, lang, allocation.compute(c))


@pytest.mark.parametrize("text,lang,pid", [
    ("Wat is een KBC spaarrekening?", "nl", "savings_account"),
    ("Tell me about pension saving", "en", "pension_saving"),
    ("C'est quoi un prêt rénovation ?", "fr", "renovation_loan"),
    ("Hoe werkt een termijnrekening?", "nl", "term_account"),
    ("assurance habitation", "fr", "home_insurance"),
])
def test_product_question_matches(text, lang, pid):
    r = _ans(text, _cust(), lang)
    assert r and r["products"][0]["id"] == pid
    assert r["assumptions"] and "kbc.be" in r["assumptions"][0]


def test_non_product_returns_none():
    assert _ans("Hoeveel heb ik uitgegeven aan boodschappen?", _cust(), "nl") is None


def test_generic_ranks_renovation_for_goal():
    c = _cust(accounts={"savings_balance": 60000.0})  # surplus too: goal must still rank in
    c = c.model_copy(update={"goals": [Goal(id="g_0123456789ab", purpose="renovation", amount=8000,
                                            created=date(2026, 9, 1))]})
    r = _ans("Which KBC products fit me?", c, "en")
    ids = [p["id"] for p in r["products"]]
    assert "renovation_loan" in ids and len(ids) <= 3
    reno = next(p for p in r["products"] if p["id"] == "renovation_loan")
    assert "renovation goal" in reno["why"]
    assert _ans("welke producten heeft KBC voor mij?", c, "nl")["products"]
    assert _ans("quels produits pour moi ?", c, "fr")["products"]


def test_generic_without_signals_still_answers():
    c = _cust(accounts={"savings_balance": 0.0})
    r = _ans("what products does kbc offer", c)
    assert r["products"]


@pytest.mark.parametrize("text,kind", [
    ("Is Revolut beter dan KBC?", "competitor"),
    ("What are Belfius savings rates?", "competitor"),
    ("compte chez BNP Paribas", "competitor"),
    ("Tell me a joke", "offtopic"),
    ("Wat is het weerbericht voor morgen?", "offtopic"),
    ("Who won the football match?", "offtopic"),
    ("Write code in python", "offtopic"),
    ("Hoeveel heb ik uitgegeven?", None),
    ("Overschrijving naar ING van gisteren?", None),
    ("Wat is een spaarrekening?", None),
])
def test_out_of_scope(text, kind):
    assert products.out_of_scope(text) == kind
    if kind:
        for lang in ("nl", "en", "fr"):
            assert "KBC" in products.scope_message(kind, lang)


def test_never_promises_returns():
    c = _cust()
    texts = ["beleggingsplan", "investment plan", "plan d'investissement", "which kbc products",
             "pensioensparen", "woonkrediet"]
    for lang in ("nl", "en", "fr"):
        for t in texts:
            r = _ans(t, c, lang)
            blob = (r["message"] + " ".join(p["summary"] + p.get("why", "") for p in r["products"])).lower()
            for bad in ("guaranteed", "gegarandeerd", "garanti", "we recommend", "je moet", "you should buy"):
                assert bad not in blob, (t, lang, bad)
