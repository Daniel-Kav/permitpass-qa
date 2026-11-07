"""M-Pesa payments: starting an STK push, applying results (callback or query) and sweeping stuck payments.

Every result, whichever way it arrives, goes through apply_result(), so callbacks, STK queries and late
answers follow exactly the same rules.
"""
import hmac
import logging
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock, config
from .audit import record
from .auth import current_user
from .db import SessionLocal, get_db
from .deps import get_mpesa_client
from .domain import SYSTEM_ACTOR_MPESA, TRANSITIONS, Role, State
from .integrations.mpesa import CallbackIn, MpesaClient, MpesaUnavailable, normalise_phone
from .models import ApplicationRow, PaymentRow, UserRow

log = logging.getLogger("permitpass.payments")
router = APIRouter(tags=["payments"])
FINAL = {"succeeded", "failed", "amount_mismatch", "refund_due"}


def start_payment(db: Session, row: ApplicationRow, phone: str, mpesa: MpesaClient) -> PaymentRow:
    """Ask M-Pesa to prompt the citizen's phone. Raises 503 (and changes nothing) if M-Pesa can't be reached."""
    account_ref = secrets.token_hex(6).upper()   # 12 chars, Daraja's AccountReference limit
    try:
        push = mpesa.stk_push(phone, row.fee_kes, account_ref, "Permit fee", config.MPESA_CALLBACK_URL)
    except MpesaUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "M-Pesa is unavailable, please try again later",
                            headers={"Retry-After": "30"}) from None
    payment = PaymentRow(id=str(uuid.uuid4()), application_id=row.id, account_ref=account_ref,
                         checkout_request_id=push.checkout_request_id, phone=normalise_phone(phone),
                         amount=row.fee_kes, status="pending", created_at=clock.now())
    db.add(payment)
    row.payment_note = None
    return payment


def _move(db: Session, app_row: ApplicationRow, action: str, note: str | None, reason: str) -> bool:
    target = TRANSITIONS.get((app_row.state, action))
    if target is None:
        return False
    from_state = app_row.state
    app_row.state, app_row.payment_note = target, note
    record(db, app_row, SYSTEM_ACTOR_MPESA, action, from_state, reason)
    return True


def apply_result(db: Session, payment: PaymentRow, code: int, desc: str, *, paid_amount: int | None,
                 receipt: str | None, via: str) -> str:
    """Apply one M-Pesa outcome to a payment (row must be locked by the caller). Returns what happened."""
    if payment.status in FINAL:
        return "already processed"
    late = payment.status == "expired"
    if late and code != 0:
        return "already processed"            # a late failure changes nothing: we already gave up on it

    app_row = db.get(ApplicationRow, payment.application_id, with_for_update=True)
    payment.result_code, payment.result_desc, payment.completed_at = code, desc, clock.now()

    if code != 0:
        payment.status = "failed"
        _move(db, app_row, "payment_failed", f"Payment failed: {desc} (M-Pesa code {code})",
              f"Payment failed: {desc} (M-Pesa code {code}) [{via}]")
        return "failed"

    payment.paid_amount = paid_amount
    if via == "callback" and (paid_amount != payment.amount or not receipt):
        payment.status = "amount_mismatch"
        msg = f"Amount mismatch: expected KES {payment.amount}, M-Pesa reported {paid_amount}. Flagged for finance review"
        _move(db, app_row, "payment_failed", msg, msg)
        return "amount_mismatch"

    payment.mpesa_receipt = str(receipt) if receipt else None
    proof = f"M-Pesa receipt {receipt}" if receipt else "confirmed by STK query (no receipt in query answers)"
    if _move(db, app_row, "payment_confirmed", None, f"{proof}{' (arrived after expiry)' if late else ''} [{via}]"):
        payment.status = "succeeded"
        return "succeeded"
    # Money arrived but the application no longer needs it (already paid by another attempt, or moved on)
    payment.status = "refund_due"
    record(db, app_row, SYSTEM_ACTOR_MPESA, "payment_refund_due", app_row.state,
           f"{proof}: application was already {app_row.state.value}; refund KES {payment.amount} to {payment.phone}")
    return "refund_due"


