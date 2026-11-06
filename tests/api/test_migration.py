"""Legacy data migration: cleansing rules, rejects, idempotency and SQL reconciliation.

The fixture (data-migration/legacy/permits_export.csv) has 25 rows with known answers:
12 migrate, 12 are rejected (one per rule), 1 exact duplicate is dropped. Traceability: US-14.
"""
from pathlib import Path

import pytest
from sqlalchemy import select

from conftest import CITIZEN, OFFICER

from permitpass import clock
from permitpass.db import SessionLocal
from permitpass.migration import migrate, reconcile
from permitpass.migration.importer import write_rejects
from permitpass.models import ApplicationRow, CertificateRow, UserRow

FIXTURE = Path(__file__).resolve().parents[2] / "data-migration" / "legacy" / "permits_export.csv"

EXPECTED_REJECTS = {
    "L-1008": "invalid KRA PIN 'B123456789Z'",
    "L-1009": "invalid KRA PIN 'A12345678Z'",
    "L-1010": "unknown status 'PENDING_REVIEW'",
    "L-1011": "unparseable applied_on 'sometime in 2025'",
    "L-1012": "applied_on 2031-01-01 is in the future",
    "L-1013": "status paid needs a fee, got ''",
    "L-1014": "issued without issued_on",
    "L-1015": "missing or invalid business name",
    "L-1017": "conflicting duplicate of L-1017",
    "L-1019": "invalid fee '-2500'",
    "L-1020": "missing owner email",
    "": "missing legacy_id",
}


@pytest.fixture
def migrated(client):
    with SessionLocal() as db:
        report = migrate(db, FIXTURE)
    return report


def _app(legacy_id) -> ApplicationRow:
    with SessionLocal() as db:
        return db.scalar(select(ApplicationRow).where(ApplicationRow.legacy_id == legacy_id))


def test_counts(migrated):
    assert migrated.as_dict() == {"rows_read": 25, "migrated": 12, "already_migrated": 0,
                                  "duplicates_dropped": 1, "rejected": 12, "users_created": 2}


def test_every_reject_has_the_right_reason(migrated):
    assert {r.legacy_id: r.reason for r in migrated.rejected} == EXPECTED_REJECTS


def test_rejects_file(migrated, tmp_path):
    out = tmp_path / "rejects.csv"
    write_rejects(migrated, out)
    lines = out.read_text().splitlines()
    assert lines[0] == "line,legacy_id,reason" and len(lines) == 13
    assert "9,L-1008,invalid KRA PIN 'B123456789Z'" in lines


def test_reconciliation_passes(migrated):
    with SessionLocal() as db:
        checks = reconcile(db, migrated)
    failed = [(c.name, c.expected, c.actual) for c in checks if not c.ok]
    assert not failed, failed
    assert len(checks) == 10


# ---------- cleansing rules ----------

def test_r1_r2_r7_whitespace_case_and_fee_formats_are_cleaned(migrated):
    a = _app("L-1002")   # "  Kibanda   Coffee House ", a051234567k, "2,500", 15/03/2025
    assert (a.business_name, a.kra_pin, a.fee_kes, a.state.value) == ("Kibanda Coffee House", "A051234567K", 2500, "issued")


def test_r2_spaces_inside_the_pin_are_removed(migrated):
    assert _app("L-1004").kra_pin == "A123456789B"


@pytest.mark.parametrize("legacy_id,iso_utc", [
    ("L-1001", "2025-01-14T21:00:00"),   # 2025-01-15 00:00 EAT
    ("L-1002", "2025-03-14T21:00:00"),   # DD/MM/YYYY
    ("L-1004", "2025-07-09T21:00:00"),   # DD-Mon-YYYY
])
def test_r4_all_date_formats_become_eat_midnight(migrated, legacy_id, iso_utc):
    assert clock.aware(_app(legacy_id).created_at).replace(tzinfo=None).isoformat() == iso_utc


def test_r6_unknown_owners_get_an_inactive_placeholder_account(migrated):
    with SessionLocal() as db:
        user = db.scalar(select(UserRow).where(UserRow.email == "newtrader@example.co.ke"))
        assert user is not None and not user.is_active and user.role.value == "citizen"
        owned = db.scalars(select(ApplicationRow.legacy_id).where(ApplicationRow.owner_id == user.id)).all()
    assert sorted(owned) == ["L-1005", "L-1006"]


def test_r6_existing_owners_are_matched_case_insensitively(migrated, client):
    mine = client.get("/applications", headers=CITIZEN).json()["items"]
    assert {"Mama Mboga Groceries", "Kibanda Coffee House", "Old Price Traders"} <= {a["business_name"] for a in mine}


def test_r7_historic_fee_is_kept(migrated):
    assert _app("L-1007").fee_kes == 2000


def test_r8_issued_rows_get_certificates_dated_from_the_legacy_issue_date(migrated, client):
    a = _app("L-1022")   # issued 2024-11-15 -> expired by now
    cert = client.get(f"/applications/{a.id}/certificate", headers=OFFICER).json()
    assert cert["issued_at"].startswith("2024-11-14T21:00:00")
    verdict = client.get(f"/verify/{cert['number']}", params={"sig": cert["signature"]}).json()
    assert verdict["status"] == "expired"


def test_migrated_rejection_keeps_a_reason(migrated):
    assert _app("L-1006").rejection_reason == "Rejected in the legacy system"


def test_migration_is_audited(migrated, client):
    a = _app("L-1003")
    [event] = client.get(f"/applications/{a.id}/history", headers=OFFICER).json()
    assert (event["action"], event["actor_id"], event["to_state"]) == ("migrate", "system:migration", "approved")
    assert "legacy L-1003" in event["reason"]


# ---------- idempotency ----------

def test_rerunning_the_import_changes_nothing(migrated):
    with SessionLocal() as db:
        second = migrate(db, FIXTURE)
        checks = reconcile(db, second)
        total = db.query(ApplicationRow).count()
    assert (second.migrated, second.already_migrated, second.users_created) == (0, 12, 0)
    assert total == 12
    assert all(c.ok for c in checks)


# ---------- the reconciliation really catches problems ----------

def _failing(report) -> set[str]:
    with SessionLocal() as db:
        return {c.name for c in reconcile(db, report) if not c.ok}


def test_reconciliation_catches_a_lost_certificate(migrated):
    with SessionLocal() as db:
        db.delete(db.scalars(select(CertificateRow)).first())
        db.commit()
    assert _failing(migrated) == {"issued rows = migrated certificates", "every issued application has a certificate"}


def test_reconciliation_catches_a_changed_fee(migrated):
    with SessionLocal() as db:
        db.scalar(select(ApplicationRow).where(ApplicationRow.legacy_id == "L-1001")).fee_kes = 25000
        db.commit()
    assert _failing(migrated) == {"fee total (paid or later) matches the source"}


def test_reconciliation_catches_a_lost_row(migrated):
    with SessionLocal() as db:
        db.delete(db.scalar(select(ApplicationRow).where(ApplicationRow.legacy_id == "L-1021")))
        db.commit()
    assert _failing(migrated) == {"accepted rows = migrated applications", "per-state counts match the source"}


def test_cli_exit_code_and_rejects_file(client, tmp_path, capsys):
    from permitpass.migrate_legacy import main
    rejects = tmp_path / "r.csv"
    assert main([str(FIXTURE), "--rejects", str(rejects)]) == 0
    out = capsys.readouterr().out
    assert out.count("[PASS]") == 10 and "[FAIL]" not in out
    assert rejects.exists()
