"""Push-to-talk voice: status, transcribe guards (auth, type, size, key), amount parsing, mocked STT."""
from __future__ import annotations

import httpx
import pytest

import config
import voice_api
from voice_api import parse_amounts

WEBM = {"Content-Type": "audio/webm"}


@pytest.fixture(autouse=True)
def _reset_voice():
    voice_api.reset_rate_limit()
    yield
    voice_api.reset_rate_limit()


def _auth(headers_for, subject="lien", role="customer", extra=None):
    h = headers_for(subject, role)
    h.update(extra or {})
    return h


def test_voice_status_false_without_key(client, headers_for):
    r = client.get("/me/talk/voice-status", headers=headers_for("lien"))
    assert r.status_code == 200 and r.json() == {"stt": False, "tts": False}


def test_transcribe_503_without_key(client, headers_for):
    r = client.post("/me/talk/transcribe", headers=_auth(headers_for, extra=WEBM), content=b"\x1a\x45\xdf\xa3fake")
    assert r.status_code == 503 and "type" in r.json()["detail"]


def test_transcribe_413_over_limit(client, headers_for):
    r = client.post("/me/talk/transcribe", headers=_auth(headers_for, extra=WEBM), content=b"0" * 1_000_001)
    assert r.status_code == 413


def test_transcribe_415_wrong_type(client, headers_for):
    r = client.post("/me/talk/transcribe", headers=_auth(headers_for, extra={"Content-Type": "text/plain"}),
                    content=b"hello")
    assert r.status_code == 415


def test_transcribe_admin_token_403(client, headers_for):
    r = client.post("/me/talk/transcribe", headers=_auth(headers_for, "admin", "admin", WEBM), content=b"abc")
    assert r.status_code == 403
    assert client.post("/me/talk/transcribe", headers=WEBM, content=b"abc").status_code in (401, 403)


@pytest.mark.parametrize("text, expected", [
    ("ik wil achtduizend euro opzij", [8000]),
    ("€8.000", [8000]),
    ("Ik wil €8.000 beschikbaar houden", [8000]),
    ("I want to keep eight thousand euros aside", [8000]),
    ("je veux garder huit mille euros", [8000]),
    ("deux mille cinq cents euros", [2500]),
    ("achtduizend vijfhonderd voor een auto", [8500]),
    ("vijfentwintigduizend", [25000]),
    ("8 duizend euro", [8000]),
    ("8k for travel", [8000]),
    ("8,000 for the renovation", [8000]),
    ("achtduizend of tienduizend", []),
    ("€5.000 or maybe €8.000", []),
    ("een auto kopen", []),
    ("hallo Kate", []),
])
def test_amount_parsing(text, expected):
    assert parse_amounts(text) == expected


def test_transcribe_success_with_mocked_elevenlabs(client, headers_for, monkeypatch):
    seen = {}

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        seen.update(url=url, model=data["model_id"], lang=data["language_code"], has_key="xi-api-key" in headers,
                    timeout=timeout, mime=files["file"][2])
        return httpx.Response(200, json={"text": "Ik wil achtduizend euro opzij zetten voor mijn verbouwing"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "test-key-not-real")
    monkeypatch.setattr(voice_api.httpx, "post", fake_post)
    r = client.post("/me/talk/transcribe?lang=nl", headers=_auth(headers_for, extra={"Content-Type": "audio/ogg;codecs=opus"}),
                    content=b"OggSfake")
    assert r.status_code == 200
    body = r.json()
    assert body["text"].startswith("Ik wil achtduizend") and body["amount_candidates"] == [8000]
    assert seen == {"url": "https://api.elevenlabs.io/v1/speech-to-text", "model": "scribe_v1", "lang": "nld",
                    "has_key": True, "timeout": 30.0, "mime": "audio/ogg"}
    assert client.get("/me/talk/voice-status", headers=headers_for("lien")).json()["stt"] is True


def test_transcribe_upstream_failure_is_502(client, headers_for, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("blocked")
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "test-key-not-real")
    monkeypatch.setattr(voice_api.httpx, "post", boom)
    r = client.post("/me/talk/transcribe", headers=_auth(headers_for, extra=WEBM), content=b"abc")
    assert r.status_code == 502


def test_rate_limit_per_customer(client, headers_for):
    h = _auth(headers_for, extra=WEBM)
    codes = [client.post("/me/talk/transcribe", headers=h, content=b"abc").status_code for _ in range(11)]
    assert codes[:10] == [503] * 10 and codes[10] == 429


def test_speak_404_without_voice(client, headers_for):
    r = client.post("/me/talk/speak", headers=headers_for("lien"), json={"text": "Hallo"})
    assert r.status_code == 404
    assert client.post("/me/talk/speak", headers=headers_for("lien"), json={"text": ""}).status_code == 422
    assert client.post("/me/talk/speak", headers=headers_for("admin", "admin"), json={"text": "x"}).status_code == 403
