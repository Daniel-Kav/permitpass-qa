"""Shared fixtures for the API suite.

Tests run in-process against the FastAPI app (fast, no network). Set
PERMITPASS_BASE_URL to point the same tests at a running stack instead.
"""
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

from permitpass.main import app, reset_db  # noqa: E402

BASE_URL = os.getenv("PERMITPASS_BASE_URL")


@pytest.fixture(autouse=True)
def clean_db():
    reset_db()
    yield
    reset_db()


@pytest.fixture
def client():
    if BASE_URL:
        with httpx.Client(base_url=BASE_URL, timeout=10) as c:
            yield c
    else:
        with TestClient(app) as c:
            yield c


def as_role(role: str, user_id: str | None = None) -> dict[str, str]:
    return {"X-User-Id": user_id or f"{role}-1", "X-User-Role": role}


CITIZEN = as_role("citizen", "citizen-1")
OTHER_CITIZEN = as_role("citizen", "citizen-2")
OFFICER = as_role("officer", "officer-1")
ADMIN = as_role("admin", "admin-1")

VALID_APPLICATION = {"business_name": "Mama Mboga Groceries", "kra_pin": "A123456789Z"}
