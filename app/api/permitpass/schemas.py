"""Request and response shapes."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .domain import Role, State


class User(BaseModel):
    id: str
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
    created_at: datetime
    rejection_reason: str | None = None


class ActionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
