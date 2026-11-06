"""Authentication: login, token handling and the negative cases attackers try first.

Traceability: US-16, US-17.
"""
import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from conftest import CITIZEN, EMAILS, PASSWORD, VALID_APPLICATION, bearer, drive

from permitpass import config
from permitpass.db import SessionLocal
from permitpass.models import UserRow


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------- login ----------

@pytest.mark.parametrize("user_id", list(EMAILS))
def test_login_returns_token_with_role(client, user_id):
    r = _login(client, EMAILS[user_id], PASSWORD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == config.ACCESS_TOKEN_MINUTES * 60
    claims = jwt.decode(body["access_token"], config.JWT_SECRET, algorithms=["HS256"])
    assert claims["sub"] == user_id
    assert claims["role"] == body["role"]


def test_login_token_works_on_protected_route(client):
    token = _login(client, EMAILS["citizen-1"], PASSWORD).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == "citizen-1"
    assert "password_hash" not in r.json()


def test_login_email_is_case_insensitive(client):
    assert _login(client, "  CITIZEN@PermitPass.test ", PASSWORD).status_code == 200


@pytest.mark.parametrize("email,password", [
    ("citizen@permitpass.test", "wrong-password"),   # known user, wrong password
    ("nobody@permitpass.test", "PermitPass!2026"),   # unknown user
    ("citizen@permitpass.test", "permitpass!2026"),  # password is case-sensitive
])
def test_failed_login_gives_one_generic_answer(client, email, password):
    """Same status and message whatever was wrong, so attackers can't discover which emails exist."""
    r = _login(client, email, password)
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


@pytest.mark.parametrize("body", [{}, {"email": "a@b.c"}, {"email": "", "password": "x"}, {"email": "a@b.c", "password": ""}])
def test_malformed_login_body_rejected(client, body):
    assert client.post("/auth/login", json=body).status_code == 422


def test_deactivated_user_cannot_log_in_or_use_old_token(client):
    old_token = CITIZEN
    with SessionLocal() as s:
        s.get(UserRow, "citizen-1").is_active = False
        s.commit()
    assert _login(client, EMAILS["citizen-1"], PASSWORD).status_code == 401
    assert client.get("/auth/me", headers=old_token).status_code == 401


def test_passwords_are_stored_hashed_and_salted():
    with SessionLocal() as s:
        hashes = [u.password_hash for u in s.query(UserRow).all()]
    assert all(h.startswith("pbkdf2_sha256$") for h in hashes)
    assert PASSWORD not in "".join(hashes)
    assert len(set(hashes)) == len(hashes), "same password must give different hashes (salt)"


# ---------- bad tokens ----------

def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _bad_tokens() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    good = bearer("citizen-1")["Authorization"].removeprefix("Bearer ")
    header, payload, sig = good.split(".")
    claims = {"sub": "officer-1", "role": "officer", "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=5)).timestamp())}
    return {
        "expired": bearer("citizen-1", minutes=-1)["Authorization"].removeprefix("Bearer "),
        "wrong_secret": jwt.encode(claims, "some-other-secret-0123456789abcdef", algorithm="HS256"),
        "alg_none": f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}.",
        "payload_swapped": f"{header}.{_b64(claims)}.{sig}",  # officer claims under the citizen's signature
        "unknown_user": jwt.encode({**claims, "sub": "ghost"}, config.JWT_SECRET, algorithm="HS256"),
        "missing_exp": jwt.encode({"sub": "citizen-1", "role": "citizen", "iat": claims["iat"]}, config.JWT_SECRET, algorithm="HS256"),
        "garbage": "not.a.jwt",
    }


@pytest.mark.parametrize("kind", list(_bad_tokens()))
def test_bad_tokens_are_rejected(client, kind):
    token = _bad_tokens()[kind]
    r = client.post("/applications", json=VALID_APPLICATION, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, f"{kind} token was accepted"
    assert r.headers.get("www-authenticate") == "Bearer"


def test_wrong_auth_scheme_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Basic Y2l0aXplbjpwYXNz"})
    assert r.status_code == 401


def test_role_comes_from_database_not_token(client):
    """A validly signed token claiming 'officer' for a citizen account must not grant officer powers."""
    forged = jwt.encode(
        {"sub": "citizen-1", "role": "officer", "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        config.JWT_SECRET, algorithm="HS256",
    )
    app_id = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN).json()["id"]
    drive(client, app_id, ["submit", "pay"])
    r = client.post(f"/applications/{app_id}/approve", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403
