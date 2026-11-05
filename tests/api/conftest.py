"""Shared fixtures for the API suite.

Tests run in-process against the FastAPI app (fast, no network). Set
DATABASE_URL to choose the database engine, or PERMITPASS_BASE_URL to point
the same tests at a running stack (which must share JWT_SECRET).
"""
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app" / "api"))

# Fast, isolated defaults. CI also runs with DATABASE_URL pointing at PostgreSQL.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789")
os.environ.setdefault("PASSWORD_HASH_ITERATIONS", "1000")

from fastapi.testclient import TestClient  # noqa: E402

from permitpass.db import SessionLocal  # noqa: E402
from permitpass.main import app, reset_db  # noqa: E402
from permitpass.security import create_access_token  # noqa: E402
from permitpass.seed import DEMO_PASSWORD, DEMO_USERS, seed_users  # noqa: E402

BASE_URL = os.getenv("PERMITPASS_BASE_URL")
PASSWORD = DEMO_PASSWORD


@pytest.fixture(autouse=True)
def clean_db():
    reset_db()
    with SessionLocal() as s:
        seed_users(s)
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


def bearer(user_id: str, **token_kwargs) -> dict[str, str]:
    role = next(r for uid, _, _, r in DEMO_USERS if uid == user_id).value
    return {"Authorization": f"Bearer {create_access_token(user_id, role, **token_kwargs)}"}


CITIZEN = bearer("citizen-1")
OTHER_CITIZEN = bearer("citizen-2")
OFFICER = bearer("officer-1")
ADMIN = bearer("admin-1")
EMAILS = {uid: email for uid, email, _, _ in DEMO_USERS}

VALID_APPLICATION = {"business_name": "Mama Mboga Groceries", "kra_pin": "A123456789Z"}
