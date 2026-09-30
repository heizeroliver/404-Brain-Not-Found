"""Advisor requests created by customer actions (prototype, in-memory, synthetic identities only).

Status flow: requested -> in_review -> resolved. One open request per (customer, moment_type):
repeated clicks return the existing open request instead of creating a duplicate.
"""
from __future__ import annotations

import secrets
import threading
from datetime import datetime, timezone
from typing import Literal

Status = Literal["requested", "in_review", "resolved"]
OPEN: tuple[str, ...] = ("requested", "in_review")
MAX_PER_CUSTOMER = 20

_lock = threading.Lock()
_requests: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create(customer_id: str, moment_type: str, reason: str, context: dict) -> tuple[dict, bool]:
    """Return (request, created). created=False when an open request already exists."""
    with _lock:
        for r in _requests.values():
            if r["customer_id"] == customer_id and r["moment_type"] == moment_type and r["status"] in OPEN:
                return dict(r), False
        if sum(1 for r in _requests.values() if r["customer_id"] == customer_id) >= MAX_PER_CUSTOMER:
            raise OverflowError("too many requests")
        rid = "AR-" + secrets.token_hex(3).upper()
        r = {"id": rid, "customer_id": customer_id, "moment_type": moment_type, "reason": reason[:200],
             "context": context, "status": "requested", "created": _now(), "updated": _now()}
        _requests[rid] = r
        return dict(r), True


def for_customer(customer_id: str) -> list[dict]:
    with _lock:
        return [dict(r) for r in _requests.values() if r["customer_id"] == customer_id]


def all_requests(status: str | None = None) -> list[dict]:
    with _lock:
        return [dict(r) for r in _requests.values() if status in (None, "", r["status"])]


def set_status(request_id: str, status: Status) -> dict | None:
    with _lock:
        r = _requests.get(request_id)
        if r is None:
            return None
        r["status"] = status
        r["updated"] = _now()
        return dict(r)


def reset() -> None:
    with _lock:
        _requests.clear()
