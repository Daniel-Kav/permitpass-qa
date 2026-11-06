"""M-Pesa Daraja: OAuth token + Lipa na M-Pesa Online (STK push), and parsing of the result callback."""
import base64
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field

EAT = ZoneInfo("Africa/Nairobi")   # Daraja timestamps are Kenyan local time


def normalise_phone(phone: str) -> str:
    """0712345678 / +254712345678 / 254712345678 -> 254712345678 (format already validated)."""
    digits = phone.lstrip("+")
    return "254" + digits[1:] if digits.startswith("0") else digits


@dataclass(frozen=True)
class StkPush:
    merchant_request_id: str
    checkout_request_id: str


class MpesaUnavailable(Exception):
    """The STK push could not be started."""


class MpesaClient(Protocol):
    def stk_push(self, phone: str, amount: int, account_ref: str, description: str, callback_url: str) -> StkPush: ...


@dataclass
class HttpMpesaClient:
    base_url: str
    consumer_key: str
    consumer_secret: str
    shortcode: str
    passkey: str
    timeout_seconds: float = 10.0
    transport: httpx.BaseTransport | None = None
    _token: str | None = field(default=None, init=False, repr=False)
    _token_expires: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self):
        self._http = httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds, transport=self.transport)

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        r = self._http.get("/oauth/v1/generate", params={"grant_type": "client_credentials"},
                           auth=(self.consumer_key, self.consumer_secret))
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_expires = time.monotonic() + int(body.get("expires_in", 3599)) - 60   # refresh a minute early
        return self._token

    def password(self, timestamp: str) -> str:
        return base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode()).decode()

    def stk_push(self, phone: str, amount: int, account_ref: str, description: str, callback_url: str) -> StkPush:
        timestamp = datetime.now(EAT).strftime("%Y%m%d%H%M%S")
        msisdn = int(normalise_phone(phone))
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self.password(timestamp),
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": msisdn,
            "PartyB": self.shortcode,
            "PhoneNumber": msisdn,
            "CallBackURL": callback_url,
            "AccountReference": account_ref,
            "TransactionDesc": description[:13],   # Daraja limit
        }
        try:
            r = self._http.post("/mpesa/stkpush/v1/processrequest", json=payload,
                                headers={"Authorization": f"Bearer {self._access_token()}"})
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise MpesaUnavailable(f"M-Pesa unreachable: {exc}") from None
        if r.status_code != 200:
            raise MpesaUnavailable(f"M-Pesa returned HTTP {r.status_code}")
        try:
            body = r.json()
            if str(body["ResponseCode"]) != "0":
                raise MpesaUnavailable(f"M-Pesa refused: {body.get('ResponseDescription')}")
            return StkPush(body["MerchantRequestID"], body["CheckoutRequestID"])
        except (KeyError, ValueError):
            raise MpesaUnavailable("unexpected M-Pesa response") from None


# ---------- callback (what M-Pesa POSTs to us) ----------

class _Item(BaseModel):
    Name: str
    Value: str | int | float | None = None


class _Metadata(BaseModel):
    Item: list[_Item] = []


class StkCallback(BaseModel):
    model_config = ConfigDict(extra="ignore")
    MerchantRequestID: str
    CheckoutRequestID: str = Field(min_length=1, max_length=64)
    ResultCode: int
    ResultDesc: str = Field(max_length=300)
    CallbackMetadata: _Metadata | None = None

    def item(self, name: str):
        for i in (self.CallbackMetadata.Item if self.CallbackMetadata else []):
            if i.Name == name:
                return i.Value
        return None


class _CallbackBody(BaseModel):
    stkCallback: StkCallback


class CallbackIn(BaseModel):
    Body: _CallbackBody
