"""The real KRA HTTP client, against a scripted transport (no network).

Covers the request shape, response parsing, every failure mode and hostile XML.
"""
import httpx
import pytest

from permitpass.integrations.kra import SOAP_ACTION, HttpKraClient, KraUnavailable, PinStatus, envelope

SOAP = ('<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
        '{}</soap:Body></soap:Envelope>')


def answer(pin="A123456789Z", status="Active", name="MAMA MBOGA"):
    return SOAP.format(f'<PinCheckResponse xmlns="urn:kra:pinchecker"><KRAPIN>{pin}</KRAPIN>'
                       f'<Status>{status}</Status><TaxpayerName>{name}</TaxpayerName></PinCheckResponse>')


def client_returning(*, status=200, body="", exc=None, seen=None):
    def handler(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        if exc:
            raise exc
        return httpx.Response(status, text=body, headers={"Content-Type": "text/xml"})
    return HttpKraClient("http://kra.test", transport=httpx.MockTransport(handler))


def test_request_shape():
    seen = []
    client_returning(body=answer(), seen=seen).validate_pin("A123456789Z")
    req = seen[0]
    assert (req.method, req.url.path) == ("POST", "/kra/PinChecker")
    assert req.headers["SOAPAction"] == SOAP_ACTION
    assert req.headers["Content-Type"].startswith("text/xml")
    assert b"<KRAPIN>A123456789Z</KRAPIN>" in req.content and b"<ValidatePIN" in req.content


@pytest.mark.parametrize("status", list(PinStatus))
def test_parses_each_status(status):
    result = client_returning(body=answer(status=status.value)).validate_pin("A123456789Z")
    assert result.status is status


def test_taxpayer_name_is_read():
    assert client_returning(body=answer(name="DUKA LTD")).validate_pin("A123456789Z").taxpayer_name == "DUKA LTD"


@pytest.mark.parametrize("case,kwargs", [
    ("timeout", {"exc": httpx.ReadTimeout("slow")}),
    ("connection refused", {"exc": httpx.ConnectError("refused")}),
    ("http 500 soap fault", {"status": 500, "body": SOAP.format("<soap:Fault><faultstring>down</faultstring></soap:Fault>")}),
    ("http 503", {"status": 503, "body": ""}),
    ("not xml", {"body": "<html>Gateway error</html"}),
    ("no PinCheckResponse", {"body": SOAP.format("<Other/>")}),
    ("unknown status", {"body": answer(status="Suspended")}),
    ("answer for another PIN", {"body": answer(pin="P000000000A")}),
])
def test_every_failure_becomes_kra_unavailable(case, kwargs):
    with pytest.raises(KraUnavailable):
        client_returning(**kwargs).validate_pin("A123456789Z")


@pytest.mark.parametrize("payload", [
    # XXE: try to read a local file through an external entity
    '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    '<PinCheckResponse><KRAPIN>A123456789Z</KRAPIN><Status>&xxe;</Status></PinCheckResponse>',
    # Billion laughs: entity expansion bomb
    '<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
    '<PinCheckResponse><KRAPIN>A123456789Z</KRAPIN><Status>&b;</Status></PinCheckResponse>',
], ids=["xxe", "entity-expansion"])
def test_hostile_xml_is_refused(payload):
    with pytest.raises(KraUnavailable):
        client_returning(body=payload).validate_pin("A123456789Z")


def test_pin_is_xml_escaped_in_the_request():
    assert "<KRAPIN>A&lt;b&gt;&amp;</KRAPIN>" in envelope("A<b>&")
