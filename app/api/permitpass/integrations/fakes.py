"""In-process fakes for unit tests and offline dev. They follow the SAME test-data rules as the
WireMock stubs in mocks/ (see mocks/README.md), so a test behaves identically against either."""
from .kra import KraUnavailable, PinCheck, PinStatus

KRA_RULES = {  # nine-digit block inside the PIN -> behaviour
    "999999999": PinStatus.not_found,
    "666666666": PinStatus.inactive,
    "888888888": "fault",
    "777777777": "timeout",
}


class FakeKraClient:
    def __init__(self):
        self.calls: list[str] = []

    def validate_pin(self, pin: str) -> PinCheck:
        self.calls.append(pin)
        rule = KRA_RULES.get(pin[1:10])
        if rule in ("fault", "timeout"):
            raise KraUnavailable(f"fake KRA {rule}")
        return PinCheck(pin=pin, status=rule or PinStatus.active, taxpayer_name="REGISTERED TAXPAYER")


# ---------- M-Pesa ----------
# Phone-number rules (same as the WireMock stubs): see mocks/README.md
from .mpesa import MpesaUnavailable, StkPush, StkQueryResult, normalise_phone  # noqa: E402

MPESA_RULES = {
    "254700000032": "cancelled",
    "254700000037": "timeout",
    "254700000001": "wrong_amount",
    "254700000002": "duplicate",
    "254700000000": "no_callback",
    "254700000500": "stk_error",
    "254700000003": "query_success",     # no callback; STK query later says success
    "254700000004": "query_cancelled",   # no callback; STK query later says cancelled (1032)
}
# Those two get recognisable CheckoutRequestIDs so the query (which only sees that id) can follow the rule
QUERY_PREFIX = {"query_success": "QOK_", "query_cancelled": "QCX_"}


def query_answer(checkout_id: str) -> StkQueryResult:
    """What the STK Push Query returns (same rules as mocks/mappings/mpesa-query-*.json)."""
    if "_QOK_" in checkout_id:
        return StkQueryResult(False, 0, "The service request is processed successfully.")
    if "_QCX_" in checkout_id:
        return StkQueryResult(False, 1032, "Request cancelled by user")
    return StkQueryResult(True, None, "The transaction is being processed")


def callback_body(checkout_id: str, amount: int, phone: str, rule: str | None, receipt: str) -> dict | None:
    """The callback M-Pesa (or our stub) would send for this STK push."""
    if rule == "cancelled":
        result = {"ResultCode": 1032, "ResultDesc": "Request cancelled by user"}
    elif rule == "timeout":
        result = {"ResultCode": 1037, "ResultDesc": "DS timeout user cannot be reached"}
    else:
        paid = 1 if rule == "wrong_amount" else amount
        result = {"ResultCode": 0, "ResultDesc": "The service request is processed successfully.",
                  "CallbackMetadata": {"Item": [
                      {"Name": "Amount", "Value": paid},
                      {"Name": "MpesaReceiptNumber", "Value": receipt},
                      {"Name": "TransactionDate", "Value": 20261106093000},
                      {"Name": "PhoneNumber", "Value": int(phone)},
                  ]}}
    return {"Body": {"stkCallback": {"MerchantRequestID": f"fake-{checkout_id[-6:]}", "CheckoutRequestID": checkout_id, **result}}}


class FakeMpesaClient:
    """Records STK pushes and queues the callbacks the stub would send. Tests deliver them explicitly."""

    def __init__(self):
        self.pushes: list[dict] = []
        self.pending_callbacks: list[dict] = []
        self.queries: list[str] = []
        self.query_unavailable = False
        self._n = 0

    def stk_push(self, phone, amount, account_ref, description, callback_url) -> StkPush:
        msisdn = normalise_phone(phone)
        rule = MPESA_RULES.get(msisdn)
        self.pushes.append({"phone": msisdn, "amount": amount, "account_ref": account_ref, "callback_url": callback_url})
        if rule == "stk_error":
            raise MpesaUnavailable("fake STK error")
        checkout = f"ws_CO_{QUERY_PREFIX.get(rule, '')}{account_ref}"
        if rule not in ("no_callback", "query_success", "query_cancelled"):
            self._n += 1
            body = callback_body(checkout, amount, msisdn, rule, receipt=f"FAKE{self._n:06d}")
            self.pending_callbacks += [body, body] if rule == "duplicate" else [body]
        return StkPush(merchant_request_id=f"fake-{account_ref}", checkout_request_id=checkout)

    def stk_query(self, checkout_request_id: str) -> StkQueryResult:
        self.queries.append(checkout_request_id)
        if self.query_unavailable:
            raise MpesaUnavailable("fake query outage")
        return query_answer(checkout_request_id)
