"""Wiring for external clients, overridable in tests via app.dependency_overrides."""
from functools import lru_cache

from . import config
from .integrations.fakes import FakeKraClient
from .integrations.kra import HttpKraClient, KraClient


@lru_cache
def get_kra_client() -> KraClient:
    if config.INTEGRATIONS_MODE == "fake":
        return FakeKraClient()
    if not config.KRA_BASE_URL:
        raise RuntimeError("KRA_BASE_URL is not set (or set INTEGRATIONS_MODE=fake for offline use)")
    return HttpKraClient(config.KRA_BASE_URL, config.KRA_TIMEOUT_SECONDS)
