"""Idempotency-Key on write requests (#47): retries replay the first answer and never run twice.

Traceability: US-30.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import CITIZEN, OFFICER, OTHER_CITIZEN, VALID_APPLICATION, new_application

from permitpass import clock
from permitpass.db import SessionLocal
from permitpass.idempotency import prune
from permitpass.models import IdempotencyKeyRow


def key() -> str:
    return str(uuid.uuid4())


def create(client, k, body=VALID_APPLICATION, who=CITIZEN):
    return client.post("/applications", json=body, headers={**who, "Idempotency-Key": k})


def count(client, who=CITIZEN):
    return client.get("/applications", headers=who).json()["total"]


# ---------- create ----------

def test_retry_after_a_lost_response_replays_and_creates_nothing_new(client, kra):
    k = key()
    first = create(client, k)
    second = create(client, k)          # e.g. the phone never saw the first response and retried
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json() == second.json()
    assert second.headers.get("idempotent-replayed") == "true"
    assert "idempotent-replayed" not in first.headers
    assert count(client) == 1
    assert kra.calls == [VALID_APPLICATION["kra_pin"]]      # KRA asked once, not twice


def test_without_a_key_nothing_changes(client):
    create_plain = lambda: client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN)  # noqa: E731
    assert create_plain().json()["id"] != create_plain().json()["id"]
    assert count(client) == 2


def test_same_key_for_a_different_request_is_refused(client):
    k = key()
    create(client, k)
    r = create(client, k, {**VALID_APPLICATION, "business_name": "Something Else"})
    assert (r.status_code, r.json()["detail"]) == (422, "Idempotency-Key was already used for a different request")
    assert count(client) == 1


def test_keys_are_per_user(client):
    """Another user sending the same key gets their own application, never the first user's data."""
    k = key()
    mine = create(client, k).json()
    theirs = create(client, k, who=OTHER_CITIZEN)
    assert theirs.status_code == 201 and theirs.json()["id"] != mine["id"]
    assert theirs.json()["owner_id"] == "citizen-2"


@pytest.mark.parametrize("bad", ["short", "has spaces in it", "x" * 65, "semi;colon-key", ""])
def test_malformed_keys_are_refused(client, bad):
    r = create(client, bad)
    assert r.status_code == 422
    assert count(client) == 0


@pytest.mark.parametrize("good", ["abcdefgh", "x" * 64, str(uuid.uuid4()), "offline_2026-11-08_0001"])
def test_well_formed_keys_are_accepted(client, good):
    assert create(client, good).status_code == 201


# ---------- refusals are remembered, outages are not ----------

def test_a_refusal_is_replayed_not_rerun(client, kra):
    k = key()
    r1 = create(client, k, {**VALID_APPLICATION, "kra_pin": "A999999999Z"})     # KRA: not registered
    r2 = create(client, k, {**VALID_APPLICATION, "kra_pin": "A999999999Z"})
    assert (r1.status_code, r2.status_code) == (422, 422)
    assert r2.json() == {"detail": "KRA PIN is not registered"}
    assert r2.headers.get("idempotent-replayed") == "true"
    assert len(kra.calls) == 1


def test_an_outage_releases_the_key_so_the_retry_really_runs(client, kra):
    k = key()
    original = kra.validate_pin
    outage = {"on": True}

    def flaky(pin):
        if outage["on"]:
            from permitpass.integrations.kra import KraUnavailable
            raise KraUnavailable("down")
        return original(pin)

    kra.validate_pin = flaky
    assert create(client, k).status_code == 503
    outage["on"] = False
    retry = create(client, k)
    assert retry.status_code == 201 and "idempotent-replayed" not in retry.headers
    assert count(client) == 1


# ---------- actions, above all pay ----------

def _pay(client, app_id, k, phone="0712345678"):
    return client.post(f"/applications/{app_id}/pay", json={"phone": phone}, headers={**CITIZEN, "Idempotency-Key": k})


def test_pay_retried_sends_one_mpesa_prompt(client, mpesa):
    app_id = new_application(client, ["submit"])
    k = key()
    first, second = _pay(client, app_id, k), _pay(client, app_id, k)
    assert first.json() == second.json() and second.json()["state"] == "payment_pending"
    assert len(mpesa.pushes) == 1, "a retried pay must not prompt the citizen's phone twice"
    assert len(client.get(f"/applications/{app_id}/payments", headers=CITIZEN).json()) == 1


def test_pay_without_a_key_retried_is_refused_by_the_state_machine(client, mpesa):
    """The older safety net still holds: a second pay while pending is a 409, never a second push."""
    app_id = new_application(client, ["submit"])
    client.post(f"/applications/{app_id}/pay", json={"phone": "0712345678"}, headers=CITIZEN)
    r = client.post(f"/applications/{app_id}/pay", json={"phone": "0712345678"}, headers=CITIZEN)
    assert r.status_code == 409 and len(mpesa.pushes) == 1


def test_mpesa_outage_on_pay_releases_the_key(client, mpesa):
    app_id = new_application(client, ["submit"])
    k = key()
    original = mpesa.stk_push
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            from permitpass.integrations.mpesa import MpesaUnavailable
            raise MpesaUnavailable("down")
        return original(*a, **kw)

    mpesa.stk_push = flaky
    assert _pay(client, app_id, k).status_code == 503
    assert _pay(client, app_id, k).status_code == 200
    assert len(mpesa.pushes) == 1


def test_a_refused_action_is_replayed(client):
    app_id = new_application(client)                     # draft
    k = key()
    hdr = {**OFFICER, "Idempotency-Key": k}
    r1 = client.post(f"/applications/{app_id}/approve", headers=hdr)
    r2 = client.post(f"/applications/{app_id}/approve", headers=hdr)
    assert (r1.status_code, r2.status_code) == (409, 409)
    assert r2.headers.get("idempotent-replayed") == "true"


def test_same_key_on_another_application_is_a_different_request(client):
    a, b = new_application(client), new_application(client)
    k = key()
    assert client.post(f"/applications/{a}/submit", headers={**CITIZEN, "Idempotency-Key": k}).status_code == 200
    r = client.post(f"/applications/{b}/submit", headers={**CITIZEN, "Idempotency-Key": k})
    assert r.status_code == 422                          # key reuse across different requests is a client bug


# ---------- expiry ----------

def test_keys_expire_after_24_hours(client, monkeypatch):
    t0 = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(clock, "now", lambda: t0)
    k = key()
    first = create(client, k).json()
    monkeypatch.setattr(clock, "now", lambda: t0 + timedelta(hours=23, minutes=59))
    assert create(client, k).json()["id"] == first["id"]            # still replayed
    monkeypatch.setattr(clock, "now", lambda: t0 + timedelta(hours=24, seconds=1))
    assert create(client, k).json()["id"] != first["id"]            # expired: runs again
    with SessionLocal() as db:
        monkeypatch.setattr(clock, "now", lambda: t0 + timedelta(hours=49))
        assert prune(db) == 1
        assert db.query(IdempotencyKeyRow).count() == 0
