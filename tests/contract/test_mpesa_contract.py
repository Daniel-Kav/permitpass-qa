"""M-Pesa Daraja contract: real HttpMpesaClient ↔ WireMock stubs (mocks/mappings/mpesa-*.json).

A small HTTP server stands in for our callback endpoint, so we also check that every callback the stubs
send parses with the API's own CallbackIn model (and that the unit-test fake produces the same results).
CALLBACK_HOST is how WireMock reaches this test process (localhost, or host.docker.internal in CI).
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from permitpass.integrations.fakes import MPESA_RULES, callback_body
from permitpass.integrations.mpesa import CallbackIn, HttpMpesaClient, MpesaUnavailable, normalise_phone

CALLBACK_HOST = os.getenv("CALLBACK_HOST", "localhost")


@pytest.fixture
def receiver():
    got: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ResultCode":0,"ResultDesc":"Accepted"}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.got = got
    server.url = f"http://{CALLBACK_HOST}:{server.server_address[1]}/payments/mpesa/callback?token=t"
    yield server
    server.shutdown()


def wait_for(got, n, seconds=6.0):
    deadline = time.monotonic() + seconds
    while len(got) < n and time.monotonic() < deadline:
        time.sleep(0.1)
    return got


@pytest.fixture
def mpesa(base_url):
    return HttpMpesaClient(base_url, "key", "secret", "174379", "passkey", timeout_seconds=5)


def _push(mpesa, receiver, phone, ref):
    return mpesa.stk_push(phone, 2500, ref, "Permit fee", receiver.url)


def test_success_push_and_callback(wiremock, mpesa, receiver):
    push = _push(mpesa, receiver, "0712345678", "REFSUCCESS01")
    assert push.checkout_request_id == "ws_CO_REFSUCCESS01"
    [body] = wait_for(receiver.got, 1)
    cb = CallbackIn.model_validate(body).Body.stkCallback           # parses with the API's own model
    assert (cb.CheckoutRequestID, cb.ResultCode) == ("ws_CO_REFSUCCESS01", 0)
    assert cb.item("Amount") == 2500 and cb.item("PhoneNumber") == 254712345678
    assert len(str(cb.item("MpesaReceiptNumber"))) == 10


@pytest.mark.parametrize("phone,code,amount,callbacks", [
    ("0700000032", 1032, None, 1),
    ("0700000037", 1037, None, 1),
    ("0700000001", 0, 1, 1),
    ("0700000002", 0, 2500, 2),
])
def test_rule_phones(wiremock, mpesa, receiver, phone, code, amount, callbacks):
    ref = f"R{phone[-6:]}{code:05d}"[:12]
    _push(mpesa, receiver, phone, ref)
    got = wait_for(receiver.got, callbacks)
    time.sleep(0.3)   # make sure no extra callback follows
    assert len(got) == callbacks
    for body in got:
        cb = CallbackIn.model_validate(body).Body.stkCallback
        assert (cb.CheckoutRequestID, cb.ResultCode, cb.item("Amount")) == (f"ws_CO_{ref}", code, amount)


def test_no_callback_phone_never_calls_back(wiremock, mpesa, receiver):
    _push(mpesa, receiver, "0700000000", "REFSILENT001")
    time.sleep(2.5)
    assert receiver.got == []


def test_stk_error_phone_raises(wiremock, mpesa, receiver):
    with pytest.raises(MpesaUnavailable):
        _push(mpesa, receiver, "0700000500", "REFERROR0001")


@pytest.mark.parametrize("msisdn,rule", list(MPESA_RULES.items()) + [("254712345678", None)])
def test_fake_and_stubs_agree(wiremock, mpesa, receiver, msisdn, rule):
    """The unit-test fake must produce the same outcome (result code, amount, callback count) as the stubs."""
    ref = f"F{msisdn[-8:]}XYZ"[:12]
    if rule == "stk_error":
        with pytest.raises(MpesaUnavailable):
            _push(mpesa, receiver, "0" + msisdn[3:], ref)
        return
    _push(mpesa, receiver, "0" + msisdn[3:], ref)
    expected = 0 if rule == "no_callback" else 2 if rule == "duplicate" else 1
    got = wait_for(receiver.got, expected, seconds=3 if expected else 2.5)
    assert len(got) == expected
    if expected:
        fake = callback_body(f"ws_CO_{ref}", 2500, msisdn, rule, receipt="X")["Body"]["stkCallback"]
        stub = got[0]["Body"]["stkCallback"]
        assert (stub["ResultCode"], stub["CheckoutRequestID"]) == (fake["ResultCode"], fake["CheckoutRequestID"])
        amount = lambda cb: next((i["Value"] for i in cb.get("CallbackMetadata", {}).get("Item", []) if i["Name"] == "Amount"), None)  # noqa: E731
        assert amount(stub) == amount(fake)


def test_requests_without_bearer_token_break_the_contract(wiremock, base_url):
    """Guard: the stubs really enforce auth and required fields, so the tests above prove something."""
    r = httpx.post(f"{base_url}/mpesa/stkpush/v1/processrequest", json={"Amount": 1})
    assert r.status_code == 400 and "CONTRACT VIOLATION" in r.text
    wiremock.delete("/requests")


def test_phone_normalisation_matches_stub_rules():
    assert normalise_phone("0700000032") == "254700000032"
