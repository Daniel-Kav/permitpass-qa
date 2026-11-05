"""Data written through the API is really stored, not just held in the response.

Reads go straight to the database through a new session, so they don't depend on API caching.
"""
from conftest import CITIZEN, OFFICER, VALID_APPLICATION

from permitpass.db import SessionLocal
from permitpass.models import ApplicationRow


def _stored(app_id: str) -> ApplicationRow | None:
    with SessionLocal() as s:
        return s.get(ApplicationRow, app_id)


def test_created_application_is_stored(client):
    r = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN)
    row = _stored(r.json()["id"])
    assert row is not None
    assert (row.business_name, row.kra_pin, row.owner_id) == (
        VALID_APPLICATION["business_name"], VALID_APPLICATION["kra_pin"], "citizen-1",
    )


def test_state_change_and_reason_are_stored(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    client.post(f"/applications/{app_id}/submit", headers=CITIZEN)
    client.post(f"/applications/{app_id}/reject", json={"reason": "Wrong KRA PIN"}, headers=OFFICER)
    row = _stored(app_id)
    assert row.state.value == "rejected"
    assert row.rejection_reason == "Wrong KRA PIN"


def test_refused_transition_changes_nothing(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    assert client.post(f"/applications/{app_id}/approve", headers=OFFICER).status_code == 409
    assert _stored(app_id).state.value == "draft"


def test_rejection_reason_longer_than_500_chars_is_refused(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    client.post(f"/applications/{app_id}/submit", headers=CITIZEN)
    r = client.post(f"/applications/{app_id}/reject", json={"reason": "x" * 501}, headers=OFFICER)
    assert r.status_code == 422
    assert _stored(app_id).state.value == "submitted"
