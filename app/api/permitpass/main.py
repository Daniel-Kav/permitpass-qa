"""PermitPass API: a deliberately small permit service used as the system under test.

Lifecycle: draft -> submitted -> paid -> approved -> issued   (or submitted/paid -> rejected)
Roles: citizen (applies, pays), officer (reviews, approves/rejects), admin (manages fees).

Storage is in-memory for the week-1 skeleton; PostgreSQL replaces it in week 1/2.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="PermitPass API", version="0.1.0")


class Role(str, Enum):
    citizen = "citizen"
    officer = "officer"
    admin = "admin"


class State(str, Enum):
    draft = "draft"
    submitted = "submitted"
    paid = "paid"
    approved = "approved"
    issued = "issued"
    rejected = "rejected"


# Allowed transitions: (from_state, action) -> to_state
TRANSITIONS: dict[tuple[State, str], State] = {
    (State.draft, "submit"): State.submitted,
    (State.submitted, "pay"): State.paid,
    (State.paid, "approve"): State.approved,
    (State.submitted, "reject"): State.rejected,
    (State.paid, "reject"): State.rejected,
    (State.approved, "issue"): State.issued,
}

# Which role may perform which action
ACTION_ROLES: dict[str, set[Role]] = {
    "submit": {Role.citizen},
    "pay": {Role.citizen},
    "approve": {Role.officer},
    "reject": {Role.officer},
    "issue": {Role.officer},
}

PERMIT_FEE_KES = 2500


class User(BaseModel):
    id: str
    role: Role


class ApplicationIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    kra_pin: str = Field(pattern=r"^[AP]\d{9}[A-Z]$")


class Application(BaseModel):
    id: str
    owner_id: str
    business_name: str
    kra_pin: str
    state: State
    fee_kes: int
    created_at: datetime
    rejection_reason: str | None = None


_DB: dict[str, Application] = {}


def current_user(x_user_id: str = Header(...), x_user_role: Role = Header(...)) -> User:
    """Stand-in auth for the skeleton. Replaced by JWT in week 2."""
    return User(id=x_user_id, role=x_user_role)


def _get_visible(app_id: str, user: User) -> Application:
    application = _DB.get(app_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    # Citizens may only see their own applications (prevents IDOR)
    if user.role == Role.citizen and application.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/applications", status_code=status.HTTP_201_CREATED, response_model=Application)
def create_application(body: ApplicationIn, user: User = Depends(current_user)) -> Application:
    if user.role != Role.citizen:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only citizens can apply")
    application = Application(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        business_name=body.business_name,
        kra_pin=body.kra_pin,
        state=State.draft,
        fee_kes=PERMIT_FEE_KES,
        created_at=datetime.now(timezone.utc),
    )
    _DB[application.id] = application
    return application


@app.get("/applications/{app_id}", response_model=Application)
def get_application(app_id: str, user: User = Depends(current_user)) -> Application:
    return _get_visible(app_id, user)


class ActionIn(BaseModel):
    reason: str | None = None


@app.post("/applications/{app_id}/{action}", response_model=Application)
def act(app_id: str, action: str, body: ActionIn | None = None, user: User = Depends(current_user)) -> Application:
    if action not in ACTION_ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown action")
    application = _get_visible(app_id, user)
    if user.role not in ACTION_ROLES[action]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role.value}' cannot {action}")
    if user.role == Role.citizen and application.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    target = TRANSITIONS.get((application.state, action))
    if target is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot {action} an application in state '{application.state.value}'",
        )
    if action == "reject":
        if not body or not body.reason:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A rejection reason is required")
        application.rejection_reason = body.reason
    application.state = target
    return application


def reset_db() -> None:
    """Test helper: clear all data so every test starts from a known state."""
    _DB.clear()
