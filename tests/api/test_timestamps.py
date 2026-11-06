"""Regression for #13: every timestamp the API returns carries an explicit UTC offset.

Without an offset, browsers read the value as local time and show the wrong time.
"""
from datetime import datetime, timedelta

import pytest

from conftest import CITIZEN, OFFICER, VALID_APPLICATION, drive


@pytest.fixture
def issued(client):
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    drive(client, app_id, ["submit", "pay", "approve", "issue"])
    client.post(f"/applications/{app_id}/revoke", json={"reason": "Closed"}, headers=OFFICER)
    return app_id


def _timestamps(client, app_id):
    app = client.get(f"/applications/{app_id}", headers=CITIZEN).json()
    listed = client.get("/applications", headers=CITIZEN).json()["items"][0]
    history = client.get(f"/applications/{app_id}/history", headers=CITIZEN).json()
    cert = client.get(f"/applications/{app_id}/certificate", headers=CITIZEN).json()
    payment = client.get(f"/applications/{app_id}/payments", headers=CITIZEN).json()[0]
    return {
        "payment.created_at": payment["created_at"],
        "payment.completed_at": payment["completed_at"],
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
