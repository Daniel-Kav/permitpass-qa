"""One-off start-up step, run once before the API workers: create tables, seed demo users if enabled.

    python -m permitpass.prestart && uvicorn permitpass.main:app --workers 4
Safe to run repeatedly.
"""
from . import config
from .db import SessionLocal, init_db


def main() -> None:
    init_db()
    if config.SEED_DEMO_USERS:
        from .seed import seed_users

        with SessionLocal() as session:
            seed_users(session)
    print("prestart: database ready" + (", demo users seeded" if config.SEED_DEMO_USERS else ""))


if __name__ == "__main__":
    main()
