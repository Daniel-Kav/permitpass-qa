"""Single source of 'now', so tests can move time (e.g. to check certificate expiry)."""
from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime) -> datetime:
    """Normalise to UTC. SQLite returns naive values (stored as UTC); PostgreSQL returns them
    in the server's session time zone. Either way the API speaks UTC (see #13)."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
