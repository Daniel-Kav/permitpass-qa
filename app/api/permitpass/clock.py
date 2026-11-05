"""Single source of 'now', so tests can move time (e.g. to check certificate expiry)."""
from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
