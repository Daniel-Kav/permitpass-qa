"""Database tables."""
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .domain import State


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
