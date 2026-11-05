"""Listing applications: ownership filtering, state filter and pagination boundaries.

Traceability: US-19.
"""
import pytest

from conftest import ADMIN, CITIZEN, OFFICER, OTHER_CITIZEN, VALID_APPLICATION


def _make(client, n, who=CITIZEN, submit=False):
    ids = []
    for i in range(n):
        app_id = client.post("/applications", json={**VALID_APPLICATION, "business_name": f"Duka {i}"}, headers=who).json()["id"]
        if submit:
            client.post(f"/applications/{app_id}/submit", headers=who)
        ids.append(app_id)
    return ids


def _list(client, who=OFFICER, **params):
    return client.get("/applications", params=params, headers=who)


def test_citizen_sees_only_own_applications(client):
    mine = set(_make(client, 3))
    _make(client, 2, who=OTHER_CITIZEN)
    body = _list(client, CITIZEN).json()
    assert body["total"] == 3
    assert {a["id"] for a in body["items"]} == mine


@pytest.mark.parametrize("who", [OFFICER, ADMIN])
def test_staff_see_all_applications(client, who):
    _make(client, 3)
    _make(client, 2, who=OTHER_CITIZEN)
    assert _list(client, who).json()["total"] == 5


def test_state_filter(client):
    _make(client, 2)
    submitted = set(_make(client, 3, submit=True))
    body = _list(client, state="submitted").json()
    assert body["total"] == 3
    assert {a["id"] for a in body["items"]} == submitted
    assert _list(client, state="issued").json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_unknown_state_filter_rejected(client):
    assert _list(client, state="pending").status_code == 422


def test_newest_first(client):
    ids = _make(client, 3)
    assert [a["id"] for a in _list(client).json()["items"]] == list(reversed(ids))


def test_pages_cover_everything_exactly_once(client):
    ids = set(_make(client, 7))
    seen = []
    for offset in range(0, 9, 3):
        seen += [a["id"] for a in _list(client, limit=3, offset=offset).json()["items"]]
    assert len(seen) == 7 and set(seen) == ids


@pytest.mark.parametrize("limit,status", [(0, 422), (1, 200), (100, 200), (101, 422), (-1, 422)])
def test_limit_boundaries(client, limit, status):
    assert _list(client, limit=limit).status_code == status


@pytest.mark.parametrize("offset,status", [(-1, 422), (0, 200)])
def test_offset_boundaries(client, offset, status):
    assert _list(client, offset=offset).status_code == status


def test_offset_past_the_end_returns_empty_page(client):
    _make(client, 2)
    body = _list(client, offset=50).json()
    assert body["items"] == [] and body["total"] == 2


def test_listing_requires_login(client):
    assert client.get("/applications").status_code == 401
