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

import hashlib
import hmac
import secrets
import time
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


def verify_password(password: str, admin: bool = False) -> bool:
    """Constant-time comparison against the hashed demo (or admin) password."""
    return hmac.compare_digest(_hash(password), _ADMIN_HASH if admin else _DEMO_HASH)


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
