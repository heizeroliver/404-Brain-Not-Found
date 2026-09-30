"""Push-to-talk voice for Kate Talk (see docs/TALK_CONTRACT.md).

  GET  /me/talk/voice-status -> {stt, tts}
  POST /me/talk/transcribe   -> {text, amount_candidates}  (raw audio/* body, <= 1 MB; never stored)
  POST /me/talk/speak        -> audio/mpeg (ElevenLabs TTS with the AI disclosure) or 404

The customer id comes only from the token. The audio clip is forwarded to
ElevenLabs Speech-to-Text and dropped; transcripts are never logged.
python-multipart is not installed, so the clip is posted as the raw request body
with its own Content-Type (audio/webm, audio/ogg, ...).
"""
from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

import auth
import config
from engine import voice as tts

log = logging.getLogger("foresight.voice")
router = APIRouter()

STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
STT_MODEL = "scribe_v1"
STT_LANG = {"nl": "nld", "en": "eng", "fr": "fra"}
MAX_AUDIO_BYTES = 1_000_000
MAX_TEXT = 300
ALLOWED_AUDIO = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav"}
RATE_LIMIT = 10
RATE_WINDOW = 60.0

# ------------------------------------------------------------------ rate limit (per customer, in memory)
_hits: dict[str, list[float]] = {}
_lock = threading.Lock()


def _rate_limit(customer_id: str) -> None:
    now = time.monotonic()
    with _lock:
        hits = [t for t in _hits.get(customer_id, []) if now - t < RATE_WINDOW]
        if len(hits) >= RATE_LIMIT:
            _hits[customer_id] = hits
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many voice requests, try again in a minute")
        hits.append(now)
        _hits[customer_id] = hits


def reset_rate_limit() -> None:
    with _lock:
        _hits.clear()


# ------------------------------------------------------------------ amount parsing
_WORDS: dict[str, Any] = {
    # nl
    "nul": 0, "een": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8,
    "negen": 9, "tien": 10, "elf": 11, "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15,
    "zestien": 16, "zeventien": 17, "achttien": 18, "negentien": 19, "twintig": 20, "dertig": 30,
    "veertig": 40, "vijftig": 50, "zestig": 60, "zeventig": 70, "tachtig": 80, "negentig": 90,
    "honderd": "H", "duizend": "T", "miljoen": "M",
    # en
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": "H", "thousand": "T", "million": "M", "millions": "M",
    # fr
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
    "cent": "H", "cents": "H", "mille": "T",
}
_CONNECTORS = {"en", "and", "et"}
_LONE_ARTICLES = {"een", "one", "un", "une"}
_MORPH = re.compile("(?:" + "|".join(sorted(map(re.escape, set(_WORDS) | {"en"}), key=len, reverse=True)) + ")")
_TOKEN = re.compile(r"\d+(?:[.,   ]\d{3})*(?:[.,]\d{1,2})?k?|[a-z]+")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _split_word(word: str) -> list[str] | None:
    """Split a (possibly compound) number word into morphemes, or None if it is not a number word."""
    parts: list[str] = []
    pos = 0
    while pos < len(word):
        m = _MORPH.match(word, pos)
        if not m:
            return None
        parts.append(m.group(0))
        pos = m.end()
    if not parts or parts[0] == "en" or parts[-1] == "en":
        return None
    return parts


def _digits(token: str) -> float | None:
    mult = 1000 if token.endswith("k") else 1
    token = token.rstrip("k")
    m = re.fullmatch(r"(\d+(?:[.,   ]\d{3})*)(?:[.,](\d{1,2}))?", token)
    if not m:
        return None
    whole = re.sub(r"\D", "", m.group(1))
    value = float(whole) + (float("0." + m.group(2)) if m.group(2) else 0.0)
    return value * mult


