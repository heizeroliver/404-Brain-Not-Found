"""Test configuration: offline, deterministic, no real secrets.

Environment is set before the app is imported. `load_dotenv` never overrides
variables that are already set, so a developer's backend/.env cannot leak
Gemini or ElevenLabs keys into the test run.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

os.environ["JWT_SECRET"] = "test-only-secret-" + "0123456789abcdef" * 3
os.environ["DEMO_PASSWORD"] = "test-demo-password"
os.environ["DEMO_TODAY"] = "2026-09-30"
os.environ["APP_ENV"] = "test"
os.environ["LOGIN_RATE_LIMIT"] = "5/minute"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["GLOBAL_RATE_LIMIT"] = "10000/minute"
for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GCP_PROJECT", "ELEVENLABS_API_KEY"):
    os.environ[key] = ""
os.environ["DECISION_LOG_PATH"] = str(pathlib.Path(tempfile.mkdtemp()) / "decision_log.jsonl")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
from api import app, store  # noqa: E402
from engine.rules.rulebook import RULEBOOK  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def headers_for():
    """Bearer headers for a subject, minted directly (no /login, so no rate-limit noise)."""
    def _make(subject: str, role: str = "customer") -> dict[str, str]:
        return {"Authorization": f"Bearer {auth.create_token(subject, role)}"}
    return _make


@pytest.fixture(autouse=True)
def _reset_state():
    yield
    store.feedback.clear()
    store.deliveries.clear()
    store.goals.clear()
    RULEBOOK.reset()
