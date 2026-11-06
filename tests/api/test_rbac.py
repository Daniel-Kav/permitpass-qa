"""Role-based access control, driven by one matrix: role x action -> allowed?

Adding a role or action to the matrix adds coverage automatically.
"""
import pytest

from conftest import ADMIN, CITIZEN, OFFICER, OTHER_CITIZEN, VALID_APPLICATION, act, drive

ROLES = {"citizen": CITIZEN, "officer": OFFICER, "admin": ADMIN}

# action -> (state the application must be in first, roles allowed)
MATRIX = {
    "submit": ("draft", {"citizen"}),
    "pay": ("submitted", {"citizen"}),
    "approve": ("paid", {"officer"}),
    "reject": ("submitted", {"officer"}),
    "issue": ("approved", {"officer"}),
    "revoke": ("issued", {"officer"}),
}
SETUP = {
    "draft": [],
    "submitted": ["submit"],
    "paid": ["submit", "pay"],
    "approved": ["submit", "pay", "approve"],
    "issued": ["submit", "pay", "approve", "issue"],
}


def _prepare(client, state):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    drive(client, app_id, SETUP[state])
    return app_id


@pytest.mark.parametrize("role", list(ROLES))
@pytest.mark.parametrize("action", list(MATRIX))
def test_role_action_matrix(client, role, action):
    state, allowed = MATRIX[action]
    app_id = _prepare(client, state)
    r = act(client, app_id, action, ROLES[role])
    if role in allowed:
        assert r.status_code == 200, r.text
    else:
        assert r.status_code == 403, f"{role} should not be able to {action}"


@pytest.mark.parametrize("role", ["officer", "admin"])
def test_only_citizens_can_apply(client, role):
    r = client.post("/applications", json=VALID_APPLICATION, headers=ROLES[role])
    assert r.status_code == 403


def test_citizen_cannot_read_another_citizens_application(client):
    """IDOR: changing the ID in the URL must not expose someone else's data."""
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    r = client.get(f"/applications/{app_id}", headers=OTHER_CITIZEN)
    assert r.status_code == 404


def test_citizen_cannot_pay_another_citizens_application(client):
    app_id = _prepare(client, "submitted")
    r = act(client, app_id, "pay", OTHER_CITIZEN)
    assert r.status_code == 404


def test_missing_token_rejected(client):
    r = client.post("/applications", json=VALID_APPLICATION)
    assert r.status_code == 401
