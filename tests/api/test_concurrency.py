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
