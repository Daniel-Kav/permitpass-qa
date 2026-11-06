"""Run reconciliation.sql and compare every number with what the source file says."""
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from .importer import MigrationReport

SQL = Path(__file__).with_name("reconciliation.sql").read_text()


def _queries() -> dict[str, str]:
    parts = re.split(r"^-- name: (\w+)\s*$", SQL, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


QUERIES = _queries()


@dataclass(frozen=True)
class Check:
    name: str
    expected: object
    actual: object

    @property
    def ok(self) -> bool:
        return self.expected == self.actual


def reconcile(db: Session, report: MigrationReport) -> list[Check]:
    one = lambda q: db.execute(text(QUERIES[q])).scalar_one()  # noqa: E731
    by_state = {s.value if hasattr(s, "value") else s: n for s, n in db.execute(text(QUERIES["migrated_by_state"])).all()}
    return [
        Check("source rows = accepted + rejected + duplicates",
              report.rows_read, len(report.accepted_ids) + len(report.rejected) + report.duplicates_dropped),
        Check("accepted rows = migrated applications", len(report.accepted_ids), one("migrated_applications")),
        Check("per-state counts match the source", dict(report.source_by_state), by_state),
        Check("fee total (paid or later) matches the source", report.source_fee_total, one("migrated_fee_total")),
        Check("no duplicate legacy ids", 0, one("duplicate_legacy_ids")),
        Check("issued rows = migrated certificates", report.source_certificates, one("migrated_certificates")),
        Check("every issued application has a certificate", 0, one("issued_without_certificate")),
        Check("no orphan certificates", 0, one("orphan_certificates")),
        Check("every application has an owner", 0, one("applications_without_owner")),
        Check("every migrated application has a 'migrate' audit event", 0, one("migrated_without_audit")),
    ]
