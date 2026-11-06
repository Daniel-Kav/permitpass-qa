"""Import the legacy CSV export. Each rule below is numbered to match docs/data-migration.md."""
import csv
import re
import secrets
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..audit import record
from ..certificates import new_certificate
from ..domain import PERMIT_FEE_KES, SYSTEM_ACTOR_MIGRATION, Role, State
from ..models import ApplicationRow, UserRow
from ..security import hash_password

EAT = ZoneInfo("Africa/Nairobi")
KRA_PIN = re.compile(r"^[AP]\d{9}[A-Z]$")

# R3: legacy status -> PermitPass state
STATUS_MAP = {"applied": State.submitted, "paid": State.paid, "approved": State.approved,
              "issued": State.issued, "rejected": State.rejected}
PAID_OR_LATER = {State.paid, State.approved, State.issued}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y")   # R4


class RowError(ValueError):
    pass


@dataclass
class Reject:
    line: int
    legacy_id: str
    reason: str
    raw: dict


@dataclass
class MigrationReport:
    rows_read: int = 0
    migrated: int = 0
    already_migrated: int = 0
    duplicates_dropped: int = 0
    users_created: int = 0
    rejected: list[Reject] = field(default_factory=list)
    accepted_ids: set[str] = field(default_factory=set)
    # what the SOURCE says, after cleansing, for the accepted rows (used by reconciliation)
    source_by_state: Counter = field(default_factory=Counter)
    source_fee_total: int = 0
    source_certificates: int = 0

    def as_dict(self) -> dict:
        return {"rows_read": self.rows_read, "migrated": self.migrated, "already_migrated": self.already_migrated,
                "duplicates_dropped": self.duplicates_dropped, "rejected": len(self.rejected),
                "users_created": self.users_created}


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())                       # R1


def _parse_date(value: str, what: str) -> date:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            d = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue
    else:
        raise RowError(f"unparseable {what} {value!r}")
    if d > clock.now().astimezone(EAT).date():
        raise RowError(f"{what} {d} is in the future")
    return d


def _at_eat_midnight(d: date) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=EAT).astimezone(timezone.utc)


def _clean(raw: dict) -> dict:
    """Apply rules R1-R7 to one row. Raises RowError with the reason if the row can't be fixed."""
    legacy_id = _clean_text(raw.get("legacy_id"))
    if not legacy_id:
        raise RowError("missing legacy_id")
    name = _clean_text(raw.get("business_name"))
    if not 2 <= len(name) <= 120:
        raise RowError("missing or invalid business name")
    pin = re.sub(r"\s+", "", raw.get("kra_pin") or "").upper()             # R2
    if not KRA_PIN.match(pin):
        raise RowError(f"invalid KRA PIN {raw.get('kra_pin')!r}")
    email = _clean_text(raw.get("owner_email")).lower()                     # R6
    if "@" not in email:
        raise RowError("missing owner email")
    status = _clean_text(raw.get("status")).lower()
    if status not in STATUS_MAP:
        raise RowError(f"unknown status {raw.get('status')!r}")
    state = STATUS_MAP[status]
    applied = _parse_date(raw.get("applied_on") or "", "applied_on")
    fee_text = (raw.get("fee_paid") or "").replace(",", "").strip()          # R7
    if state in PAID_OR_LATER:
        try:
            fee = int(round(float(fee_text)))
        except ValueError:
            raise RowError(f"status {status} needs a fee, got {raw.get('fee_paid')!r}") from None
        if fee <= 0:
            raise RowError(f"invalid fee {raw.get('fee_paid')!r}")
    else:
        fee = PERMIT_FEE_KES                                                  # unpaid: current price
    issued = None
    if state is State.issued:                                                 # R8
        if not (raw.get("issued_on") or "").strip():
            raise RowError("issued without issued_on")
        issued = _parse_date(raw["issued_on"], "issued_on")
        if issued < applied:
            raise RowError("issued_on before applied_on")
    return {"legacy_id": legacy_id, "business_name": name, "kra_pin": pin, "email": email, "state": state,
            "fee": fee, "applied": applied, "issued": issued}


def _owner(db: Session, email: str, report: MigrationReport) -> UserRow:
    user = db.scalar(select(UserRow).where(UserRow.email == email))
    if user is None:   # R6: placeholder account, inactive until the owner claims it
        user = UserRow(id=f"legacy-{uuid.uuid4().hex[:12]}", email=email, full_name=email.split("@")[0],
                       role=Role.citizen, password_hash=hash_password(secrets.token_urlsafe(24)), is_active=False)
        db.add(user)
        db.flush()
        report.users_created += 1
    return user


def migrate(db: Session, csv_path: str | Path) -> MigrationReport:
    report = MigrationReport()
    seen: dict[str, dict] = {}   # legacy_id -> cleaned row (R5 duplicates)
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for line, raw in enumerate(csv.DictReader(f), start=2):              # line 1 is the header
            report.rows_read += 1
            try:
                row = _clean(raw)
            except RowError as exc:
                report.rejected.append(Reject(line, (raw.get("legacy_id") or "").strip(), str(exc), raw))
                continue
            lid = row["legacy_id"]
            if lid in seen:                                                   # R5
                if seen[lid] == row:
                    report.duplicates_dropped += 1
                else:
                    report.rejected.append(Reject(line, lid, f"conflicting duplicate of {lid}", raw))
                continue
            seen[lid] = row
            report.accepted_ids.add(lid)
            report.source_by_state[row["state"].value] += 1
            if row["state"] in PAID_OR_LATER:
                report.source_fee_total += row["fee"]
            if row["state"] is State.issued:
                report.source_certificates += 1
            if db.scalar(select(ApplicationRow.id).where(ApplicationRow.legacy_id == lid)):
                report.already_migrated += 1                                  # idempotent re-run
                continue
            owner = _owner(db, row["email"], report)
            app = ApplicationRow(id=str(uuid.uuid4()), owner_id=owner.id, business_name=row["business_name"],
                                 kra_pin=row["kra_pin"], state=row["state"], fee_kes=row["fee"],
                                 created_at=_at_eat_midnight(row["applied"]), legacy_id=lid,
                                 rejection_reason="Rejected in the legacy system" if row["state"] is State.rejected else None)
            db.add(app)
            db.flush()
            if row["issued"]:
                db.add(new_certificate(app, issued_at=_at_eat_midnight(row["issued"])))
            record(db, app, SYSTEM_ACTOR_MIGRATION, "migrate", None, f"Imported from legacy {lid} (line {line})")
            report.migrated += 1
    db.commit()
    return report


def write_rejects(report: MigrationReport, path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["line", "legacy_id", "reason"])
        for r in report.rejected:
            w.writerow([r.line, r.legacy_id, r.reason])
