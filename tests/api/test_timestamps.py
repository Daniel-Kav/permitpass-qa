"""Regression for #13: every timestamp the API returns carries an explicit UTC offset.

Without an offset, browsers read the value as local time and show the wrong time.
"""
from datetime import datetime, timedelta

import pytest

from conftest import CITIZEN, OFFICER, VALID_APPLICATION


@pytest.fixture
def issued(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    for action, who in [("submit", CITIZEN), ("pay", CITIZEN), ("approve", OFFICER), ("issue", OFFICER)]:
        client.post(f"/applications/{app_id}/{action}", headers=who)
    client.post(f"/applications/{app_id}/revoke", json={"reason": "Closed"}, headers=OFFICER)
    return app_id


def _timestamps(client, app_id):
    app = client.get(f"/applications/{app_id}", headers=CITIZEN).json()
    listed = client.get("/applications", headers=CITIZEN).json()["items"][0]
    history = client.get(f"/applications/{app_id}/history", headers=CITIZEN).json()
    cert = client.get(f"/applications/{app_id}/certificate", headers=CITIZEN).json()
    return {
        "application.created_at": app["created_at"],
        "list.created_at": listed["created_at"],
        **{f"history[{i}].at": e["at"] for i, e in enumerate(history)},
        "certificate.issued_at": cert["issued_at"],
        "certificate.expires_at": cert["expires_at"],
        "certificate.revoked_at": cert["revoked_at"],
    }


def test_every_timestamp_has_utc_offset(client, issued):
    missing = {k: v for k, v in _timestamps(client, issued).items() if datetime.fromisoformat(v).utcoffset() != timedelta(0)}
    assert not missing, f"timestamps without a UTC offset: {missing}"
