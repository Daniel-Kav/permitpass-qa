"""Database engine and session handling (SQLAlchemy 2.0)."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from . import config


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite") and ":memory:" in url:
        # One shared in-memory database across threads (TestClient runs the app in a worker thread)
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=config.DB_POOL_SIZE,
                         max_overflow=config.DB_MAX_OVERFLOW, pool_timeout=config.DB_POOL_TIMEOUT_SECONDS)


engine = _make_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def reset_db() -> None:
    """Test helper: empty every table so each test starts from a known state."""
    init_db()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
