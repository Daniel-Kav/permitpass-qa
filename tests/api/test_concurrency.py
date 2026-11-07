"""Concurrent officers acting on the same application. Regression for #34 (found by the k6 load test).

Exactly one of N simultaneous requests may win; the rest must get 409, with one audit event and no 500s.
Needs PostgreSQL (real row locking); SQLite serialises the whole database, so the race can't happen there.
"""
import os
import threading

import pytest
from fastapi.testclient import TestClient

from conftest import OFFICER, new_application

from permitpass.main import app

pytestmark = pytest.mark.skipif(not os.environ["DATABASE_URL"].startswith("postgresql"),
                                reason="row-locking race needs PostgreSQL")
PARALLEL, ROUNDS = 4, 10


def _race(app_id: str, action: str) -> list[int]:
    """Fire PARALLEL identical requests at the same instant; return their status codes."""
    body = {"reason": "Race"} if action == "reject" else None
    barrier, codes = threading.Barrier(PARALLEL), []

    def worker():
        c = TestClient(app, raise_server_exceptions=False)   # one client per thread; a 500 is a result, not a crash
        barrier.wait()
        codes.append(c.post(f"/applications/{app_id}/{action}", json=body, headers=OFFICER).status_code)

    threads = [threading.Thread(target=worker) for _ in range(PARALLEL)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return codes


@pytest.mark.parametrize("action,steps", [
    ("approve", ["submit", "pay"]),
    ("issue", ["submit", "pay", "approve"]),
    ("reject", ["submit", "pay"]),
])
def test_only_one_concurrent_transition_wins(client, action, steps):
    for _ in range(ROUNDS):
        app_id = new_application(client, steps)
        codes = _race(app_id, action)
        assert sorted(codes) == [200] + [409] * (PARALLEL - 1), f"{action}: {codes}"
        events = [e for e in client.get(f"/applications/{app_id}/history", headers=OFFICER).json() if e["action"] == action]
        assert len(events) == 1, f"{action}: {len(events)} audit events for one application"


def test_concurrent_sweeps_process_each_payment_once(client, monkeypatch):
    """Two workers sweeping at the same moment (SKIP LOCKED): every stuck payment expires exactly once (#30)."""
    from datetime import timedelta

    from conftest import ADMIN, act

    from permitpass import clock, config

    real_now = clock.now
    ids = []
    for _ in range(6):
        app_id = new_application(client, ["submit"])
        act(client, app_id, "pay", phone="0700000000")       # never answers
        ids.append(app_id)
    monkeypatch.setattr(clock, "now", lambda: real_now() + timedelta(seconds=config.PAYMENT_EXPIRE_AFTER_SECONDS + 1))

    barrier, results = threading.Barrier(PARALLEL), []

    def worker():
        c = TestClient(app, raise_server_exceptions=False)
        barrier.wait()
        results.append(c.post("/admin/payments/sweep", headers=ADMIN).json())

    threads = [threading.Thread(target=worker) for _ in range(PARALLEL)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(r["outcomes"].get("expired", 0) for r in results) == 6
    for app_id in ids:
        events = [e["action"] for e in client.get(f"/applications/{app_id}/history", headers=OFFICER).json()]
        assert events.count("payment_failed") == 1


def test_concurrent_requests_with_one_idempotency_key_create_one_application(client):
    """Four copies of one create, same key, at the same instant: exactly one runs (#47)."""
    import uuid as _uuid

    from conftest import CITIZEN, VALID_APPLICATION

    for _ in range(ROUNDS):
        k = str(_uuid.uuid4())
        barrier, results = threading.Barrier(PARALLEL), []

        def worker():
            c = TestClient(app, raise_server_exceptions=False)
            barrier.wait()
            r = c.post("/applications", json=VALID_APPLICATION, headers={**CITIZEN, "Idempotency-Key": k})
            results.append((r.status_code, r.json().get("id")))

        threads = [threading.Thread(target=worker) for _ in range(PARALLEL)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        codes = sorted(c for c, _ in results)
        assert set(codes) <= {201, 409}, codes             # 201 (ran or replayed) or 409 (in progress, retry)
        assert len({i for c, i in results if c == 201}) == 1, results
    total = client.get("/applications", headers=CITIZEN).json()["total"]
    assert total == ROUNDS
