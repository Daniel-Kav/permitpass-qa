"""Permit lifecycle as a state machine: legal transitions succeed, every illegal one is refused.

Technique: state-transition testing (ISTQB). Traceability: US-01..US-04 in docs/traceability.csv.
"""
import pytest

from conftest import CITIZEN, OFFICER, VALID_APPLICATION

ALL_ACTIONS = ["submit", "pay", "approve", "reject", "issue", "revoke"]
ACTOR = {"submit": CITIZEN, "pay": CITIZEN, "approve": OFFICER, "reject": OFFICER, "issue": OFFICER, "revoke": OFFICER}

# How to drive a fresh application into each state
PATH_TO = {
    "draft": [],
    "submitted": ["submit"],
    "paid": ["submit", "pay"],
    "approved": ["submit", "pay", "approve"],
    "issued": ["submit", "pay", "approve", "issue"],
    "rejected": ["submit", "reject"],
    "revoked": ["submit", "pay", "approve", "issue", "revoke"],
}
LEGAL = {
    ("draft", "submit"), ("submitted", "pay"), ("paid", "approve"),
    ("submitted", "reject"), ("paid", "reject"), ("approved", "issue"), ("issued", "revoke"),
}


def _new_app(client):
    r = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _do(client, app_id, action):
    body = {"reason": "Incomplete documents"} if action in ("reject", "revoke") else None
    return client.post(f"/applications/{app_id}/{action}", json=body, headers=ACTOR[action])


def _drive(client, state):
    app_id = _new_app(client)
    for step in PATH_TO[state]:
        assert _do(client, app_id, step).status_code == 200
    return app_id


def test_happy_path_reaches_issued(client):
    app_id = _drive(client, "issued")
    r = client.get(f"/applications/{app_id}", headers=CITIZEN)
    assert r.json()["state"] == "issued"


@pytest.mark.parametrize("state", list(PATH_TO))
@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_every_transition(client, state, action):
    app_id = _drive(client, state)
    r = _do(client, app_id, action)
    if (state, action) in LEGAL:
        assert r.status_code == 200, r.text
    else:
        assert r.status_code == 409, f"{action} from {state} should be refused, got {r.status_code}"


def test_reject_requires_reason(client):
    app_id = _drive(client, "submitted")
    r = client.post(f"/applications/{app_id}/reject", json={}, headers=OFFICER)
    assert r.status_code == 422


def test_revoke_requires_reason(client):
    app_id = _drive(client, "issued")
    r = client.post(f"/applications/{app_id}/revoke", json={}, headers=OFFICER)
    assert r.status_code == 422
