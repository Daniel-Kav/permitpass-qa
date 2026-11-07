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

# External systems. INTEGRATIONS_MODE=fake uses in-process fakes (unit tests, offline dev);
# otherwise the base URLs must point at the real services or the WireMock stubs in mocks/.
INTEGRATIONS_MODE = os.getenv("INTEGRATIONS_MODE", "real")
KRA_BASE_URL = os.getenv("KRA_BASE_URL", "")
KRA_TIMEOUT_SECONDS = float(os.getenv("KRA_TIMEOUT_SECONDS", "3"))
MPESA_BASE_URL = os.getenv("MPESA_BASE_URL", "")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "dev-consumer-key")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "dev-consumer-secret")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "dev-passkey")
MPESA_TIMEOUT_SECONDS = float(os.getenv("MPESA_TIMEOUT_SECONDS", "10"))
# Where M-Pesa should POST results. The token must match MPESA_CALLBACK_TOKEN.
MPESA_CALLBACK_TOKEN = os.getenv("MPESA_CALLBACK_TOKEN", "dev-callback-token-0123456789")
MPESA_CALLBACK_URL = os.getenv(
    "MPESA_CALLBACK_URL", f"http://localhost:8000/payments/mpesa/callback?token={MPESA_CALLBACK_TOKEN}"
)
# Payments that get no callback (#30): query M-Pesa after this long, give up after that long
PAYMENT_QUERY_AFTER_SECONDS = int(os.getenv("PAYMENT_QUERY_AFTER_SECONDS", "120"))
PAYMENT_EXPIRE_AFTER_SECONDS = int(os.getenv("PAYMENT_EXPIRE_AFTER_SECONDS", "600"))
PAYMENT_SWEEP_INTERVAL_SECONDS = int(os.getenv("PAYMENT_SWEEP_INTERVAL_SECONDS", "30"))   # 0 disables the background sweep

# Capacity (#36)
# In production a pre-start step (python -m permitpass.prestart) creates tables and seeds once, before the
# workers start; INIT_DB_ON_STARTUP=false then stops N workers racing to do the same thing.
INIT_DB_ON_STARTUP = os.getenv("INIT_DB_ON_STARTUP", "true").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT_SECONDS = float(os.getenv("DB_POOL_TIMEOUT_SECONDS", "5"))   # fail fast instead of SQLAlchemy's 30 s
# Requests a worker accepts at once; beyond that it answers 503 immediately. 0 = unlimited (tests, dev).
MAX_IN_FLIGHT = int(os.getenv("MAX_IN_FLIGHT", "0"))
