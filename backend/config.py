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
        if len(secret) < 32 and APP_ENV == "production":
            raise RuntimeError("JWT_SECRET must be at least 32 characters in production")
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


def today() -> date:
    """Demo clock. DEMO_TODAY=YYYY-MM-DD freezes the engine for reproducible demos."""
    raw = _env("DEMO_TODAY")
    if raw:
        return date.fromisoformat(raw)
    return date.today()


FRONTEND_ORIGIN = _env("FRONTEND_ORIGIN", "http://localhost:5173")
CUSTOMERS_PATH = Path(_env("CUSTOMERS_PATH", str(BASE_DIR / "data" / "customers.json")))
DECISION_LOG_PATH = Path(_env("DECISION_LOG_PATH", str(BASE_DIR / "data" / "decision_log.jsonl")))
LOGIN_RATE_LIMIT = _env("LOGIN_RATE_LIMIT", "5/minute")
VOICE_RATE_LIMIT = _env("VOICE_RATE_LIMIT", "10/minute")
JWT_TTL_HOURS = 8

GCP_PROJECT = _env("GCP_PROJECT")
GCP_LOCATION = _env("GCP_LOCATION", "europe-west1")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.5-flash")

ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_NL = _env("ELEVENLABS_VOICE_NL")
ELEVENLABS_VOICE_FR = _env("ELEVENLABS_VOICE_FR")
ELEVENLABS_MODEL = _env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
