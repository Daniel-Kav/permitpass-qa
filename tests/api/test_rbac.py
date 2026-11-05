"""Role-based access control, driven by one matrix: role x action -> allowed?

Adding a role or action to the matrix adds coverage automatically.
"""
import pytest

from conftest import ADMIN, CITIZEN, OFFICER, OTHER_CITIZEN, VALID_APPLICATION

ROLES = {"citizen": CITIZEN, "officer": OFFICER, "admin": ADMIN}

# action -> (state the application must be in first, roles allowed)
MATRIX = {
    "submit": ("draft", {"citizen"}),
    "pay": ("submitted", {"citizen"}),
    "approve": ("paid", {"officer"}),
    "reject": ("submitted", {"officer"}),
    "issue": ("approved", {"officer"}),
}
SETUP = {
    "draft": [],
    "submitted": [("submit", CITIZEN)],
    "paid": [("submit", CITIZEN), ("pay", CITIZEN)],
    "approved": [("submit", CITIZEN), ("pay", CITIZEN), ("approve", OFFICER)],
}


def _prepare(client, state):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    for action, who in SETUP[state]:
        assert client.post(f"/applications/{app_id}/{action}", headers=who).status_code == 200
    return app_id


@pytest.mark.parametrize("role", list(ROLES))
@pytest.mark.parametrize("action", list(MATRIX))
def test_role_action_matrix(client, role, action):
    state, allowed = MATRIX[action]
    app_id = _prepare(client, state)
    body = {"reason": "Test"} if action == "reject" else None
    r = client.post(f"/applications/{app_id}/{action}", json=body, headers=ROLES[role])
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
    r = client.post(f"/applications/{app_id}/pay", headers=OTHER_CITIZEN)
    assert r.status_code == 404


def test_missing_token_rejected(client):
    r = client.post("/applications", json=VALID_APPLICATION)
    assert r.status_code == 401
