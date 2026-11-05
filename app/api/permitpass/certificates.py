"""Signed permit certificates and public verification.

The signature is an HMAC-SHA256 over the certificate's content, so changing any signed field
(or presenting a signature from another certificate) makes verification fail.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from enum import Enum

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import clock, config
from .db import get_db
from .models import ApplicationRow, CertificateRow

VALIDITY = timedelta(days=365)
router = APIRouter(tags=["certificates"])


class VerifyStatus(str, Enum):
    valid = "valid"
    invalid = "invalid"   # unknown number or bad signature: deliberately indistinguishable
    revoked = "revoked"
    expired = "expired"


class VerifyOut(BaseModel):
    status: VerifyStatus
    number: str | None = None
    business_name: str | None = None
    expires_at: str | None = None


def _payload(c: CertificateRow) -> bytes:
    fields = [c.number, c.application_id, c.business_name,
              str(int(clock.aware(c.issued_at).timestamp())), str(int(clock.aware(c.expires_at).timestamp()))]
    return "|".join(fields).encode()


def sign(c: CertificateRow) -> str:
    mac = hmac.new(config.CERT_SECRET.encode(), _payload(c), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def new_certificate(application: ApplicationRow) -> CertificateRow:
    issued = clock.now().replace(microsecond=0)
    cert = CertificateRow(
        number=f"PP-{issued.year}-{secrets.token_hex(4).upper()}",
        application_id=application.id,
        business_name=application.business_name,
        issued_at=issued,
        expires_at=issued + VALIDITY,
    )
    cert.signature = sign(cert)
    return cert


def status_of(cert: CertificateRow | None, sig: str) -> VerifyStatus:
    if cert is None or not hmac.compare_digest(sign(cert), sig):
        return VerifyStatus.invalid
    if cert.revoked_at is not None:
        return VerifyStatus.revoked  # revocation wins over expiry
    if clock.now() >= clock.aware(cert.expires_at):
        return VerifyStatus.expired
    return VerifyStatus.valid


@router.get("/verify/{number}", response_model=VerifyOut, response_model_exclude_none=True)
def verify(number: str, sig: str = Query(..., max_length=128), db: Session = Depends(get_db)) -> VerifyOut:
    """Public: no login. Reveals only what is printed on the certificate, and only for a genuine one."""
    cert = db.get(CertificateRow, number)
    result = status_of(cert, sig)
    if result is VerifyStatus.invalid:
        return VerifyOut(status=result)
    return VerifyOut(status=result, number=cert.number, business_name=cert.business_name,
                     expires_at=clock.aware(cert.expires_at).isoformat())
