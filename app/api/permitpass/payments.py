"""M-Pesa payments: starting an STK push and processing the result callback."""
import hmac
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock, config
from .audit import record
from .db import get_db
from .domain import SYSTEM_ACTOR_MPESA, TRANSITIONS, State
from .integrations.mpesa import CallbackIn, MpesaClient, MpesaUnavailable, normalise_phone
from .models import ApplicationRow, PaymentRow

router = APIRouter(tags=["payments"])


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


ACK = {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/payments/mpesa/callback")
def mpesa_callback(body: CallbackIn, token: str = Query(""), db: Session = Depends(get_db)) -> dict:
    """Called by M-Pesa. Idempotent: a repeated callback for a finished payment changes nothing."""
    if not hmac.compare_digest(token, config.MPESA_CALLBACK_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid callback token")
    cb = body.Body.stkCallback
    payment = db.scalar(
        select(PaymentRow).where(PaymentRow.checkout_request_id == cb.CheckoutRequestID).with_for_update()
    )   # row lock: two simultaneous duplicate callbacks are processed one after the other (PostgreSQL)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown CheckoutRequestID")
    if payment.status != "pending":
        return {**ACK, "ResultDesc": "Already processed"}

    app_row = db.get(ApplicationRow, payment.application_id)
    payment.result_code, payment.result_desc, payment.completed_at = cb.ResultCode, cb.ResultDesc, clock.now()
    from_state = app_row.state

    if cb.ResultCode == 0:
        paid = cb.item("Amount")
        receipt = cb.item("MpesaReceiptNumber")
        payment.paid_amount = int(paid) if paid is not None else None
        if payment.paid_amount == payment.amount and receipt:
            payment.status, payment.mpesa_receipt = "succeeded", str(receipt)
            action, note = "payment_confirmed", None
            reason = f"M-Pesa receipt {receipt}"
        else:
            payment.status = "amount_mismatch"
            action = "payment_failed"
            note = reason = f"Amount mismatch: expected KES {payment.amount}, M-Pesa reported {paid}. Flagged for finance review"
    else:
        payment.status = "failed"
        action = "payment_failed"
        note = reason = f"Payment failed: {cb.ResultDesc} (M-Pesa code {cb.ResultCode})"

    target = TRANSITIONS.get((app_row.state, action))
    if target is not None:   # application still waiting for this payment
        app_row.state = target
        app_row.payment_note = note
        record(db, app_row, SYSTEM_ACTOR_MPESA, action, from_state, reason)
    db.commit()
    return ACK
