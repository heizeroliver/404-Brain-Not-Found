"""Storage backends for the durable, shared, mutable state.

Selected explicitly with STORAGE=memory|firestore (default memory; the tests use memory).

Persisted (STORAGE=firestore):
  1. customer goals      customers/{customer_id}/goals/{goal_id}
  2. consents            customers/{customer_id}  field `consents` (merge write, other fields untouched)
  3. advisor requests    advisor_requests/{request_id}
                         advisor_open/{customer_id}__{moment_type}  (lock: at most one open request
                         per customer + moment type, created in the same transaction as the request)

Deliberately NOT persisted (stay in process memory in both modes, reset on restart, per instance):
feedback, deliveries and the in-memory decision log (the decision log also appends to a local JSONL
file). The customer dataset itself is synthetic and loaded from customers.json.

Rules:
  * Writes go to Firestore FIRST; the in-memory cache is updated only after the write succeeded.
    A failed write raises StorageError (mapped to HTTP 503 by `install_handlers`). There is no
    silent fallback to memory.
  * With STORAGE=firestore the client is created and a lightweight read is done at startup; if either
    fails the process refuses to start with a clear message.
  * Reads of goals and advisor requests go to Firestore (read-through), so several Cloud Run instances
    agree. Fine at demo scale.

`google-cloud-firestore` is imported lazily inside FirestoreBackend, so memory mode needs no GCP.
"""
from __future__ import annotations

import logging
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Protocol

log = logging.getLogger("foresight.persistence")

OPEN_STATUSES: tuple[str, ...] = ("requested", "in_review")
SAVE_FAILED = "Could not save; nothing was changed"
READ_FAILED = "Storage is temporarily unavailable; please retry"


class StorageError(RuntimeError):
    """The durable store could not complete an operation. Nothing was changed in memory.

    Not a ValueError on purpose: callers that map ValueError to 4xx must not swallow it.
    """

    def __init__(self, message: str, public: str = SAVE_FAILED) -> None:
        super().__init__(message)
        self.public = public


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_request_id() -> str:
    return "AR-" + secrets.token_hex(3).upper()


class Backend(Protocol):
    name: str
    durable: bool  # False: the Store's in-memory cache is the source of truth

    # goals (plain JSON dicts, Goal.model_dump(mode="json"))
    def load_all_goals(self) -> dict[str, list[dict]]: ...
    def list_goals(self, customer_id: str) -> list[dict]: ...
    def save_goal(self, customer_id: str, goal: dict) -> None: ...
    def delete_goal(self, customer_id: str, goal_id: str) -> bool: ...

    # consents
    def load_all_consents(self) -> dict[str, dict]: ...
    def save_consents(self, customer_id: str, consents: dict) -> None: ...

    # advisor requests
    def create_request(self, customer_id: str, moment_type: str, reason: str, context: dict,
                       max_per_customer: int) -> tuple[dict, bool]: ...
    def requests_for_customer(self, customer_id: str) -> list[dict]: ...
    def all_requests(self, status: str | None = None) -> list[dict]: ...
    def set_request_status(self, request_id: str, status: str) -> dict | None: ...
    def reset_requests(self) -> None: ...


class MemoryBackend:
    """Current demo behaviour: nothing survives a restart, and nothing is shared between instances.

    Goals and consents live in the Store's own dicts (this backend's goal/consent writes are no-ops);
    advisor requests live here.
    """

    name = "memory"
    durable = False

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[str, dict] = {}

    # goals / consents: the Store's cache is the only copy
    def load_all_goals(self) -> dict[str, list[dict]]:
        return {}

    def list_goals(self, customer_id: str) -> list[dict]:
        raise NotImplementedError("memory backend: read the Store cache")

    def save_goal(self, customer_id: str, goal: dict) -> None:
        return None

    def delete_goal(self, customer_id: str, goal_id: str) -> bool:
        return True

    def load_all_consents(self) -> dict[str, dict]:
        return {}

    def save_consents(self, customer_id: str, consents: dict) -> None:
        return None

    # advisor requests
    def create_request(self, customer_id: str, moment_type: str, reason: str, context: dict,
                       max_per_customer: int) -> tuple[dict, bool]:
        with self._lock:
            for r in self._requests.values():
                if r["customer_id"] == customer_id and r["moment_type"] == moment_type \
                        and r["status"] in OPEN_STATUSES:
                    return dict(r), False
            if sum(1 for r in self._requests.values() if r["customer_id"] == customer_id) >= max_per_customer:
                raise OverflowError("too many requests")
            rid = new_request_id()
            now = _now_iso()
            r = {"id": rid, "customer_id": customer_id, "moment_type": moment_type, "reason": reason,
                 "context": context, "status": "requested", "created": now, "updated": now}
            self._requests[rid] = r
            return dict(r), True

    def requests_for_customer(self, customer_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._requests.values() if r["customer_id"] == customer_id]

    def all_requests(self, status: str | None = None) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._requests.values() if status in (None, "", r["status"])]

    def set_request_status(self, request_id: str, status: str) -> dict | None:
        with self._lock:
            r = self._requests.get(request_id)
            if r is None:
                return None
            r["status"] = status
            r["updated"] = _now_iso()
            return dict(r)

    def reset_requests(self) -> None:
        with self._lock:
            self._requests.clear()


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds")
    return value


