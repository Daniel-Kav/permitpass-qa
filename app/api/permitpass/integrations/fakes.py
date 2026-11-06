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
