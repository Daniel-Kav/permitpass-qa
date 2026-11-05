"""Input validation using equivalence partitioning and boundary values.

KRA PIN format: one letter (A or P), nine digits, one letter. Business name: 2-120 characters.
"""
import pytest

from conftest import CITIZEN


@pytest.mark.parametrize("pin", ["A123456789Z", "P000000000A"])
def test_valid_kra_pins_accepted(client, pin):
    r = client.post("/applications", json={"business_name": "Duka", "kra_pin": pin}, headers=CITIZEN)
    assert r.status_code == 201


@pytest.mark.parametrize("pin", [
    "B123456789Z",   # wrong leading letter
    "A12345678Z",    # 8 digits (boundary - 1)
    "A1234567890Z",  # 10 digits (boundary + 1)
    "A123456789",    # missing trailing letter
    "a123456789z",   # lowercase
    "",              # empty
])
def test_invalid_kra_pins_rejected(client, pin):
    r = client.post("/applications", json={"business_name": "Duka", "kra_pin": pin}, headers=CITIZEN)
    assert r.status_code == 422


@pytest.mark.parametrize("length,expected", [(1, 422), (2, 201), (120, 201), (121, 422)])
def test_business_name_length_boundaries(client, length, expected):
    r = client.post("/applications", json={"business_name": "x" * length, "kra_pin": "A123456789Z"}, headers=CITIZEN)
    assert r.status_code == expected


def test_new_application_has_correct_fee_and_state(client):
    r = client.post("/applications", json={"business_name": "Duka", "kra_pin": "A123456789Z"}, headers=CITIZEN)
    body = r.json()
    assert body["state"] == "draft"
    assert body["fee_kes"] == 2500
