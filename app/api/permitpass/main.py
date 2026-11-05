"""PermitPass API: a deliberately small permit service used as the system under test.

Lifecycle: draft -> submitted -> paid -> approved -> issued   (or submitted/paid -> rejected)
Roles: citizen (applies, pays), officer (reviews, approves/rejects), admin (manages fees).
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db, init_db, reset_db  # noqa: F401  (reset_db re-exported for tests)
from .domain import ACTION_ROLES, PERMIT_FEE_KES, TRANSITIONS, Role, State
from .models import ApplicationRow
from .schemas import ActionIn, Application, ApplicationIn, User


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="PermitPass API", version="0.2.0", lifespan=lifespan)


def current_user(x_user_id: str = Header(...), x_user_role: Role = Header(...)) -> User:
    """Stand-in auth. Replaced by JWT in #3."""
    return User(id=x_user_id, role=x_user_role)


def _get_visible(db: Session, app_id: str, user: User) -> ApplicationRow:
    row = db.get(ApplicationRow, app_id)
    # Citizens may only see their own applications; answer 404 rather than 403 so ids can't be probed (IDOR)
    if row is None or (user.role == Role.citizen and row.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return row


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/applications", status_code=status.HTTP_201_CREATED, response_model=Application)
def create_application(
    body: ApplicationIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ApplicationRow:
    if user.role != Role.citizen:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only citizens can apply")
    row = ApplicationRow(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        business_name=body.business_name,
        kra_pin=body.kra_pin,
        state=State.draft,
        fee_kes=PERMIT_FEE_KES,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row


@app.get("/applications/{app_id}", response_model=Application)
def get_application(app_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApplicationRow:
    return _get_visible(db, app_id, user)


@app.post("/applications/{app_id}/{action}", response_model=Application)
def act(
    app_id: str,
    action: str,
    body: ActionIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplicationRow:
    if action not in ACTION_ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown action")
    row = _get_visible(db, app_id, user)
    if user.role not in ACTION_ROLES[action]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role.value}' cannot {action}")
    target = TRANSITIONS.get((row.state, action))
    if target is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot {action} an application in state '{row.state.value}'")
    if action == "reject":
        if not body or not body.reason:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A rejection reason is required")
        row.rejection_reason = body.reason
    row.state = target
    db.commit()
    return row
