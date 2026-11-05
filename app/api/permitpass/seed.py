"""Demo users for local development. Never enable SEED_DEMO_USERS in a real environment.

Run directly:  python -m permitpass.seed
"""
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .domain import Role
from .models import UserRow
from .security import hash_password

DEMO_PASSWORD = "PermitPass!2026"  # local dev only, documented in README

DEMO_USERS = [
    ("citizen-1", "citizen@permitpass.test", "Wanjiru Kamau", Role.citizen),
    ("citizen-2", "citizen2@permitpass.test", "Otieno Ouma", Role.citizen),
    ("officer-1", "officer@permitpass.test", "Achieng Odhiambo", Role.officer),
    ("admin-1", "admin@permitpass.test", "Mwangi Njoroge", Role.admin),
]


def seed_users(session: Session, password: str = DEMO_PASSWORD, iterations: int | None = None) -> None:
    for user_id, email, name, role in DEMO_USERS:
        if session.get(UserRow, user_id) is None:
            session.add(UserRow(id=user_id, email=email, full_name=name, role=role,
                                password_hash=hash_password(password, iterations)))
    session.commit()


if __name__ == "__main__":
    init_db()
    with SessionLocal() as s:
        seed_users(s)
    print(f"Seeded {len(DEMO_USERS)} demo users")