def _evaluate(items: list[Any]) -> float:
    total = 0.0
    cur = 0.0
    prev: Any = None
    for item in items:
        if item == "H":
            cur = (cur or 1) * 100
        elif item == "T":
            total += (cur or 1) * 1000
            cur = 0.0
        elif item == "M":
            total = (total + (cur or 1)) * 1_000_000 if total < 1000 else total + (cur or 1) * 1_000_000
            cur = 0.0
        elif item == 20 and prev == 4:  # quatre-vingt(s) = 80
            cur += 80 - 4
        else:
            cur += float(item)
        prev = item
    return total + cur


def parse_amounts(text: str) -> list[float]:
    """Amounts spoken or written in a transcript. One unambiguous amount -> [amount]; none or several -> []."""
    runs: list[tuple[list[Any], list[str]]] = []
    items: list[Any] = []
    words: list[str] = []
    pending_connector = False

    def flush() -> None:
        nonlocal items, words
        if items:
            runs.append((items, words))
        items, words = [], []

    for token in _TOKEN.findall(_normalize(text)):
        if token[0].isdigit():
            value = _digits(token)
            flush()
            pending_connector = False
            if value is not None:
                items, words = [value], [token]
            continue
        if token in _CONNECTORS and items:
            pending_connector = True
            continue
        parts = _split_word(token)
        if parts is None:
            flush()
            pending_connector = False
            continue
        morphs = [_WORDS[p] for p in parts if p != "en"]
        # after a digit only a multiplier may continue the run ("8 duizend", "8 thousand")
        if items and isinstance(items[-1], float) and len(items) == 1 and words[0][0].isdigit() and morphs[0] not in ("H", "T", "M"):
            flush()
        items.extend(morphs)
        words.append(token)
        pending_connector = False
    flush()

    values: set[float] = set()
    for run_items, run_words in runs:
        if len(run_words) == 1 and run_words[0] in _LONE_ARTICLES:
            continue
        value = _evaluate(run_items)
        if 0 < value <= 10_000_000:
            values.add(round(value, 2))
    if len(values) != 1:
        return []
    value = values.pop()
    return [int(value) if value.is_integer() else value]


# ------------------------------------------------------------------ routes
def _lang(lang: str) -> str:
    return lang if lang in STT_LANG else "nl"


@router.get("/me/talk/voice-status")
def voice_status(lang: Literal["nl", "en", "fr"] = Query("nl"),
                 customer_id: str = Depends(auth.current_customer_id)) -> dict[str, bool]:
    key = bool(config.ELEVENLABS_API_KEY)
    return {"stt": key, "tts": key and tts.voice_id_for(lang) is not None}


@router.post("/me/talk/transcribe")
async def transcribe(request: Request, lang: Literal["nl", "en", "fr"] = Query("nl"),
                     customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    _rate_limit(customer_id)
    mime = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_AUDIO:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "Send the recording as audio/webm, audio/ogg, audio/mp4, audio/mpeg or audio/wav")
    audio = await request.body()
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Recording too large (max 1 MB)")
    if not audio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty recording")
    key = config.ELEVENLABS_API_KEY
    if not key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Speech-to-text is not configured on this server; please type your question")
    ext = mime.split("/")[1].replace("x-", "").replace("mpeg", "mp3")
    try:
        response = httpx.post(
            STT_URL,
            headers={"xi-api-key": key},
            data={"model_id": STT_MODEL, "language_code": STT_LANG[_lang(lang)]},
            files={"file": (f"clip.{ext}", audio, mime)},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("ElevenLabs STT failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Transcription failed, please try again or type") from None
    finally:
        del audio  # never kept
    text = str(payload.get("text") or "").strip() if isinstance(payload, dict) else ""
    text = re.sub(r"\s+", " ", text)[:MAX_TEXT]
    return {"text": text, "amount_candidates": parse_amounts(text)}


class SpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=400)


@router.post("/me/talk/speak")
def speak(body: SpeakRequest, lang: Literal["nl", "en", "fr"] = Query("nl"),
          customer_id: str = Depends(auth.current_customer_id)) -> Response:
    _rate_limit(customer_id)
    audio = tts.synthesize(body.text.strip(), _lang(lang))
    if audio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Voice not available")
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Content-Disposition": 'inline; filename="kate_talk.mp3"', "Cache-Control": "no-store"})
