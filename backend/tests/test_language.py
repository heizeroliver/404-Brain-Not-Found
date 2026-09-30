"""The app speaks NL (default), EN and FR; anything else is rejected."""


def test_default_language_is_dutch(client, headers_for):
    feed = client.get("/me/moments", headers=headers_for("rita")).json()["moments"]
    protection = next(m for m in feed if m["type"] == "payment_protection")
    assert "tegengehouden" in protection["message"]


def test_english_and_french_on_request(client, headers_for):
    h = headers_for("rita")
    en = client.get("/me/moments?lang=en", headers=h).json()["moments"]
    fr = client.get("/me/moments?lang=fr", headers=h).json()["moments"]
    assert "we held a payment" in next(m for m in en if m["type"] == "payment_protection")["message"]
    assert "nous avons retenu" in next(m for m in fr if m["type"] == "payment_protection")["message"]
    assert client.get("/me/timeline?lang=fr", headers=h).status_code == 200


def test_unknown_language_is_rejected(client, headers_for):
    assert client.get("/me/moments?lang=de", headers=headers_for("lien")).status_code == 422


def test_rita_storyline_moments(client, headers_for):
    body = client.get("/me/moments", headers=headers_for("rita")).json()
    types = {m["type"] for m in body["moments"]}
    assert {"payment_protection", "energy_bill_spike"} <= types
    assert body["care_mode"] is True  # protection first: offers such as the term account are held back
    protection = next(m for m in body["moments"] if m["type"] == "payment_protection")
    assert protection["channel"] == "advisor" and protection["human_review"] is True
