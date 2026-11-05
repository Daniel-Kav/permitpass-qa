"""Signed permit certificates and public verification.

Techniques: decision table (signature × revoked × expired), boundary value on expiry, tamper testing.
Traceability: US-10, US-20.
"""
from datetime import datetime, timedelta, timezone

import pytest

from conftest import CITIZEN, OFFICER, OTHER_CITIZEN, VALID_APPLICATION

from permitpass import clock
from permitpass.certificates import VALIDITY
from permitpass.db import SessionLocal
from permitpass.models import CertificateRow

STEPS = [("submit", CITIZEN), ("pay", CITIZEN), ("approve", OFFICER), ("issue", OFFICER)]


def _issued(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    for action, who in STEPS:
        assert client.post(f"/applications/{app_id}/{action}", headers=who).status_code == 200
    cert = client.get(f"/applications/{app_id}/certificate", headers=CITIZEN).json()
    return app_id, cert


def _verify(client, number, sig):
    r = client.get(f"/verify/{number}", params={"sig": sig})  # no auth header: public
    assert r.status_code == 200, r.text
    return r.json()


def _revoke(client, app_id, reason="Business closed"):
    return client.post(f"/applications/{app_id}/revoke", json={"reason": reason}, headers=OFFICER)


@pytest.fixture
def frozen(monkeypatch):
    """Move the app's clock: frozen(days=366) puts 'now' 366 days after the real now."""
    real_now = clock.now

    def _set(**delta):
        monkeypatch.setattr(clock, "now", lambda: real_now() + timedelta(**delta))
    return _set


# ---------- issuing ----------

def test_issuing_creates_a_certificate(client):
    _, cert = _issued(client)
    assert cert["number"].startswith("PP-")
    assert cert["business_name"] == VALID_APPLICATION["business_name"]
    assert cert["verify_url"] == f"/verify/{cert['number']}?sig={cert['signature']}"
    assert cert["revoked_at"] is None


def test_certificate_valid_for_one_year(client):
    _, cert = _issued(client)
    issued, expires = (datetime.fromisoformat(cert[k]) for k in ("issued_at", "expires_at"))
    assert expires - issued == VALIDITY


def test_no_certificate_before_issue(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    assert client.get(f"/applications/{app_id}/certificate", headers=CITIZEN).status_code == 404


def test_other_citizen_cannot_fetch_certificate(client):
    app_id, _ = _issued(client)
    assert client.get(f"/applications/{app_id}/certificate", headers=OTHER_CITIZEN).status_code == 404


def test_numbers_are_unique(client):
    numbers = {_issued(client)[1]["number"] for _ in range(5)}
    assert len(numbers) == 5


# ---------- verification ----------

def test_genuine_certificate_verifies_and_reveals_only_public_fields(client):
    _, cert = _issued(client)
    body = _verify(client, cert["number"], cert["signature"])
    assert body["status"] == "valid"
    assert set(body) == {"status", "number", "business_name", "expires_at"}
    assert VALID_APPLICATION["kra_pin"] not in str(body)


def _flip_last_char(s: str) -> str:
    return s[:-1] + ("A" if s[-1] != "A" else "B")


@pytest.mark.parametrize("tamper", ["flipped_char", "truncated", "empty", "other_certificate", "unknown_number"])
def test_tampered_or_unknown_is_invalid_and_reveals_nothing(client, tamper):
    _, cert = _issued(client)
    _, other = _issued(client)
    number, sig = {
        "flipped_char": (cert["number"], _flip_last_char(cert["signature"])),
        "truncated": (cert["number"], cert["signature"][:-4]),
        "empty": (cert["number"], ""),
        "other_certificate": (cert["number"], other["signature"]),
        "unknown_number": ("PP-2026-DEADBEEF", cert["signature"]),
    }[tamper]
    assert _verify(client, number, sig) == {"status": "invalid"}


def test_changing_stored_data_breaks_the_signature(client):
    """If someone edits the business name in the database, the old signature no longer matches."""
    _, cert = _issued(client)
    with SessionLocal() as s:
        s.get(CertificateRow, cert["number"]).business_name = "Forged Holdings Ltd"
        s.commit()
    assert _verify(client, cert["number"], cert["signature"])["status"] == "invalid"


def test_missing_signature_parameter_is_rejected(client):
    _, cert = _issued(client)
    assert client.get(f"/verify/{cert['number']}").status_code == 422


# ---------- expiry boundary ----------

@pytest.mark.parametrize("offset,expected", [
    (VALIDITY - timedelta(seconds=1), "valid"),     # last second of validity
    (VALIDITY, "expired"),                          # exactly at expires_at: no longer valid
    (VALIDITY + timedelta(seconds=1), "expired"),
])
def test_expiry_boundary(client, monkeypatch, offset, expected):
    t0 = datetime(2026, 11, 6, 9, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(clock, "now", lambda: t0)
    _, cert = _issued(client)
    monkeypatch.setattr(clock, "now", lambda: t0 + offset)
    assert _verify(client, cert["number"], cert["signature"])["status"] == expected


# ---------- decision table: signature × revoked × expired ----------

@pytest.mark.parametrize("sig_ok,revoked,expired,expected", [
    (True,  False, False, "valid"),
    (True,  True,  False, "revoked"),
    (True,  False, True,  "expired"),
    (True,  True,  True,  "revoked"),   # revocation wins
    (False, False, False, "invalid"),
    (False, True,  False, "invalid"),
    (False, False, True,  "invalid"),
    (False, True,  True,  "invalid"),
])
def test_verification_decision_table(client, frozen, sig_ok, revoked, expired, expected):
    app_id, cert = _issued(client)
    if revoked:
        assert _revoke(client, app_id).status_code == 200
    if expired:
        frozen(days=400)
    sig = cert["signature"] if sig_ok else _flip_last_char(cert["signature"])
    assert _verify(client, cert["number"], sig)["status"] == expected


# ---------- revocation ----------

def test_revocation_is_recorded_on_certificate_and_audit(client):
    app_id, cert = _issued(client)
    assert _revoke(client, app_id, "Fraudulent documents").json()["state"] == "revoked"
    after = client.get(f"/applications/{app_id}/certificate", headers=OFFICER).json()
    assert after["revoked_reason"] == "Fraudulent documents" and after["revoked_at"]
    last = client.get(f"/applications/{app_id}/history", headers=OFFICER).json()[-1]
    assert (last["action"], last["reason"]) == ("revoke", "Fraudulent documents")


def test_cannot_revoke_twice(client):
    app_id, _ = _issued(client)
    assert _revoke(client, app_id).status_code == 200
    assert _revoke(client, app_id).status_code == 409


def test_citizen_cannot_revoke_own_certificate(client):
    app_id, _ = _issued(client)
    r = client.post(f"/applications/{app_id}/revoke", json={"reason": "x"}, headers=CITIZEN)
    assert r.status_code == 403
