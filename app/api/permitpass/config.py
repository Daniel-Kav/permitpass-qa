"""Runtime settings, read once from the environment."""
import os
import warnings

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./permitpass.db")

_DEV_SECRET = "dev-only-change-me-0123456789abcdef"
JWT_SECRET = os.getenv("JWT_SECRET", _DEV_SECRET)
if JWT_SECRET == _DEV_SECRET:
    warnings.warn("JWT_SECRET not set: using the development secret", stacklevel=1)
JWT_ALGORITHM = "HS256"

CERT_SECRET = os.getenv("CERT_SECRET", "dev-only-cert-secret-0123456789abcdef")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))

# OWASP 2023 guidance for PBKDF2-SHA256. Tests lower this to stay fast.
PASSWORD_HASH_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "600000"))

SEED_DEMO_USERS = os.getenv("SEED_DEMO_USERS", "false").lower() == "true"
