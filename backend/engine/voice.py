"""ElevenLabs text-to-speech for Kate's voice notes (AI disclosure first, AI Act Art. 50)."""
from __future__ import annotations

import hashlib
import logging
import re

import httpx

import config

log = logging.getLogger("foresight.voice")

DISCLOSURE = {
    "nl": "Ik ben Kate, de digitale assistent van KBC.",
    "fr": "Je suis Kate, l'assistante digitale de KBC.",
    "en": "I am Kate, KBC's digital assistant.",
}
VOICE_ID = re.compile(r"^[A-Za-z0-9]{8,64}$")
_cache: dict[str, bytes] = {}


def voice_id_for(lang: str) -> str | None:
    voice = {"nl": config.ELEVENLABS_VOICE_NL, "fr": config.ELEVENLABS_VOICE_FR}.get(lang)
    if voice and VOICE_ID.match(voice):
        return voice
    return None


def synthesize(text: str, lang: str) -> bytes | None:
    """Return mp3 bytes, or None when voice is not configured or the call fails."""
    key = config.ELEVENLABS_API_KEY
    voice = voice_id_for(lang)
    if not key or not voice:
        return None
    full_text = f"{DISCLOSURE.get(lang, DISCLOSURE['en'])} {text}"
    cache_key = hashlib.sha256(f"{lang}:{voice}:{full_text}".encode()).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": key, "accept": "audio/mpeg", "content-type": "application/json"},
            json={"text": full_text, "model_id": config.ELEVENLABS_MODEL, "language_code": lang},
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("ElevenLabs call failed: %s", type(exc).__name__)
        return None
    audio = response.content
    if len(_cache) < 200:
        _cache[cache_key] = audio
    return audio
