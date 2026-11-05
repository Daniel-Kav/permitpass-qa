"""Request and response shapes."""
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from . import clock

from .domain import Role, State

# Every datetime leaves the API as UTC with an explicit offset (SQLite hands back naive values; see #13)
UTCDateTime = Annotated[datetime, AfterValidator(clock.aware)]


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: Role


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: Role


class ApplicationIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    kra_pin: str = Field(pattern=r"^[AP]\d{9}[A-Z]$")


class Application(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    business_name: str
    kra_pin: str
    state: State
    fee_kes: int
    created_at: UTCDateTime
    rejection_reason: str | None = None


class ActionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: str
    action: str
    from_state: State | None
    to_state: State
    reason: str | None
    at: UTCDateTime


class ApplicationPage(BaseModel):
    items: list[Application]
    total: int
    limit: int
    offset: int


class Certificate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: str
    business_name: str
    issued_at: UTCDateTime
    expires_at: UTCDateTime
    signature: str
    revoked_at: UTCDateTime | None
    revoked_reason: str | None
    verify_url: str
