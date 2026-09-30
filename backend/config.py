"""Configuration from environment variables only. No secrets in code."""
from __future__ import annotations

import logging
import os
import secrets
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

log = logging.getLogger("foresight")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


APP_ENV = _env("APP_ENV", "dev")


def jwt_secret() -> str:
    secret = _env("JWT_SECRET")
    if secret:
        if len(secret) < 32:
            if APP_ENV == "production":
                raise RuntimeError("JWT_SECRET must be at least 32 characters in production")
            log.warning("JWT_SECRET is shorter than 32 characters; use a random 48-byte value.")
        return secret
    if APP_ENV == "production":
        raise RuntimeError("JWT_SECRET is not set; refusing to start in production")
    generated = secrets.token_urlsafe(48)
    log.warning("JWT_SECRET not set: generated a random one for this dev process "
                "(tokens will not survive a restart). Set it in backend/.env.")
    return generated


def demo_password() -> str:
    pwd = _env("DEMO_PASSWORD")
    if not pwd:
        raise RuntimeError(
            "DEMO_PASSWORD is not set. Copy backend/.env.example to backend/.env and "
            "choose a demo password (or run ./run.sh, which generates one)."
        )
    return pwd


def admin_password() -> str:
    """Separate admin password, so a customer who knows the shared demo password is
    not an admin. Dev falls back to DEMO_PASSWORD (demo convenience); production refuses."""
    pwd = _env("ADMIN_PASSWORD")
    if pwd:
        return pwd
    if APP_ENV == "production":
        raise RuntimeError("ADMIN_PASSWORD is not set; refusing to start in production")
    log.warning("ADMIN_PASSWORD not set: the admin user accepts DEMO_PASSWORD (dev only).")
    return demo_password()


def today() -> date:
    """Demo clock. DEMO_TODAY=YYYY-MM-DD freezes the engine for reproducible demos."""
    raw = _env("DEMO_TODAY")
    if raw:
        return date.fromisoformat(raw)
    return date.today()


FRONTEND_ORIGIN = _env("FRONTEND_ORIGIN", "http://localhost:5173")
# Set in the container image; when set, the API also serves the frontend under /app (same origin).
FRONTEND_DIR = _env("FRONTEND_DIR")
CUSTOMERS_PATH = Path(_env("CUSTOMERS_PATH", str(BASE_DIR / "data" / "customers.json")))
DECISION_LOG_PATH = Path(_env("DECISION_LOG_PATH", str(BASE_DIR / "data" / "decision_log.jsonl")))
LOGIN_RATE_LIMIT = _env("LOGIN_RATE_LIMIT", "5/minute")
VOICE_RATE_LIMIT = _env("VOICE_RATE_LIMIT", "10/minute")
GLOBAL_RATE_LIMIT = _env("GLOBAL_RATE_LIMIT", "120/minute")  # per client IP, every route
MAX_BODY_BYTES = 64 * 1024  # request bodies above this are refused with 413
JWT_TTL_HOURS = 8

# Narration backends, in order of preference:
#   1. Gemini Developer API (GEMINI_API_KEY, also accepts GOOGLE_API_KEY)
#   2. Vertex AI (GCP_PROJECT + GCP_LOCATION, application-default credentials)
#   3. deterministic templates (always available, used by the tests)
GEMINI_API_KEY = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
GCP_PROJECT = _env("GCP_PROJECT")
GCP_LOCATION = _env("GCP_LOCATION", "europe-west1")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")

ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_NL = _env("ELEVENLABS_VOICE_NL")
ELEVENLABS_VOICE_FR = _env("ELEVENLABS_VOICE_FR")
ELEVENLABS_VOICE_EN = _env("ELEVENLABS_VOICE_EN")
# Optional: ElevenLabs conversational agent id ("Talk to Kate"); public agent id, not a secret
ELEVENLABS_AGENT_ID = _env("ELEVENLABS_AGENT_ID")
ELEVENLABS_MODEL = _env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
