"""Database tables."""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
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
    payment_note: Mapped[str | None] = mapped_column(String(300), nullable=True)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)


class AuditEventRow(Base):
    """Append-only record of who did what to an application."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    from_state: Mapped[State | None] = mapped_column(Enum(State, name="application_state"), nullable=True)
    to_state: Mapped[State] = mapped_column(Enum(State, name="application_state"))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CertificateRow(Base):
    __tablename__ = "certificates"

    number: Mapped[str] = mapped_column(String(20), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True)
    business_name: Mapped[str] = mapped_column(String(120))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signature: Mapped[str] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PaymentRow(Base):
    """One STK push attempt. An application can have several (e.g. after a cancelled one)."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    account_ref: Mapped[str] = mapped_column(String(12), unique=True)           # Daraja AccountReference (max 12)
    checkout_request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(12))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|succeeded|failed|amount_mismatch
    result_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_desc: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    paid_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
