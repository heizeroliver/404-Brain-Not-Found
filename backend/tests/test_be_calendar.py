"""Belgian money calendar: engine + GET /me/money-calendar."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from engine import be_calendar

TODAY = date(2026, 9, 30)


def _get(client, headers, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get("/me/money-calendar" + (f"?{q}" if q else ""), headers=headers)


def test_requires_token(client):
    assert client.get("/me/money-calendar").status_code == 401


def test_bad_lang_and_category_rejected(client, headers_for):
    h = headers_for("lien")
    assert _get(client, h, lang="de").status_code == 422
    assert _get(client, h, category="crypto").status_code == 422


@pytest.mark.parametrize("lang", ["nl", "en", "fr"])
def test_shape_and_languages(client, headers_for, lang):
    r = _get(client, headers_for("marc"), lang=lang)
    assert r.status_code == 200
    d = r.json()
    assert d["as_of"] == TODAY.isoformat() and d["disclaimer"]
    assert [c["key"] for c in d["categories"]] == list(be_calendar.CATEGORIES)
    assert sum(c["count"] for c in d["categories"]) == len(d["items"])
    dates = [i["date"] for i in d["items"]]
    assert dates == sorted(dates)
    sources = {i["source"] for i in d["items"]}
    assert sources == {"you", "belgium"}
    limit = (TODAY + timedelta(days=365)).isoformat()
    for i in d["items"]:
        assert TODAY.isoformat() <= i["date"] <= limit
        if i["source"] == "belgium":
            assert i["basis"] in be_calendar.BASES and i["tip"] and i["what"] and i["source_hint"]


def test_every_item_translated_with_basis():
    from api import store
    for cid in ("lien", "marc", "rita"):
        c = store.customers[cid] if hasattr(store, "customers") else None
        if c is None:
            pytest.skip("store has no customers map")
        for it in be_calendar.build(c, TODAY):
            assert it.category in be_calendar.CATEGORIES and it.basis in be_calendar.BASES
            for field in (it.title, it.what, it.tip):
                assert set(field) == {"nl", "en", "fr"} and all(v.strip() for v in field.values())
            assert TODAY <= it.start <= TODAY + timedelta(days=365)
            if it.end:
                assert it.end >= it.start


def test_category_filter(client, headers_for):
    d = _get(client, headers_for("marc"), lang="en", category="tax").json()
    assert d["items"] and all(i["category"] == "tax" for i in d["items"])
    tax = next(c for c in d["categories"] if c["key"] == "tax")
    assert tax["count"] == len(d["items"])


def _by_id(client, headers):
    return {i["id"]: i for i in _get(client, headers, lang="en").json()["items"] if i["source"] == "belgium"}


def test_for_you_depends_on_customer(client, headers_for):
    lien, marc = _by_id(client, headers_for("lien")), _by_id(client, headers_for("marc"))
    # lien rents, marc owns with a mortgage
    assert marc["mortgage_certificate"]["for_you"] and not lien["mortgage_certificate"]["for_you"]
    assert marc["property_tax_bill"]["for_you"] and not lien["property_tax_bill"]["for_you"]
    assert lien["rent_indexation"]["for_you"] and "rent_indexation" not in marc
    assert marc["child_benefit"]["for_you"] and not lien["child_benefit"]["for_you"]
    assert "policy_cancel_car" in marc and "policy_cancel_car" not in lien


def test_pension_deadline_is_year_end():
    from engine.models import Customer, PensionSaving, Products
    c = Customer(id="t1", name="T", first_name="T", language="en", region="flanders", age=40,
                 birthdate=date(1986, 1, 1), digital_comfort=3,
                 products=Products(pension_saving=PensionSaving()))
    items = {i.id: i for i in be_calendar.build(c, TODAY)}
    p = items["pension_saving_deadline"]
    assert p.start == date(2026, 12, 31) and p.basis == "legal" and p.relevant(c)
