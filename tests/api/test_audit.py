"""Audit trail: every change is recorded once, in order, by the right actor. Refused changes leave no trace.

Traceability: US-18.
"""
import pytest

from conftest import ADMIN, CITIZEN, OFFICER, OTHER_CITIZEN, VALID_APPLICATION


def _new(client):
    return client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]


def _history(client, app_id, headers=CITIZEN):
    return client.get(f"/applications/{app_id}/history", headers=headers)


def test_full_lifecycle_is_recorded_in_order(client):
    app_id = _new(client)
    for action, who in [("submit", CITIZEN), ("pay", CITIZEN), ("approve", OFFICER), ("issue", OFFICER)]:
        assert client.post(f"/applications/{app_id}/{action}", headers=who).status_code == 200
    events = _history(client, app_id).json()
    assert [(e["action"], e["from_state"], e["to_state"], e["actor_id"]) for e in events] == [
        ("create", None, "draft", "citizen-1"),
        ("submit", "draft", "submitted", "citizen-1"),
        ("pay", "submitted", "paid", "citizen-1"),
        ("approve", "paid", "approved", "officer-1"),
        ("issue", "approved", "issued", "officer-1"),
    ]
    times = [e["at"] for e in events]
    assert times == sorted(times)


def test_rejection_reason_is_recorded(client):
    app_id = _new(client)
    client.post(f"/applications/{app_id}/submit", headers=CITIZEN)
    client.post(f"/applications/{app_id}/reject", json={"reason": "Blurred ID copy"}, headers=OFFICER)
    last = _history(client, app_id).json()[-1]
    assert (last["action"], last["reason"], last["actor_id"]) == ("reject", "Blurred ID copy", "officer-1")


@pytest.mark.parametrize("attempt", [
    ("approve", OFFICER, None),          # illegal transition (409)
    ("submit", OFFICER, None),           # wrong role (403)
    ("submit", OTHER_CITIZEN, None),     # someone else's application (404)
])
def test_refused_actions_write_no_event(client, attempt):
    action, who, body = attempt
    app_id = _new(client)
    assert client.post(f"/applications/{app_id}/{action}", json=body, headers=who).status_code >= 400
    assert len(_history(client, app_id).json()) == 1  # only "create"


def test_reject_without_reason_writes_no_event(client):
    app_id = _new(client)
    client.post(f"/applications/{app_id}/submit", headers=CITIZEN)
    assert client.post(f"/applications/{app_id}/reject", json={}, headers=OFFICER).status_code == 422
    assert [e["action"] for e in _history(client, app_id).json()] == ["create", "submit"]


@pytest.mark.parametrize("who,expected", [(CITIZEN, 200), (OFFICER, 200), (ADMIN, 200), (OTHER_CITIZEN, 404)])
def test_history_visibility(client, who, expected):
    assert _history(client, _new(client), who).status_code == expected


def test_history_of_unknown_application_is_404(client):
    assert _history(client, "00000000-0000-0000-0000-000000000000", OFFICER).status_code == 404
