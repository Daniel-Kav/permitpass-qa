"""Payments that never get a callback (#30): STK query after 2 min, expiry after 10 min, and late answers.

Phone rules (fake == stubs): 0700000000 never answers and the query keeps saying "processing";
0700000003 no callback, query says success; 0700000004 no callback, query says cancelled.
"""
from datetime import datetime, timedelta, timezone

import pytest

from conftest import ADMIN, CITIZEN, OFFICER, act, deliver, new_application, settle

from permitpass import clock, config
from permitpass.integrations.fakes import callback_body

T0 = datetime(2026, 11, 7, 9, 0, 0, tzinfo=timezone.utc)
QUERY_AFTER, EXPIRE_AFTER = config.PAYMENT_QUERY_AFTER_SECONDS, config.PAYMENT_EXPIRE_AFTER_SECONDS


@pytest.fixture
def at(monkeypatch):
    """at(seconds) sets the app clock to T0 + seconds."""
    def _set(seconds: float = 0):
        monkeypatch.setattr(clock, "now", lambda: T0 + timedelta(seconds=seconds))
    _set(0)
    return _set


def _sweep(client, who=ADMIN):
    return client.post("/admin/payments/sweep", headers=who)


def _app(client, app_id):
    return client.get(f"/applications/{app_id}", headers=CITIZEN).json()


def _payments(client, app_id):
    return client.get(f"/applications/{app_id}/payments", headers=CITIZEN).json()


def _pending(client, phone):
    app_id = new_application(client, ["submit"])
    assert act(client, app_id, "pay", phone=phone).status_code == 200
    return app_id


# ---------- when the sweep looks at a payment ----------

@pytest.mark.parametrize("age,checked", [(QUERY_AFTER - 1, 0), (QUERY_AFTER, 1)])
def test_query_boundary(client, mpesa, at, age, checked):
    _pending(client, "0700000000")
    at(age)
    assert _sweep(client).json()["checked"] == checked
    assert len(mpesa.queries) == checked


@pytest.mark.parametrize("age,expected", [(EXPIRE_AFTER - 1, "payment_pending"), (EXPIRE_AFTER, "submitted")])
def test_expiry_boundary(client, at, age, expected):
    app_id = _pending(client, "0700000000")
    at(age)
    _sweep(client)
    assert _app(client, app_id)["state"] == expected


# ---------- outcomes ----------

def test_still_processing_stays_pending(client, at):
    app_id = _pending(client, "0700000000")
    at(QUERY_AFTER + 30)
    assert _sweep(client).json()["outcomes"] == {"still pending": 1}
    assert _app(client, app_id)["state"] == "payment_pending"


def test_expired_payment_lets_the_citizen_retry(client, at):
    app_id = _pending(client, "0700000000")
    at(EXPIRE_AFTER)
    assert _sweep(client).json()["outcomes"] == {"expired": 1}
    app = _app(client, app_id)
    assert app["state"] == "submitted"
    assert app["payment_note"].startswith("M-Pesa did not confirm this payment within 10 minutes")
    assert _payments(client, app_id)[0]["status"] == "expired"
    assert act(client, app_id, "pay").status_code == 200          # can pay again


def test_query_success_marks_paid_without_a_receipt(client, at):
    app_id = _pending(client, "0700000003")
    at(QUERY_AFTER)
    assert _sweep(client).json()["outcomes"] == {"succeeded": 1}
    assert _app(client, app_id)["state"] == "paid"
    [p] = _payments(client, app_id)
    assert (p["status"], p["mpesa_receipt"]) == ("succeeded", None)
    last = client.get(f"/applications/{app_id}/history", headers=CITIZEN).json()[-1]
    assert "confirmed by STK query" in last["reason"]


def test_query_cancelled_returns_to_submitted(client, at):
    app_id = _pending(client, "0700000004")
    at(QUERY_AFTER)
    _sweep(client)
    app = _app(client, app_id)
    assert (app["state"], app["payment_note"]) == ("submitted", "Payment failed: Request cancelled by user (M-Pesa code 1032)")


