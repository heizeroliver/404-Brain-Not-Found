"""Kate Foresight API (FastAPI).

    uvicorn api:app --reload

Routes
  POST /login                      -> JWT (demo password from env)
  GET  /me                         -> profile of the token's customer
  GET  /me/moments                 -> arbitrated + narrated moments for today
  GET  /me/timeline                -> next 12 months (life calendar + world rules)
  POST /me/feedback                -> not_now | not_relevant | never | helpful
  GET/PUT /me/consents             -> consent toggles (change which rules run)
  GET  /me/voice/{moment_type}     -> Kate voice note (mp3) or 404
  GET  /admin/overview             -> aggregates over all customers (admin only)
  GET  /admin/rules, POST /admin/rules -> world rulebook (admin only, validated JSON)
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

import auth
import config
from engine.arbitrate import ArbitrationResult, arbitrate
from engine.models import Channel, Consents, Customer, Moment
from engine.narrate import gemini_backend, narrate
from engine.rules import LIFE_CALENDAR_RULES, run_rules
from engine.rules.rulebook import RULEBOOK, WorldRule
from engine.twin import build_twin
from engine.voice import synthesize
from goals_api import router as goals_router
from customer_api import router as customer_router
from control_api import router as control_router
from talk_api import router as talk_router
from voice_api import router as voice_router
from store import Store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("foresight.api")

app = FastAPI(title="Kate Foresight API", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
store = Store(config.CUSTOMERS_PATH, config.DECISION_LOG_PATH)
app.include_router(goals_router)  # /me/goals: customer-stated intent (goals_api.py)
app.include_router(customer_router)  # /me/overview, /me/timeline-v2, /me/advisor-requests (customer_api.py)
app.include_router(talk_router)  # /me/talk: Kate Talk conversation (talk_api.py)
app.include_router(voice_router)  # /me/talk/voice: push-to-talk (voice_api.py)
app.include_router(control_router)  # /admin/* control room v2 (control_api.py)

limiter = Limiter(key_func=get_remote_address, default_limits=[config.GLOBAL_RATE_LIMIT])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    if request.method in ("POST", "PUT"):
        length = request.headers.get("content-length")
        if length is None or not length.isdigit():
            return JSONResponse(status_code=411, content={"detail": "Content-Length required"})
        limit = VOICE_MAX_BYTES if request.url.path == "/me/talk/transcribe" else config.MAX_BODY_BYTES
        if int(length) > limit:
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/app"):
        # the single-file frontend (one-container deploy): own origin only, inline script/style in that file
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; media-src 'self' blob: https:; "
            "connect-src 'self' https://*.elevenlabs.io wss://*.elevenlabs.io https://api.us.elevenlabs.io; "
            "worker-src 'self' blob:; frame-src https://*.elevenlabs.io; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'")
        # the page may use the microphone for the Kate voice conversation (ElevenLabs agent)
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Never echo the submitted input (it may contain a password).
    errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ----------------------------------------------------------------- schemas --

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(pattern=r"^[a-z0-9_]{2,40}$")
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: auth.Role
    expires_in: int
    profile: dict[str, Any]


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moment_type: str = Field(pattern=r"^[a-z0-9_]{3,60}$")
    action: Literal["not_now", "not_relevant", "never", "helpful"]


class NarratedMoment(BaseModel):
    rank: int
    type: str
    source: str
    category: str
    stakes: str
    confidence: float
    window: tuple[date, date]
    channel: Channel
    delivery: str
    score: float
    message: str
    why: str
    cta_label: str
    narrator: str
    evidence: list[str]
    actions: list[str]
    human_review: bool
    legal_basis: str
    facts: dict[str, Any]


class MomentsResponse(BaseModel):
    today: date
    care_mode: bool
    narration: str
    moments: list[NarratedMoment]


class TimelineEntry(BaseModel):
    start: date
    end: date
    type: str
    source: str
    category: str
    stakes: str
    channel: Channel
    title: str
    evidence: list[str]


class TimelineResponse(BaseModel):
    today: date
    care_mode: bool
    entries: list[TimelineEntry]


# ----------------------------------------------------------------- helpers --

MAX_FEEDBACK_PER_CUSTOMER = 500  # in-memory store: bound what one token can append


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


AppLanguage = Literal["nl", "en", "fr"]
VOICE_MAX_BYTES = 1_000_000  # one short push-to-talk clip; every other route keeps the 64 KB cap
VOICE_AGENT_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
LANG_QUERY = Query("nl", description="App language: Dutch (default), English or French")


def _in_language(customer: Customer, lang: AppLanguage) -> Customer:
    """The app speaks NL, EN or FR; the customer's record is not changed. Stated goals are attached."""
    return store.with_goals(customer).model_copy(update={"language": lang})