def _lock_id(customer_id: str, moment_type: str) -> str:
    return f"{customer_id}__{moment_type}".replace("/", "_")


class FirestoreBackend:
    """Firestore (sync client, application-default credentials = Cloud Run service identity)."""

    name = "firestore"
    durable = True
    TIMEOUT = 10.0

    def __init__(self, project: str | None, database: str = "(default)", client: Any = None) -> None:
        try:
            from google.cloud import firestore  # lazy: memory mode needs no GCP libraries
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise RuntimeError("STORAGE=firestore but google-cloud-firestore is not installed "
                               "(pip install -r requirements.lock)") from exc
        self._fs = firestore
        try:
            self.db = client or firestore.Client(project=project, database=database or "(default)")
        except Exception as exc:
            raise RuntimeError(f"STORAGE=firestore: could not create a Firestore client "
                               f"(project={project!r}, database={database!r}): {exc}. "
                               "Check GOOGLE_CLOUD_PROJECT, FIRESTORE_DATABASE and the service "
                               "account's roles/datastore.user.") from exc
        try:  # lightweight read so a misconfiguration fails at startup, not on the first click
            list(self.db.collection("advisor_requests").limit(1).get(timeout=self.TIMEOUT))
        except Exception as exc:
            raise RuntimeError(f"STORAGE=firestore: startup read failed (project={project!r}, "
                               f"database={database!r}): {exc}. Refusing to start; there is no "
                               "silent fallback to memory.") from exc
        log.info("Storage: Firestore (project=%s, database=%s)", project, database)

    # ------------------------------------------------------------ helpers
    @contextmanager
    def _guard(self, what: str, public: str = SAVE_FAILED) -> Iterator[None]:
        try:
            yield
        except (StorageError, OverflowError):
            raise
        except Exception as exc:
            log.error("Firestore %s failed: %s", what, exc)
            raise StorageError(f"Firestore {what} failed: {exc}", public=public) from exc

    def _goals(self, customer_id: str):
        return self.db.collection("customers").document(customer_id).collection("goals")

    @staticmethod
    def _clean_goal(data: dict) -> dict:
        return {k: v for k, v in data.items() if not k.startswith("_")}

    @staticmethod
    def _request_out(data: dict) -> dict:
        out = dict(data)
        for key in ("created", "updated"):
            out[key] = _iso(out.get(key)) or _now_iso()
        return out

    # -------------------------------------------------------------- goals
    def load_all_goals(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        with self._guard("load goals", READ_FAILED):
            for snap in self.db.collection_group("goals").stream(timeout=self.TIMEOUT):
                customer_id = snap.reference.parent.parent.id
                out.setdefault(customer_id, []).append(snap.to_dict())
        for cid, goals in out.items():
            goals.sort(key=lambda g: str(g.get("_created") or ""))
            out[cid] = [self._clean_goal(g) for g in goals]
        return out

    def list_goals(self, customer_id: str) -> list[dict]:
        with self._guard("list goals", READ_FAILED):
            snaps = list(self._goals(customer_id).stream(timeout=self.TIMEOUT))
        rows = [s.to_dict() for s in snaps]
        rows.sort(key=lambda g: str(g.get("_created") or ""))
        return [self._clean_goal(g) for g in rows]

    def save_goal(self, customer_id: str, goal: dict) -> None:
        with self._guard("save goal"):
            self._goals(customer_id).document(goal["id"]).set(
                {**goal, "_created": datetime.now(timezone.utc).isoformat(),
                 "_written": self._fs.SERVER_TIMESTAMP}, timeout=self.TIMEOUT)

    def delete_goal(self, customer_id: str, goal_id: str) -> bool:
        with self._guard("delete goal"):
            ref = self._goals(customer_id).document(goal_id)
            if not ref.get(timeout=self.TIMEOUT).exists:
                return False
            ref.delete(timeout=self.TIMEOUT)
            return True

    # ----------------------------------------------------------- consents
    def load_all_consents(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        with self._guard("load consents", READ_FAILED):
            for snap in self.db.collection("customers").stream(timeout=self.TIMEOUT):
                data = snap.to_dict() or {}
                if isinstance(data.get("consents"), dict):
                    out[snap.id] = data["consents"]
        return out

    def save_consents(self, customer_id: str, consents: dict) -> None:
        with self._guard("save consents"):  # merge: only this field, other fields untouched
            self.db.collection("customers").document(customer_id).set(
                {"consents": consents, "consents_updated": self._fs.SERVER_TIMESTAMP},
                merge=True, timeout=self.TIMEOUT)

    # --------------------------------------------------- advisor requests
    def create_request(self, customer_id: str, moment_type: str, reason: str, context: dict,
                       max_per_customer: int) -> tuple[dict, bool]:
        fs = self._fs
        requests = self.db.collection("advisor_requests")
        lock_ref = self.db.collection("advisor_open").document(_lock_id(customer_id, moment_type))

        @fs.transactional
        def txn(transaction) -> tuple[str, bool]:
            lock = lock_ref.get(transaction=transaction)
            if lock.exists:
                rid = (lock.to_dict() or {}).get("request_id")
                if rid:
                    existing = requests.document(rid).get(transaction=transaction)
                    if existing.exists and (existing.to_dict() or {}).get("status") in OPEN_STATUSES:
                        return rid, False
            query = requests.where(filter=fs.FieldFilter("customer_id", "==", customer_id))
            if sum(1 for _ in transaction.get(query)) >= max_per_customer:
                raise OverflowError("too many requests")
            rid = new_request_id()
            transaction.set(requests.document(rid), {
                "id": rid, "customer_id": customer_id, "moment_type": moment_type, "reason": reason,
                "context": context, "status": "requested",
                "created": fs.SERVER_TIMESTAMP, "updated": fs.SERVER_TIMESTAMP})
            transaction.set(lock_ref, {"request_id": rid, "customer_id": customer_id,
                                       "moment_type": moment_type, "created": fs.SERVER_TIMESTAMP})
            return rid, True

        with self._guard("create advisor request"):
            rid, created = txn(self.db.transaction())
            snap = requests.document(rid).get(timeout=self.TIMEOUT)
        return self._request_out(snap.to_dict() or {}), created

    def requests_for_customer(self, customer_id: str) -> list[dict]:
        fs = self._fs
        with self._guard("list advisor requests", READ_FAILED):
            query = self.db.collection("advisor_requests").where(
                filter=fs.FieldFilter("customer_id", "==", customer_id))
            return [self._request_out(s.to_dict() or {}) for s in query.stream(timeout=self.TIMEOUT)]

    def all_requests(self, status: str | None = None) -> list[dict]:
        fs = self._fs
        with self._guard("list advisor requests", READ_FAILED):
            query = self.db.collection("advisor_requests")
            if status:
                query = query.where(filter=fs.FieldFilter("status", "==", status))
            return [self._request_out(s.to_dict() or {}) for s in query.stream(timeout=self.TIMEOUT)]

    def set_request_status(self, request_id: str, status: str) -> dict | None:
        fs = self._fs
        ref = self.db.collection("advisor_requests").document(request_id)

        @fs.transactional
        def txn(transaction) -> bool:
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                return False
            data = snap.to_dict() or {}
            lock_ref = self.db.collection("advisor_open").document(
                _lock_id(data.get("customer_id", ""), data.get("moment_type", "")))
            lock = lock_ref.get(transaction=transaction)
            transaction.update(ref, {"status": status, "updated": fs.SERVER_TIMESTAMP})
            lock_owner = (lock.to_dict() or {}).get("request_id") if lock.exists else None
            if status not in OPEN_STATUSES and lock_owner == request_id:
                transaction.delete(lock_ref)  # resolved: a new request may be opened again
            elif status in OPEN_STATUSES and not lock.exists:
                transaction.set(lock_ref, {"request_id": request_id, "customer_id": data.get("customer_id"),
                                           "moment_type": data.get("moment_type"),
                                           "created": fs.SERVER_TIMESTAMP})
            return True

        with self._guard("update advisor request"):
            if not txn(self.db.transaction()):
                return None
            snap = ref.get(timeout=self.TIMEOUT)
        return self._request_out(snap.to_dict() or {})

    def reset_requests(self) -> None:
        raise RuntimeError("reset_requests is test-only and refused on Firestore")


# ------------------------------------------------------------------ selection
_backend: Backend | None = None
_backend_lock = threading.Lock()


def create_backend(storage: str | None = None) -> Backend:
    import config
    kind = (storage or config.STORAGE or "memory").lower()
    if kind == "memory":
        log.info("Storage: memory (a restart resets goals, consents and advisor requests)")
        return MemoryBackend()
    if kind == "firestore":
        return FirestoreBackend(config.GOOGLE_CLOUD_PROJECT, config.FIRESTORE_DATABASE or "(default)")
    raise RuntimeError(f"Unknown STORAGE={kind!r}; use 'memory' or 'firestore'")


def get_backend() -> Backend:
    """The process-wide backend, created on first use from config.STORAGE."""
    global _backend
    with _backend_lock:
        if _backend is None:
            _backend = create_backend()
        return _backend


def set_backend(backend: Backend | None) -> None:
    """Replace the process-wide backend (tests). None: re-create from config on next use."""
    global _backend
    with _backend_lock:
        _backend = backend


def install_handlers(app: Any) -> None:
    """Map StorageError to HTTP 503 {"detail": ...}. Call once in api.py after creating the app."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def _storage_error(request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.public},
                            headers={"Retry-After": "5", "Cache-Control": "no-store"})

    app.add_exception_handler(StorageError, _storage_error)
