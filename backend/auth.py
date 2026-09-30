"""Authentication and authorization.

- One demo password (env DEMO_PASSWORD) shared by every persona; the admin user
  has its own ADMIN_PASSWORD (dev falls back to DEMO_PASSWORD, production refuses).
  Both are hashed with PBKDF2 at startup and compared in constant time.
  Demo-only: a real deployment would use itsme / the KBC identity platform.
- JWT (HS256, 8 hours) with claims sub (customer id or "admin") and role.
- Every /me/* route derives the customer id from the token only. There is no
  path or body parameter that names a customer, which removes the IDOR class.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Iterator
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import config

ALGORITHM = "HS256"
PBKDF2_ITERATIONS = 100_000
Role = Literal["customer", "admin"]

_SECRET = config.jwt_secret()
_SALT = secrets.token_bytes(16)


def _hash(password: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _SALT, PBKDF2_ITERATIONS)


_DEMO_HASH = _hash(config.demo_password())
_ADMIN_HASH = _hash(config.admin_password())


# Cache of recent PBKDF2 results, keyed by a keyed (HMAC) digest of the attempt, never the
# plaintext: a flood repeating the same guesses costs one cheap HMAC instead of 100k iterations.
_CACHE_KEY = secrets.token_bytes(32)
_CACHE_MAX = 1024
_verify_cache: "OrderedDict[bytes, bool]" = OrderedDict()
_cache_lock = threading.Lock()


def verify_password(password: str, admin: bool = False) -> bool:
    """Constant-time comparison against the hashed demo (or admin) password."""
    key = hmac.new(_CACHE_KEY, (("a:" if admin else "c:") + password).encode("utf-8"), hashlib.sha256).digest()
    with _cache_lock:
        cached = _verify_cache.get(key)
        if cached is not None:
            _verify_cache.move_to_end(key)
            return cached
    ok = hmac.compare_digest(_hash(password), _ADMIN_HASH if admin else _DEMO_HASH)
    with _cache_lock:
        _verify_cache[key] = ok
        while len(_verify_cache) > _CACHE_MAX:
            _verify_cache.popitem(last=False)
    return ok


# Global (all clients together) guard on the expensive login path, on top of slowapi's per-IP
# limit: distributed attackers cannot pin every worker on PBKDF2.
LOGIN_MAX_CONCURRENT = 4
LOGIN_GLOBAL_PER_MINUTE = 300
_login_slots = threading.BoundedSemaphore(LOGIN_MAX_CONCURRENT)
_login_times: deque[float] = deque()
_login_lock = threading.Lock()


class LoginBusy(Exception):
    """The global login budget is exhausted; the caller answers 503/429."""


def _take_global_budget(now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _login_lock:
        while _login_times and now - _login_times[0] > 60.0:
            _login_times.popleft()
        if len(_login_times) >= LOGIN_GLOBAL_PER_MINUTE:
            return False
        _login_times.append(now)
        return True


@contextlib.contextmanager
def login_guard(timeout: float = 2.0) -> Iterator[None]:
    if not _take_global_budget():
        raise LoginBusy("global login rate exceeded")
    if not _login_slots.acquire(timeout=timeout):
        raise LoginBusy("too many concurrent logins")
    try:
        yield
    finally:
        _login_slots.release()


class Principal(BaseModel):
    subject: str
    role: Role


def create_token(subject: str, role: Role) -> str:
    now = int(time.time())
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + config.JWT_TTL_HOURS * 3600,
               "iss": "kate-foresight"}
    return jwt.encode(payload, _SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> Principal:
    payload = jwt.decode(token, _SECRET, algorithms=[ALGORITHM], issuer="kate-foresight",
                         options={"require": ["exp", "iat", "sub", "iss", "role"]})
    role = payload.get("role")
    if role not in ("customer", "admin") or not isinstance(payload.get("sub"), str):
        raise jwt.InvalidTokenError("bad claims")
    return Principal(subject=payload["sub"], role=role)


_bearer = HTTPBearer(auto_error=False)


def current_principal(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from None


def current_customer_id(principal: Principal = Depends(current_principal)) -> str:
    """The ONLY source of a customer id for /me/* routes."""
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customer token required")
    return principal.subject


def require_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return principal
