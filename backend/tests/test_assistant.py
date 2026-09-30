"""Talk to Kate: the voice agent gets only the caller's computed moments."""
import config


def test_assistant_disabled_without_agent(client, headers_for, monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_AGENT_ID", None)
    body = client.get("/me/assistant", headers=headers_for("lien")).json()
    assert body == {"enabled": False, "agent_id": None, "dynamic_variables": {}}


def test_assistant_context_is_the_callers_own_moments(client, headers_for, monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_AGENT_ID", "agent_demo1234")
    rita = client.get("/me/assistant?lang=en", headers=headers_for("rita")).json()
    assert rita["enabled"] and rita["agent_id"] == "agent_demo1234"
    v = rita["dynamic_variables"]
    assert v["first_name"] == "Rita" and v["language"] == "English" and v["care_mode"] == "yes"
    assert "we held a payment" in v["moments"]
    lien = client.get("/me/assistant", headers=headers_for("lien")).json()["dynamic_variables"]
    assert lien["first_name"] == "Lien" and "Rita" not in lien["moments"]


def test_assistant_requires_a_customer_token(client, headers_for, monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_AGENT_ID", "agent_demo1234")
    assert client.get("/me/assistant").status_code == 401
    assert client.get("/me/assistant", headers=headers_for("admin", "admin")).status_code == 403
