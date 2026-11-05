"""Database tables."""
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .domain import Role, State


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    business_name: Mapped[str] = mapped_column(String(120))
    kra_pin: Mapped[str] = mapped_column(String(11))
    state: Mapped[State] = mapped_column(Enum(State, name="application_state"), index=True)
    fee_kes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
