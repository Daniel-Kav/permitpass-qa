"""KRA PIN verification when applying. Unit level: the app talks to the fake KRA client.

Test-data rules (same as the WireMock stubs): digits 999999999 not registered, 666666666 inactive,
888888888 SOAP fault, 777777777 timeout; anything else is active. Traceability: US-09.
"""
import pytest

from conftest import CITIZEN, OFFICER


def _apply(client, pin, name="Duka La Mama"):
    return client.post("/applications", json={"business_name": name, "kra_pin": pin}, headers=CITIZEN)


def _count(client):
    return client.get("/applications", headers=OFFICER).json()["total"]


def test_registered_pin_is_accepted_and_verification_is_audited(client, kra):
    r = _apply(client, "A123456789Z")
    assert r.status_code == 201
    assert kra.calls == ["A123456789Z"]
    first = client.get(f"/applications/{r.json()['id']}/history", headers=CITIZEN).json()[0]
    assert first["reason"] == "KRA PIN verified: Active"


@pytest.mark.parametrize("pin,message", [
    ("A999999999Z", "KRA PIN is not registered"),
    ("P666666666Q", "KRA PIN is not active"),
])
def test_unregistered_or_inactive_pin_is_refused(client, pin, message):
    r = _apply(client, pin)
    assert (r.status_code, r.json()["detail"]) == (422, message)
    assert _count(client) == 0


@pytest.mark.parametrize("pin", ["A888888888Z", "A777777777Z"], ids=["soap-fault", "timeout"])
def test_kra_down_fails_closed(client, pin):
    """If KRA can't answer, nothing is stored and the citizen is told to retry."""
    r = _apply(client, pin)
    assert r.status_code == 503
    assert r.json()["detail"] == "KRA service unavailable, please try again later"
    assert r.headers["retry-after"] == "30"
    assert _count(client) == 0


@pytest.mark.parametrize("pin", ["B123456789Z", "A12345678Z", ""])
def test_malformed_pin_is_rejected_before_calling_kra(client, kra, pin):
    assert _apply(client, pin).status_code == 422
    assert kra.calls == []


def test_staff_cannot_trigger_kra_lookups(client, kra):
    """Only citizens may apply, and the role check happens before any KRA call."""
    r = client.post("/applications", json={"business_name": "Duka", "kra_pin": "A123456789Z"}, headers=OFFICER)
    assert r.status_code == 403
    assert kra.calls == []
