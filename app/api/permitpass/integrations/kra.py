"""KRA PIN Checker (SOAP 1.1).

The real client POSTs a ValidatePIN envelope and parses the reply with defusedxml (no XXE or entity
expansion from a hostile or broken upstream). Anything other than a clean, well-formed answer
(timeout, HTTP error, SOAP fault, unparseable XML) becomes KraUnavailable, and the API fails closed.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from xml.sax.saxutils import escape

import httpx
from defusedxml import ElementTree

SOAP_ACTION = "urn:kra:pinchecker/ValidatePIN"
NS = "urn:kra:pinchecker"


class PinStatus(str, Enum):
    active = "Active"
    inactive = "Inactive"
    not_found = "NotFound"


@dataclass(frozen=True)
class PinCheck:
    pin: str
    status: PinStatus
    taxpayer_name: str = ""


class KraUnavailable(Exception):
    """KRA could not give a trustworthy answer (timeout, fault, bad response)."""


class KraClient(Protocol):
    def validate_pin(self, pin: str) -> PinCheck: ...


def envelope(pin: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><ValidatePIN xmlns="{NS}"><KRAPIN>{escape(pin)}</KRAPIN></ValidatePIN></soap:Body>'
        "</soap:Envelope>"
    )


def parse(xml: bytes) -> PinCheck:
    try:
        root = ElementTree.fromstring(xml)
    except Exception as exc:  # ParseError and defusedxml's DTD/entity rejections
        raise KraUnavailable(f"unreadable KRA response: {exc}") from None
    node = next((e for e in root.iter() if e.tag.split("}")[-1] == "PinCheckResponse"), None)
    if node is None:
        raise KraUnavailable("KRA response has no PinCheckResponse")
    fields = {child.tag.split("}")[-1]: (child.text or "").strip() for child in node}
    try:
        status = PinStatus(fields.get("Status", ""))
    except ValueError:
        raise KraUnavailable(f"unknown KRA status {fields.get('Status')!r}") from None
    return PinCheck(pin=fields.get("KRAPIN", ""), status=status, taxpayer_name=fields.get("TaxpayerName", ""))


class HttpKraClient:
    def __init__(self, base_url: str, timeout_seconds: float = 3.0, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)

    def validate_pin(self, pin: str) -> PinCheck:
        try:
            r = self._http.post(
                "/kra/PinChecker",
                content=envelope(pin).encode(),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": SOAP_ACTION},
            )
        except httpx.TimeoutException:
            raise KraUnavailable("KRA timed out") from None
        except httpx.HTTPError as exc:
            raise KraUnavailable(f"KRA unreachable: {exc}") from None
        if r.status_code != 200:
            raise KraUnavailable(f"KRA returned HTTP {r.status_code}")
        result = parse(r.content)
        if result.pin != pin:
            raise KraUnavailable("KRA answered for a different PIN")
        return result
