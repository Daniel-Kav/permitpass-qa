"""Password hashing and JWT access tokens."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from . import config

_SCHEME = "pbkdf2_sha256"


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or config.PASSWORD_HASH_ITERATIONS
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"{_SCHEME}${iterations}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != _SCHEME:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
    return hmac.compare_digest(candidate, base64.b64decode(digest))


# Verified when the email is unknown, so a miss takes as long as a wrong password (no user enumeration by timing)
DUMMY_HASH = hash_password("not-a-real-password", iterations=config.PASSWORD_HASH_ITERATIONS)


def create_access_token(user_id: str, role: str, minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes if minutes is not None else config.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError for anything that is not a valid, unexpired token we signed."""
    return jwt.decode(
        token,
        config.JWT_SECRET,
        algorithms=[config.JWT_ALGORITHM],  # pinned: rejects alg=none and algorithm-confusion tokens
        options={"require": ["sub", "role", "exp", "iat"]},
    )
