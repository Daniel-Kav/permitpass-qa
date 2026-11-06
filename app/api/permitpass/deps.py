"""Wiring for external clients, overridable in tests via app.dependency_overrides."""
from functools import lru_cache

from . import config
from .integrations.fakes import FakeKraClient, FakeMpesaClient
from .integrations.kra import HttpKraClient, KraClient
from .integrations.mpesa import HttpMpesaClient, MpesaClient


@lru_cache
def get_kra_client() -> KraClient:
    if config.INTEGRATIONS_MODE == "fake":
        return FakeKraClient()
    if not config.KRA_BASE_URL:
        raise RuntimeError("KRA_BASE_URL is not set (or set INTEGRATIONS_MODE=fake for offline use)")
    return HttpKraClient(config.KRA_BASE_URL, config.KRA_TIMEOUT_SECONDS)


@lru_cache
def get_mpesa_client() -> MpesaClient:
    if config.INTEGRATIONS_MODE == "fake":
        return FakeMpesaClient()
    if not config.MPESA_BASE_URL:
        raise RuntimeError("MPESA_BASE_URL is not set (or set INTEGRATIONS_MODE=fake for offline use)")
    return HttpMpesaClient(config.MPESA_BASE_URL, config.MPESA_CONSUMER_KEY, config.MPESA_CONSUMER_SECRET,
                           config.MPESA_SHORTCODE, config.MPESA_PASSKEY, config.MPESA_TIMEOUT_SECONDS)
