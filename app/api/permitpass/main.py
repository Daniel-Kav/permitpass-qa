"""PermitPass API: a deliberately small permit service used as the system under test.

Lifecycle: draft -> submitted -> paid -> approved -> issued   (or submitted/paid -> rejected)
Roles: citizen (applies, pays), officer (reviews, approves/rejects), admin (manages fees).
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import clock, config
from .certificates import new_certificate
from .certificates import router as certificates_router
from .auth import current_user
from .auth import router as auth_router
from .audit import record
from .deps import get_kra_client, get_mpesa_client
from .integrations.mpesa import MpesaClient
from .payments import router as payments_router
from .payments import start_payment
from .integrations.kra import KraClient, KraUnavailable, PinStatus
from .db import SessionLocal, get_db, init_db, reset_db  # noqa: F401  (reset_db re-exported for tests)
from .domain import ACTION_ROLES, PERMIT_FEE_KES, REASON_REQUIRED, TRANSITIONS, Role, State
from .models import ApplicationRow, AuditEventRow, CertificateRow, PaymentRow, UserRow
from .security_headers import SecurityHeadersMiddleware
from .schemas import ActionIn, Application, ApplicationIn, ApplicationPage, AuditEvent, Certificate, Payment


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if config.SEED_DEMO_USERS:
        from .seed import seed_users

        with SessionLocal() as session:
            seed_users(session)
    yield


app = FastAPI(title="PermitPass API", version="0.2.0", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth_router)
app.include_router(certificates_router)
app.include_router(payments_router)


def _get_visible(db: Session, app_id: str, user: UserRow, lock: bool = False) -> ApplicationRow:
    # lock=True: SELECT ... FOR UPDATE, so concurrent transitions on one application run one after another (#34)
    row = db.get(ApplicationRow, app_id, with_for_update=lock)
    # Citizens may only see their own applications; answer 404 rather than 403 so ids can't be probed (IDOR)
    if row is None or (user.role == Role.citizen and row.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return row


def _record(db: Session, row: ApplicationRow, actor: UserRow, action: str,
            from_state: State | None, reason: str | None = None) -> None:
    record(db, row, actor.id, action, from_state, reason)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/applications", status_code=status.HTTP_201_CREATED, response_model=Application)
def create_application(
    body: ApplicationIn,
    user: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
    kra: KraClient = Depends(get_kra_client),
) -> ApplicationRow:
    if user.role != Role.citizen:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only citizens can apply")
    try:
        check = kra.validate_pin(body.kra_pin)
    except KraUnavailable:
        # Fail closed: never store an application whose PIN we could not verify
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "KRA service unavailable, please try again later",
                            headers={"Retry-After": "30"}) from None
    if check.status is PinStatus.not_found:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "KRA PIN is not registered")
    if check.status is PinStatus.inactive:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "KRA PIN is not active")
    row = ApplicationRow(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        business_name=body.business_name,
        kra_pin=body.kra_pin,
        state=State.draft,
        fee_kes=PERMIT_FEE_KES,
        created_at=clock.now(),
    )
    db.add(row)
    db.flush()
    _record(db, row, user, "create", None, f"KRA PIN verified: {check.status.value}")
    db.commit()
    return row


@app.get("/applications", response_model=ApplicationPage)
def list_applications(
    state: State | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplicationPage:
    query = select(ApplicationRow)
    if user.role == Role.citizen:
        query = query.where(ApplicationRow.owner_id == user.id)
    if state is not None:
        query = query.where(ApplicationRow.state == state)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(ApplicationRow.created_at.desc(), ApplicationRow.id).limit(limit).offset(offset)
    ).all()
    return ApplicationPage(items=rows, total=total, limit=limit, offset=offset)


@app.get("/applications/{app_id}", response_model=Application)
def get_application(app_id: str, user: UserRow = Depends(current_user), db: Session = Depends(get_db)) -> ApplicationRow:
    return _get_visible(db, app_id, user)


@app.post("/applications/{app_id}/{action}", response_model=Application)
def act(
    app_id: str,
    action: str,
    body: ActionIn | None = None,
    user: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
    mpesa: MpesaClient = Depends(get_mpesa_client),
) -> ApplicationRow:
    if action not in ACTION_ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown action")
    row = _get_visible(db, app_id, user, lock=True)   # held until commit: the next request sees the new state
    if user.role not in ACTION_ROLES[action]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role.value}' cannot {action}")
    target = TRANSITIONS.get((row.state, action))
    if target is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot {action} an application in state '{row.state.value}'")
    reason = body.reason if body else None
    if action in REASON_REQUIRED and not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"A reason is required to {action}")
    if action == "pay":
        if not body or not body.phone:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "An M-Pesa phone number is required to pay")
        start_payment(db, row, body.phone, mpesa)
        reason = "STK push sent to M-Pesa"
    elif action == "reject":
        row.rejection_reason = reason
    elif action == "issue":
        db.add(new_certificate(row))
    elif action == "revoke":
        cert = _certificate_for(db, row.id)
        cert.revoked_at, cert.revoked_reason = clock.now(), reason
    from_state = row.state
    row.state = target
    _record(db, row, user, action, from_state, reason)
    db.commit()
    return row


@app.get("/applications/{app_id}/history", response_model=list[AuditEvent])
def history(app_id: str, user: UserRow = Depends(current_user), db: Session = Depends(get_db)) -> list[AuditEventRow]:
    _get_visible(db, app_id, user)
    return db.scalars(
        select(AuditEventRow).where(AuditEventRow.application_id == app_id).order_by(AuditEventRow.id)
    ).all()


def _certificate_for(db: Session, app_id: str) -> CertificateRow:
    cert = db.scalar(select(CertificateRow).where(CertificateRow.application_id == app_id))
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No certificate for this application")
    return cert


@app.get("/applications/{app_id}/certificate", response_model=Certificate)
def get_certificate(app_id: str, user: UserRow = Depends(current_user), db: Session = Depends(get_db)) -> Certificate:
    _get_visible(db, app_id, user)
    cert = _certificate_for(db, app_id)
    return Certificate.model_validate(
        {**{c: getattr(cert, c) for c in Certificate.model_fields if c != "verify_url"},
         "verify_url": f"/verify/{cert.number}?sig={cert.signature}"}
    )


@app.get("/applications/{app_id}/payments", response_model=list[Payment])
def list_payments(app_id: str, user: UserRow = Depends(current_user), db: Session = Depends(get_db)) -> list[PaymentRow]:
    _get_visible(db, app_id, user)
    return db.scalars(select(PaymentRow).where(PaymentRow.application_id == app_id).order_by(PaymentRow.created_at)).all()


# Web portal: mounted last so every API route above takes precedence
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