ACK = {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/payments/mpesa/callback")
def mpesa_callback(body: CallbackIn, token: str = Query(""), db: Session = Depends(get_db)) -> dict:
    """Called by M-Pesa. Idempotent: a repeated callback for a finished payment changes nothing."""
    if not hmac.compare_digest(token, config.MPESA_CALLBACK_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid callback token")
    cb = body.Body.stkCallback
    payment = db.scalar(
        select(PaymentRow).where(PaymentRow.checkout_request_id == cb.CheckoutRequestID).with_for_update()
    )   # row lock: simultaneous duplicate callbacks (or a callback racing the sweep) run one at a time
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown CheckoutRequestID")
    paid = cb.item("Amount")
    outcome = apply_result(db, payment, cb.ResultCode, cb.ResultDesc,
                           paid_amount=int(paid) if paid is not None else None,
                           receipt=cb.item("MpesaReceiptNumber"), via="callback")
    db.commit()
    return {**ACK, "ResultDesc": "Already processed"} if outcome == "already processed" else ACK


# ---------- the sweep: payments that never got a callback (#30) ----------

@dataclass
class SweepReport:
    checked: int = 0
    outcomes: dict = field(default_factory=dict)

    def add(self, outcome: str):
        self.checked += 1
        self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1


def _expire(db: Session, payment: PaymentRow) -> str:
    payment.status, payment.completed_at = "expired", clock.now()
    app_row = db.get(ApplicationRow, payment.application_id, with_for_update=True)
    minutes = config.PAYMENT_EXPIRE_AFTER_SECONDS // 60
    _move(db, app_row, "payment_failed",
          f"M-Pesa did not confirm this payment within {minutes} minutes. Please try again; if you were charged, "
          "the payment will be matched automatically.",
          f"Payment expired after {minutes} minutes without a result")
    return "expired"


def sweep(db: Session, mpesa: MpesaClient, limit: int = 50) -> SweepReport:
    """Query M-Pesa about payments that have waited too long; expire those that never resolve."""
    now = clock.now()
    report = SweepReport()
    candidates = db.scalars(
        select(PaymentRow)
        .where(PaymentRow.status == "pending",
               PaymentRow.created_at <= now - timedelta(seconds=config.PAYMENT_QUERY_AFTER_SECONDS))
        .order_by(PaymentRow.created_at).limit(limit)
        .with_for_update(skip_locked=True)   # several workers can sweep at once without double-processing
    ).all()
    for payment in candidates:
        age = (now - clock.aware(payment.created_at)).total_seconds()
        try:
            answer = mpesa.stk_query(payment.checkout_request_id)
        except MpesaUnavailable:
            answer = None
        if answer is not None and not answer.processing:
            outcome = apply_result(db, payment, answer.result_code, answer.result_desc,
                                   paid_amount=payment.amount, receipt=None, via="query")
        elif age >= config.PAYMENT_EXPIRE_AFTER_SECONDS:
            outcome = _expire(db, payment)
        else:
            outcome = "still pending"
        report.add(outcome)
    db.commit()
    return report


@router.post("/admin/payments/sweep")
def run_sweep(user: UserRow = Depends(current_user), db: Session = Depends(get_db),
              mpesa: MpesaClient = Depends(get_mpesa_client)) -> dict:
    """Admin: run the sweep now (it also runs in the background every PAYMENT_SWEEP_INTERVAL_SECONDS)."""
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    r = sweep(db, mpesa)
    return {"checked": r.checked, "outcomes": r.outcomes}


@router.get("/admin/payments")
def payments_needing_attention(payment_status: str = Query("refund_due", alias="status"),
                               user: UserRow = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Admin / finance: payments in a given status, e.g. refund_due or amount_mismatch."""
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    rows = db.scalars(select(PaymentRow).where(PaymentRow.status == payment_status).order_by(PaymentRow.created_at)).all()
    return [{"application_id": p.application_id, "checkout_request_id": p.checkout_request_id, "phone": p.phone,
             "amount": p.amount, "status": p.status, "result_desc": p.result_desc} for p in rows]


class BackgroundSweeper:
    """Runs sweep() every N seconds in a daemon thread, for the lifetime of the app."""

    def __init__(self, interval: int):
        self.interval, self._stop = interval, threading.Event()
        self._thread = threading.Thread(target=self._run, name="payment-sweeper", daemon=True)

    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                with SessionLocal() as db:
                    r = sweep(db, get_mpesa_client())
                    from .idempotency import prune
                    prune(db)
                if r.checked:
                    log.info("payment sweep: %s", r.outcomes)
            except Exception:   # never let one bad run kill the sweeper
                log.exception("payment sweep failed")

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
