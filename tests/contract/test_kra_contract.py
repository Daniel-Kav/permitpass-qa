"""KRA PIN Checker contract: real HttpKraClient ↔ WireMock stubs (mocks/mappings/kra-*.json)."""
import pytest

from permitpass.integrations.fakes import FakeKraClient
from permitpass.integrations.kra import HttpKraClient, KraUnavailable, PinStatus


@pytest.fixture
def kra(base_url):
    return HttpKraClient(base_url, timeout_seconds=3.0)


@pytest.mark.parametrize("pin,status", [
    ("A123456789Z", PinStatus.active),
    ("P051234567K", PinStatus.active),
    ("A999999999Z", PinStatus.not_found),
    ("P666666666Q", PinStatus.inactive),
])
def test_status_answers(wiremock, kra, pin, status):
    result = kra.validate_pin(pin)
    assert (result.pin, result.status) == (pin, status)


@pytest.mark.parametrize("pin", ["A888888888Z", "A777777777Z"], ids=["soap-fault", "slower-than-timeout"])
def test_outages(wiremock, kra, pin):
    with pytest.raises(KraUnavailable):
        kra.validate_pin(pin)


def test_no_request_hits_the_contract_violation_stub(wiremock, kra):
    kra.validate_pin("A123456789Z")
    served = wiremock.get("/requests").json()["requests"]
    assert served and all(r["stubMapping"].get("name", "").startswith("KRA:") and "catch-all" not in r["stubMapping"]["name"]
                          for r in served)


def test_a_malformed_request_is_caught_by_the_stubs(wiremock, base_url):
    """Guard: proves the stubs really enforce the contract (wrong SOAPAction → 400), so the tests above mean something."""
    import httpx
    r = httpx.post(f"{base_url}/kra/PinChecker", content=b"<x/>", headers={"Content-Type": "text/xml", "SOAPAction": "wrong"})
    assert r.status_code == 400 and "CONTRACT VIOLATION" in r.text
    wiremock.delete("/requests")   # this unmatched-by-design request must not fail the fixture


@pytest.mark.parametrize("pin", ["A123456789Z", "A999999999Z", "P666666666Q"])
def test_fake_and_stubs_agree(wiremock, kra, pin):
    """The unit-test fake must behave exactly like the stubs, or unit tests would prove the wrong thing."""
    assert FakeKraClient().validate_pin(pin).status == kra.validate_pin(pin).status
