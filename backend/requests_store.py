"""Advisor requests created by customer actions (prototype, synthetic identities only).

Status flow: requested -> in_review -> resolved. One open request per (customer, moment_type):
repeated clicks return the existing open request instead of creating a duplicate.

Storage is persistence.get_backend() (STORAGE=memory|firestore). With Firestore, duplicate
prevention is a lock doc advisor_open/{customer_id}__{moment_type} created in the same
transaction as the request and removed when the request is resolved; reads are read-through.
"""
from __future__ import annotations

from typing import Literal

import persistence

Status = Literal["requested", "in_review", "resolved"]
OPEN: tuple[str, ...] = persistence.OPEN_STATUSES
MAX_PER_CUSTOMER = 20


def create(customer_id: str, moment_type: str, reason: str, context: dict) -> tuple[dict, bool]:
    """Return (request, created). created=False when an open request already exists."""
    return persistence.get_backend().create_request(customer_id, moment_type, reason[:200], context,
                                                    MAX_PER_CUSTOMER)


def for_customer(customer_id: str) -> list[dict]:
    return persistence.get_backend().requests_for_customer(customer_id)


def all_requests(status: str | None = None) -> list[dict]:
    return persistence.get_backend().all_requests(status)


def set_status(request_id: str, status: Status) -> dict | None:
    return persistence.get_backend().set_request_status(request_id, status)


def reset() -> None:
    """Test helper: clear all requests (memory backend only)."""
    persistence.get_backend().reset_requests()
