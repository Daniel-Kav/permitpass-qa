"""The real Daraja client against a scripted transport: OAuth, STK payload and failure handling."""
import base64
import re

import httpx
import pytest

from permitpass.integrations.mpesa import HttpMpesaClient, MpesaUnavailable, normalise_phone

OK = {"MerchantRequestID": "29115-1", "CheckoutRequestID": "ws_CO_ABC", "ResponseCode": "0",
      "ResponseDescription": "Success. Request accepted for processing", "CustomerMessage": "ok"}


def make(stk=lambda req: httpx.Response(200, json=OK), oauth=None, seen=None):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append(req)
        if req.url.path == "/oauth/v1/generate":
            return oauth(req) if oauth else httpx.Response(200, json={"access_token": "tok-1", "expires_in": "3599"})
        return stk(req)
    return HttpMpesaClient("http://daraja.test", "key", "secret", "174379", "passkey",
                           transport=httpx.MockTransport(handler))


def push(client, phone="0712345678"):
    return client.stk_push(phone, 2500, "AB12CD34EF56", "Permit fee for business", "http://cb.test/cb?token=t")


def test_oauth_uses_basic_auth_and_token_is_reused():
    seen = []
    client = make(seen=seen)
    push(client), push(client)
    oauth = [r for r in seen if r.url.path == "/oauth/v1/generate"]
    assert len(oauth) == 1, "token should be cached between pushes"
    assert oauth[0].headers["Authorization"] == "Basic " + base64.b64encode(b"key:secret").decode()
    assert oauth[0].url.params["grant_type"] == "client_credentials"


def test_stk_payload_matches_daraja_spec():
    seen = []
    result = push(make(seen=seen))
    req = next(r for r in seen if r.url.path == "/mpesa/stkpush/v1/processrequest")
    body = httpx.Response(200, content=req.content).json()
    assert req.headers["Authorization"] == "Bearer tok-1"
    assert re.fullmatch(r"\d{14}", body["Timestamp"])
    assert base64.b64decode(body["Password"]).decode() == f"174379passkey{body['Timestamp']}"
    assert body | {"Password": None, "Timestamp": None} == {
        "BusinessShortCode": "174379", "Password": None, "Timestamp": None,
        "TransactionType": "CustomerPayBillOnline", "Amount": 2500,
        "PartyA": 254712345678, "PartyB": "174379", "PhoneNumber": 254712345678,
        "CallBackURL": "http://cb.test/cb?token=t", "AccountReference": "AB12CD34EF56",
        "TransactionDesc": "Permit fee fo",          # Daraja's 13-character limit
    }
    assert result.checkout_request_id == "ws_CO_ABC"


@pytest.mark.parametrize("case,kwargs", [
    ("stk http 500", {"stk": lambda r: httpx.Response(500, json={"errorMessage": "boom"})}),
    ("stk refused", {"stk": lambda r: httpx.Response(200, json={**OK, "ResponseCode": "1", "ResponseDescription": "Invalid"})}),
    ("stk bad json", {"stk": lambda r: httpx.Response(200, text="<html>")}),
    ("stk missing fields", {"stk": lambda r: httpx.Response(200, json={"ResponseCode": "0"})}),
    ("oauth 401", {"oauth": lambda r: httpx.Response(401, json={})}),
    ("oauth no token", {"oauth": lambda r: httpx.Response(200, json={})}),
])
def test_failures_become_mpesa_unavailable(case, kwargs):
    with pytest.raises(MpesaUnavailable):
        push(make(**kwargs))


def test_timeout_becomes_mpesa_unavailable():
    def slow(req):
        raise httpx.ReadTimeout("slow")
    with pytest.raises(MpesaUnavailable):
        push(make(stk=slow))


@pytest.mark.parametrize("phone,expected", [("0712345678", "254712345678"), ("+254112345678", "254112345678"), ("254712345678", "254712345678")])
def test_normalise_phone(phone, expected):
    assert normalise_phone(phone) == expected