def _customer(customer_id: str) -> Customer:
    customer = store.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown customer")
    return customer


def _narrated(customer: Customer, result: ArbitrationResult) -> list[NarratedMoment]:
    out: list[NarratedMoment] = []
    for rm in result.ranked:
        text = narrate(rm.moment, customer)
        m = rm.moment
        out.append(NarratedMoment(
            rank=rm.rank, type=m.type, source=m.source, category=m.category, stakes=m.stakes,
            confidence=m.confidence, window=m.window, channel=rm.channel, delivery=rm.delivery,
            score=rm.score, message=text["message"], why=text["why"], cta_label=text["cta_label"],
            narrator=text["narrator"], evidence=m.evidence, actions=m.actions,
            human_review=m.human_review, legal_basis=m.legal_basis, facts=m.facts))
    return out


def _month_steps(today: date, months: int = 12) -> list[date]:
    steps = [today]
    y, m = today.year, today.month
    for _ in range(months):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        steps.append(date(y, m, 1))
    return steps


def _feed(customer: Customer, today: date, record: bool) -> ArbitrationResult:
    return arbitrate(customer, run_rules(customer, today), today, store, record=record)


# ------------------------------------------------------------------ routes --

@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "customers": len(store.customers), "narration": gemini_backend() or "template"}


@app.post("/login", response_model=LoginResponse)
@limiter.limit(config.LOGIN_RATE_LIMIT)
def login(request: Request, body: LoginRequest) -> LoginResponse:
    # always evaluated (one hash either way): no user enumeration by timing
    password_ok = auth.verify_password(body.password, admin=body.customer_id == "admin")
    if body.customer_id == "admin":
        role: auth.Role = "admin"
        exists = True
        profile: dict[str, Any] = {"id": "admin", "name": "KBC control room", "role": "admin"}
    else:
        customer = store.get_customer(body.customer_id)
        role = "customer"
        exists = customer is not None
        profile = customer.public_profile() if customer else {}
    if not (password_ok and exists):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = auth.create_token(body.customer_id, role)
    return LoginResponse(access_token=token, role=role, expires_in=config.JWT_TTL_HOURS * 3600, profile=profile)


