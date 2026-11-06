"""Contract tests: the REAL clients against the WireMock stubs in mocks/.

They prove our requests have the shape the stubs (and so the provider docs) expect: no request may
fall through to a catch-all 'contract violation' stub, and WireMock must report zero unmatched requests.
Run with WIREMOCK_URL set (CI starts WireMock with mocks/ mounted); skipped otherwise.
"""
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app" / "api"))

WIREMOCK_URL = os.getenv("WIREMOCK_URL")
pytestmark = pytest.mark.skipif(not WIREMOCK_URL, reason="WIREMOCK_URL not set")


@pytest.fixture
def wiremock():
    if not WIREMOCK_URL:
        pytest.skip("WIREMOCK_URL not set")
    admin = httpx.Client(base_url=f"{WIREMOCK_URL}/__admin", timeout=5)
    admin.delete("/requests")
    yield admin
    served = admin.get("/requests").json()["requests"]
    violations = [r["request"]["url"] for r in served if "catch-all" in r.get("stubMapping", {}).get("name", "")]
    unmatched = admin.get("/requests/unmatched").json()["requests"]
    admin.close()
    assert not violations, f"requests that broke the contract (hit a catch-all stub): {violations}"
    assert unmatched == [], f"requests that matched no stub at all: {unmatched}"


@pytest.fixture
def base_url():
    return WIREMOCK_URL
