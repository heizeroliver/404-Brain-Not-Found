"""Persistence layer tests.

IMPORTANT: these are MOCKED tests. `FakeFirestore` below is a tiny in-process stand-in that
implements only the calls FirestoreBackend makes. Passing here is NOT a check against real
Firestore semantics (transactions, indexes, IAM). The emulator test at the bottom runs only when
FIRESTORE_EMULATOR_HOST is set, and is skipped otherwise.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

import persistence
import requests_store
from engine.models import Consents, Goal
from persistence import FirestoreBackend, MemoryBackend, StorageError
from store import Store

import config

_SERVER_TS = object()


# ------------------------------------------------------------------ fake Firestore
class _Snap:
    def __init__(self, ref, data):
        self.reference, self.id, self._data = ref, ref.id, data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return None if self._data is None else dict(self._data)


class _Doc:
    def __init__(self, db, path):
        self.db, self.path, self.id = db, path, path.rsplit("/", 1)[-1]

    @property
    def parent(self):
        return _Coll(self.db, self.path.rsplit("/", 1)[0])

    def collection(self, name):
        return _Coll(self.db, f"{self.path}/{name}")

    def get(self, timeout=None, transaction=None):
        return _Snap(self, self.db.docs.get(self.path))

    def _resolve(self, data):
        now = datetime.now(timezone.utc)
        return {k: (now if v is _SERVER_TS else v) for k, v in data.items()}

    def set(self, data, merge=False, timeout=None):
        self.db.write_check()
        base = dict(self.db.docs.get(self.path) or {}) if merge else {}
        base.update(self._resolve(data))
        self.db.docs[self.path] = base

    def update(self, data, timeout=None):
        self.set(data, merge=True)

    def delete(self, timeout=None):
        self.db.write_check()
        self.db.docs.pop(self.path, None)


class _Query:
    def __init__(self, db, path, filters=(), limit=None, group=False):
        self.db, self.path, self.filters, self._limit, self.group = db, path, filters, limit, group

    def where(self, filter):
        return _Query(self.db, self.path, self.filters + (filter,), self._limit, self.group)

    def limit(self, n):
        return _Query(self.db, self.path, self.filters, n, self.group)

    def stream(self, timeout=None):
        self.db.read_check()
        out = []
        for path, data in list(self.db.docs.items()):
            parent, _ = path.rsplit("/", 1)
            if self.group:
                if parent.rsplit("/", 1)[-1] != self.path:
                    continue
            elif parent != self.path:
                continue
            if all(data.get(f) == v for f, v in self.filters):
                out.append(_Snap(_Doc(self.db, path), data))
        return out[: self._limit] if self._limit else out

    get = stream


class _Coll(_Query):
    def __init__(self, db, path):
        super().__init__(db, path)
        self.id = path.rsplit("/", 1)[-1]

    @property
    def parent(self):
        return _Doc(self.db, self.path.rsplit("/", 1)[0])

    def document(self, doc_id):
        return _Doc(self.db, f"{self.path}/{doc_id}")


class _Txn:
    """Applies writes immediately (the fake is single-threaded; no real isolation)."""

    def get(self, ref_or_query):
        return ref_or_query.stream() if isinstance(ref_or_query, _Query) else ref_or_query.get()

    def set(self, ref, data):
        ref.set(data)

    def update(self, ref, data):
        ref.update(data)

    def delete(self, ref):
        ref.delete()


class FakeFirestore:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.fail_writes = False
        self.fail_reads = False

    def write_check(self):
        if self.fail_writes:
            raise ConnectionError("simulated Firestore outage")

    def read_check(self):
        if self.fail_reads:
            raise ConnectionError("simulated Firestore outage")

    def collection(self, name):
        return _Coll(self, name)

    def collection_group(self, name):
        return _Query(self, name, group=True)

    def transaction(self):
        return _Txn()


FAKE_FS_MODULE = SimpleNamespace(transactional=lambda fn: fn, SERVER_TIMESTAMP=_SERVER_TS,
                                 FieldFilter=lambda field, op, value: (field, value))


@pytest.fixture
def fake_db():
    return FakeFirestore()


@pytest.fixture
def fs_backend(fake_db):
    pytest.importorskip("google.cloud.firestore")
    backend = FirestoreBackend("demo-project", client=fake_db)
    backend._fs = FAKE_FS_MODULE
    return backend


@pytest.fixture
def use_backend():
    def _use(backend):
        persistence.set_backend(backend)
        return backend
    yield _use
    persistence.set_backend(None)  # back to config (memory) for the rest of the suite


def _goal(n: int = 0) -> Goal:
    return Goal(id="g_" + f"{n:012x}", purpose="travel", amount=1000 + n, created=date(2026, 9, 30))


def _store(backend) -> Store:
    return Store(config.CUSTOMERS_PATH, None, backend=backend)


# ------------------------------------------------------------------ tests
def test_default_storage_is_memory():
    assert config.STORAGE == "memory"
    assert isinstance(persistence.get_backend(), MemoryBackend)


def test_unknown_storage_refused():
    with pytest.raises(RuntimeError, match="Unknown STORAGE"):
        persistence.create_backend("sqlite")


def test_memory_backend_restart_semantics():
    """Memory mode: a new Store (= a process restart) starts with no goals. Documented behaviour."""
    s1 = _store(MemoryBackend())
    cid = next(iter(s1.customers))
    s1.add_goal(cid, _goal(1))
    assert len(s1.list_goals(cid)) == 1
    assert _store(MemoryBackend()).list_goals(cid) == []


def test_firestore_goals_survive_restart(fs_backend):
    s1 = _store(fs_backend)
    cid = next(iter(s1.customers))
    s1.add_goal(cid, _goal(1))
    s1.add_goal(cid, _goal(2))
    s2 = _store(fs_backend)  # new process, same database
    assert [g.id for g in s2.goals[cid]] == [_goal(1).id, _goal(2).id]  # warmed at startup
    assert s2.delete_goal(cid, _goal(1).id).id == _goal(1).id
    assert [g.id for g in s1.list_goals(cid)] == [_goal(2).id]  # read-through sees other instance


def test_failed_goal_write_raises_and_changes_nothing(fs_backend, fake_db):
    store = _store(fs_backend)
    cid = next(iter(store.customers))
    store.add_goal(cid, _goal(1))
    fake_db.fail_writes = True
    with pytest.raises(StorageError) as exc:
        store.add_goal(cid, _goal(2))
    assert exc.value.public == persistence.SAVE_FAILED
    assert not isinstance(exc.value, ValueError)  # goals_api maps ValueError to 4xx
    fake_db.fail_writes = False
    assert [g.id for g in store.list_goals(cid)] == [_goal(1).id]
    assert [g.id for g in store.goals[cid]] == [_goal(1).id]


def test_failed_goal_delete_keeps_goal(fs_backend, fake_db):
    store = _store(fs_backend)
    cid = next(iter(store.customers))
    store.add_goal(cid, _goal(1))
    fake_db.fail_writes = True
    with pytest.raises(StorageError):
        store.delete_goal(cid, _goal(1).id)
    fake_db.fail_writes = False
    assert len(store.list_goals(cid)) == 1


def test_consents_merge_write_keeps_other_fields(fs_backend, fake_db):
    store = _store(fs_backend)
    cid = next(iter(store.customers))
    fake_db.docs[f"customers/{cid}"] = {"unrelated": "keep me"}
    new = Consents(use_insurance_data=False, use_other_banks=True, marketing=False)
    store.set_consents(cid, new)
    assert fake_db.docs[f"customers/{cid}"]["unrelated"] == "keep me"
    assert fake_db.docs[f"customers/{cid}"]["consents"] == new.model_dump()
    assert _store(fs_backend).get_customer(cid).consents == new  # reloaded at startup


def test_failed_consent_write_leaves_memory_unchanged(fs_backend, fake_db):
    store = _store(fs_backend)
    cid = next(iter(store.customers))
    before = store.get_customer(cid).consents
    fake_db.fail_writes = True
    with pytest.raises(StorageError):
        store.set_consents(cid, Consents(use_insurance_data=not before.use_insurance_data))
    assert store.get_customer(cid).consents == before


@pytest.mark.parametrize("kind", ["memory", "firestore"])
def test_requests_duplicate_prevention_and_status(kind, use_backend, request):
    backend = use_backend(MemoryBackend() if kind == "memory" else request.getfixturevalue("fs_backend"))
    r1, created1 = requests_store.create("lien", "idle_cash", "x" * 300, {"a": 1})
    r2, created2 = requests_store.create("lien", "idle_cash", "again", {})
    assert created1 and not created2 and r1["id"] == r2["id"]
    assert len(r1["reason"]) == 200
    assert isinstance(r1["created"], str) and datetime.fromisoformat(r1["created"])
    other, created3 = requests_store.create("lien", "car_loan", "x", {})
    assert created3 and other["id"] != r1["id"]

    updated = requests_store.set_status(r1["id"], "in_review")
    assert updated["status"] == "in_review" and isinstance(updated["updated"], str)
    assert requests_store.create("lien", "idle_cash", "still open", {})[1] is False
    requests_store.set_status(r1["id"], "resolved")
    assert {r["id"]: r["status"] for r in requests_store.for_customer("lien")}[r1["id"]] == "resolved"
    assert [r["id"] for r in requests_store.all_requests("resolved")] == [r1["id"]]
    r4, created4 = requests_store.create("lien", "idle_cash", "new one", {})  # lock cleared
    assert created4 and r4["id"] != r1["id"]
    assert requests_store.set_status("AR-NOPE", "resolved") is None
    if kind == "firestore":
        assert "advisor_open/lien__idle_cash" in backend.db.docs


def test_requests_status_persists_across_restart(fs_backend, use_backend):
    use_backend(fs_backend)
    r, _ = requests_store.create("rita", "idle_cash", "x", {})
    requests_store.set_status(r["id"], "in_review")
    fresh = FirestoreBackend("demo-project", client=fs_backend.db)  # a new process
    fresh._fs = FAKE_FS_MODULE
    use_backend(fresh)
    assert requests_store.for_customer("rita")[0]["status"] == "in_review"


def test_requests_cap_per_customer(use_backend):
    use_backend(MemoryBackend())
    for i in range(requests_store.MAX_PER_CUSTOMER):
        requests_store.create("lien", f"m{i}", "x", {})
    with pytest.raises(OverflowError):
        requests_store.create("lien", "one_more", "x", {})


def test_firestore_read_failure_is_storage_error(fs_backend, fake_db):
    fake_db.fail_reads = True
    with pytest.raises(StorageError) as exc:
        fs_backend.all_requests()
    assert exc.value.public == persistence.READ_FAILED


def test_startup_fails_loudly_when_firestore_unreachable(fake_db):
    pytest.importorskip("google.cloud.firestore")
    fake_db.fail_reads = True
    with pytest.raises(RuntimeError, match="startup read failed"):
        FirestoreBackend("demo-project", client=fake_db)


def test_install_handlers_maps_storage_error_to_503():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    persistence.install_handlers(app)

    @app.get("/boom")
    def boom():
        raise StorageError("disk on fire")

    resp = TestClient(app).get("/boom")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Could not save; nothing was changed"}


@pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"),
                    reason="Firestore emulator not available (set FIRESTORE_EMULATOR_HOST, e.g. via "
                           "`gcloud emulators firestore start`); real-Firestore behaviour is not tested")
def test_emulator_roundtrip():  # pragma: no cover - needs the emulator
    backend = FirestoreBackend(os.environ.get("GOOGLE_CLOUD_PROJECT", "demo-test"))
    cid = "emu_" + uuid.uuid4().hex[:8]
    r1, c1 = backend.create_request(cid, "idle_cash", "x", {}, 20)
    r2, c2 = backend.create_request(cid, "idle_cash", "x", {}, 20)
    assert c1 and not c2 and r1["id"] == r2["id"]
    assert backend.set_request_status(r1["id"], "resolved")["status"] == "resolved"
    backend.save_goal(cid, _goal(1).model_dump(mode="json"))
    assert backend.list_goals(cid)[0]["id"] == _goal(1).id