@app.get("/me")
def me(customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    return _customer(customer_id).public_profile()


@app.get("/me/moments", response_model=MomentsResponse)
def my_moments(customer_id: str = Depends(auth.current_customer_id),
               lang: AppLanguage = LANG_QUERY) -> MomentsResponse:
    customer = _in_language(_customer(customer_id), lang)
    today = config.today()
    result = _feed(customer, today, record=True)
    return MomentsResponse(today=today, care_mode=result.care_mode,
                           narration=gemini_backend() or "template",
                           moments=_narrated(customer, result))


@app.get("/me/timeline", response_model=TimelineResponse)
def my_timeline(customer_id: str = Depends(auth.current_customer_id),
                lang: AppLanguage = LANG_QUERY) -> TimelineResponse:
    customer = _in_language(_customer(customer_id), lang)
    today = config.today()
    seen: dict[tuple[str, date], Moment] = {}
    for i, step in enumerate(_month_steps(today)):
        for m in run_rules(customer, step, projectable_only=i > 0):
            seen.setdefault((m.type, m.window[1]), m)
    result = arbitrate(customer, list(seen.values()), today, store, record=False)
    entries = []
    for rm in sorted(result.ranked, key=lambda r: (r.moment.window[0], r.moment.type)):
        text = narrate(rm.moment, customer, allow_llm=False)
        m = rm.moment
        entries.append(TimelineEntry(start=m.window[0], end=m.window[1], type=m.type, source=m.source,
                                     category=m.category, stakes=m.stakes, channel=rm.channel,
                                     title=text["message"], evidence=m.evidence))
    return TimelineResponse(today=today, care_mode=result.care_mode, entries=entries)


@app.post("/me/feedback", status_code=status.HTTP_201_CREATED)
def my_feedback(body: FeedbackRequest, customer_id: str = Depends(auth.current_customer_id)) -> dict[str, Any]:
    _customer(customer_id)
    known = {m.TYPE for m in LIFE_CALENDAR_RULES} | {r.id for r in RULEBOOK.rules()}
    if body.moment_type not in known:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown moment type")
    if store.feedback_count(customer_id) >= MAX_FEEDBACK_PER_CUSTOMER:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too much feedback")
    entry = store.add_feedback(customer_id, body.moment_type, body.action)
    store.log_decisions([{"ts": entry["ts"], "customer_id": customer_id, "moment_type": body.moment_type,
                          "source": None, "stakes": None, "decision": "feedback", "reason": body.action,
                          "score": None, "channel": None, "delivery": None}])
    return {"ok": True, "moment_type": body.moment_type, "action": body.action}


@app.get("/me/consents", response_model=Consents)
def my_consents(customer_id: str = Depends(auth.current_customer_id)) -> Consents:
    return _customer(customer_id).consents


@app.put("/me/consents", response_model=Consents)
def update_consents(body: Consents, customer_id: str = Depends(auth.current_customer_id)) -> Consents:
    _customer(customer_id)
    updated = store.set_consents(customer_id, body)
    store.log_decisions([{"ts": _now(), "customer_id": customer_id, "moment_type": None,
                          "source": None, "stakes": None, "decision": "consent_update",
                          "reason": ", ".join(f"{k}={'on' if v else 'off'}" for k, v in updated.model_dump().items()),
                          "score": None, "channel": None, "delivery": None}])
    return updated


class AssistantConfig(BaseModel):
    enabled: bool
    agent_id: str | None = None
    dynamic_variables: dict[str, str] = Field(default_factory=dict)


@app.get("/me/assistant", response_model=AssistantConfig)
def my_assistant(customer_id: str = Depends(auth.current_customer_id),
                 lang: AppLanguage = LANG_QUERY) -> AssistantConfig:
    """Config for the Kate voice conversation (ElevenLabs agent widget).

    The agent only receives this customer's already-computed moments as context, so every
    number it can say comes from the engine. Nothing is returned when no agent is configured.
    """
    agent_id = config.ELEVENLABS_AGENT_ID
    if not agent_id or not VOICE_AGENT_ID.match(agent_id):
        return AssistantConfig(enabled=False)
    customer = _in_language(_customer(customer_id), lang)
    result = _feed(customer, config.today(), record=False)
    lines = []
    for rm in result.ranked[:6]:
        text = narrate(rm.moment, customer, allow_llm=False)
        lines.append(f"- {text['message']} (Why: {text['why']}) [channel: {rm.channel}]")
    language = {"nl": "Dutch (Flemish)", "en": "English", "fr": "French"}[lang]
    return AssistantConfig(enabled=True, agent_id=agent_id, dynamic_variables={
        "first_name": customer.first_name,
        "language": language,
        "care_mode": "yes" if result.care_mode else "no",
        "moments": "\n".join(lines)[:3000] or "- No moments today.",
    })


@app.get("/me/voice/{moment_type}")
@limiter.limit(config.VOICE_RATE_LIMIT)
def my_voice(request: Request, moment_type: str = Path(pattern=r"^[a-z0-9_]{3,60}$"),
             customer_id: str = Depends(auth.current_customer_id),
             lang: AppLanguage = LANG_QUERY) -> Response:
    customer = _in_language(_customer(customer_id), lang)
    result = _feed(customer, config.today(), record=False)
    match = next((rm for rm in result.ranked if rm.moment.type == moment_type), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such moment for this customer today")
    text = narrate(match.moment, customer)
    audio = synthesize(text["message"], customer.language)
    if audio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Voice not available")
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Content-Disposition": f'inline; filename="kate_{moment_type}.mp3"'})


# ------------------------------------------------------------------- admin --

@app.get("/admin/overview")
def admin_overview(_: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    today = config.today()
    by_type: Counter[str] = Counter()
    by_channel: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_delivery: Counter[str] = Counter()
    care_mode_ids: list[str] = []
    customers_with_moments = 0
    world: dict[str, dict[str, Any]] = {
        r.id: {"id": r.id, "title": r.title["en"], "effective_date": r.effective_date.isoformat(),
               "level": r.level, "affected": 0, "total_impact": 0.0}
        for r in RULEBOOK.rules()}
    for customer in store.customers.values():
        result = _feed(store.with_goals(customer), today, record=False)
        if result.care_mode:
            care_mode_ids.append(customer.id)
        if result.ranked:
            customers_with_moments += 1
        for rm in result.ranked:
            m = rm.moment
            by_type[m.type] += 1
            by_channel[rm.channel] += 1
            by_source[m.source] += 1
            by_delivery[rm.delivery] += 1
            if m.source == "world_rule" and m.type in world:
                world[m.type]["affected"] += 1
                amount = m.facts.get("amount")
                if isinstance(amount, (int, float)):
                    world[m.type]["total_impact"] += float(amount)
    consents = [c.consents for c in store.customers.values()]
    feedback_counts = Counter(fb["action"] for fb in store.feedback)
    return {
        "today": today.isoformat(),
        "customers_total": len(store.customers),
        "customers_with_moments": customers_with_moments,
        "moments_total": sum(by_type.values()),
        "moments_by_type": dict(by_type.most_common()),
        "moments_by_channel": dict(by_channel),
        "moments_by_source": dict(by_source),
        "moments_by_delivery": dict(by_delivery),
        "human_handoffs": by_channel.get("advisor", 0),
        "care_mode_count": len(care_mode_ids),
        "care_mode_customer_ids": care_mode_ids,
        "opt_outs": {
            "never_feedback": store.opt_out_count(),
            "marketing_off": sum(1 for c in consents if not c.marketing),
            "insurance_data_off": sum(1 for c in consents if not c.use_insurance_data),
            "other_banks_on": sum(1 for c in consents if c.use_other_banks),
        },
        "feedback_counts": dict(feedback_counts),
        "goals_total": store.goals_count(),
        "world_rules": list(world.values()),
        "decision_log_tail": store.decision_log_tail(30),
        "narration": gemini_backend() or "template",
    }


@app.get("/admin/rules")
def admin_rules(_: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    return {"rules": [r.model_dump(mode="json") for r in RULEBOOK.rules()]}


@app.post("/admin/rules", status_code=status.HTTP_201_CREATED)
def admin_add_rule(rule: WorldRule, principal: auth.Principal = Depends(auth.require_admin)) -> dict[str, Any]:
    try:
        RULEBOOK.add(rule)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    today = config.today()
    affected: list[str] = []
    total_impact = 0.0
    for customer in store.customers.values():
        if rule.requires_insurance_data and not customer.consents.use_insurance_data:
            continue
        twin = build_twin(customer, today)
        if rule.affected(twin):
            affected.append(customer.id)
            amount = rule.impact.compute(twin, today).get("amount")
            if isinstance(amount, (int, float)):
                total_impact += float(amount)
    store.log_decisions([{"ts": _now(), "customer_id": principal.subject, "moment_type": rule.id,
                          "source": "world_rule", "stakes": rule.stakes, "decision": "rule_added",
                          "reason": f"{len(affected)} customers affected", "score": None, "channel": None,
                          "delivery": None}])
    return {"rule": rule.model_dump(mode="json"), "affected_customers": len(affected),
            "sample_customer_ids": affected[:5], "total_impact": round(total_impact, 2),
            "customers_total": len(store.customers)}


# ------------------------------------------------------------- static app --
# One-container deploy (Cloud Run): the frontend is served from the same origin under /app.
if config.FRONTEND_DIR and os.path.isdir(config.FRONTEND_DIR):
    from fastapi.responses import RedirectResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/app", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="app")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/app/")