def test_query_outage_waits_then_expires(client, mpesa, at):
    mpesa.query_unavailable = True
    app_id = _pending(client, "0700000003")
    at(QUERY_AFTER)
    assert _sweep(client).json()["outcomes"] == {"still pending": 1}
    at(EXPIRE_AFTER)
    assert _sweep(client).json()["outcomes"] == {"expired": 1}
    assert _app(client, app_id)["state"] == "submitted"


def test_sweep_is_idempotent(client, at):
    _pending(client, "0700000000")
    at(EXPIRE_AFTER)
    assert _sweep(client).json()["checked"] == 1
    assert _sweep(client).json()["checked"] == 0


def test_payments_with_callbacks_are_never_swept(client, at):
    new_application(client, ["submit", "pay"])                    # normal phone: callback delivered
    at(EXPIRE_AFTER * 2)
    assert _sweep(client).json()["checked"] == 0


# ---------- late answers after expiry: money must never be lost or taken twice ----------

def _checkout(mpesa):
    return f"ws_CO_{mpesa.pushes[-1]['account_ref']}"


def test_late_success_after_expiry_still_pays(client, mpesa, at):
    app_id = _pending(client, "0700000000")
    checkout = _checkout(mpesa)
    at(EXPIRE_AFTER)
    _sweep(client)
    r = deliver(client, callback_body(checkout, 2500, "254700000000", None, receipt="LATE123456"))
    assert r.json()["ResultDesc"] == "Accepted"
    assert _app(client, app_id)["state"] == "paid"
    last = client.get(f"/applications/{app_id}/history", headers=CITIZEN).json()[-1]
    assert "arrived after expiry" in last["reason"]


def test_late_failure_after_expiry_changes_nothing(client, mpesa, at):
    app_id = _pending(client, "0700000000")
    checkout = _checkout(mpesa)
    at(EXPIRE_AFTER)
    _sweep(client)
    r = deliver(client, callback_body(checkout, 2500, "254700000000", "cancelled", receipt="X"))
    assert r.json()["ResultDesc"] == "Already processed"
    assert _payments(client, app_id)[0]["status"] == "expired"


def test_double_payment_is_flagged_for_refund(client, mpesa, at):
    """Citizen retries after expiry and pays; then the first attempt's success arrives late."""
    app_id = _pending(client, "0700000000")
    first = _checkout(mpesa)
    at(EXPIRE_AFTER)
    _sweep(client)
    act(client, app_id, "pay")
    settle(client)                                                 # second attempt succeeds
    assert _app(client, app_id)["state"] == "paid"
    deliver(client, callback_body(first, 2500, "254700000000", None, receipt="LATE999999"))
    statuses = sorted(p["status"] for p in _payments(client, app_id))
    assert statuses == ["refund_due", "succeeded"]
    assert _app(client, app_id)["state"] == "paid"                 # unchanged
    due = client.get("/admin/payments", params={"status": "refund_due"}, headers=ADMIN).json()
    assert [(d["application_id"], d["amount"], d["phone"]) for d in due] == [(app_id, 2500, "254700000000")]
    events = [e["action"] for e in client.get(f"/applications/{app_id}/history", headers=CITIZEN).json()]
    assert events[-1] == "payment_refund_due"


# ---------- access ----------

@pytest.mark.parametrize("who", [CITIZEN, OFFICER])
def test_only_admins_can_sweep_or_see_refunds(client, who):
    assert _sweep(client, who).status_code == 403
    assert client.get("/admin/payments", headers=who).status_code == 403


def test_sweep_needs_login(client):
    assert client.post("/admin/payments/sweep").status_code == 401


def test_background_sweeper_runs_on_its_own(client, at):
    """The sweeper thread started with the app does the same job without anyone calling the endpoint."""
    import time

    from permitpass.payments import BackgroundSweeper

    app_id = _pending(client, "0700000000")
    at(EXPIRE_AFTER)
    sweeper = BackgroundSweeper(interval=1)
    sweeper.start()
    try:
        for _ in range(40):
            if _app(client, app_id)["state"] == "submitted":
                break
            time.sleep(0.1)
    finally:
        sweeper.stop()
    assert _app(client, app_id)["state"] == "submitted"
