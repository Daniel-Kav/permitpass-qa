# Legacy data migration

Brings permit records from the legacy system's CSV export into PermitPass, then **proves** with SQL that nothing
was lost, duplicated or changed on the way.

```bash
# inside the API container or a venv with app/api on the path
python -m permitpass.migrate_legacy data-migration/legacy/permits_export.csv --rejects rejects.csv
# or: make migrate-demo   (runs against the Compose database)
```

Exit code is **0 only if every reconciliation check passes**, so it can gate a cut-over script.

## Cleansing rules

| Rule | What happens | Rejected when |
| --- | --- | --- |
| R1 | Trim whitespace; collapse inner runs of spaces in names | business name < 2 or > 120 chars |
| R2 | KRA PIN: remove spaces, upper-case | still not `[AP]` + 9 digits + letter |
| R3 | Status mapped case-insensitively: APPLIED→submitted, PAID→paid, APPROVED→approved, ISSUED→issued, REJECTED→rejected | any other status |
| R4 | Dates accepted as `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-Mon-YYYY`; stored as 00:00 Nairobi time | unparseable or in the future |
| R5 | Exact duplicate rows are dropped (and counted) | same `legacy_id` with *different* data: the later row is rejected as a conflicting duplicate |
| R6 | Owner matched by email (case-insensitive); unknown owners get an **inactive** placeholder citizen account to claim later | no email |
| R7 | Fee `2,500` / `2500.00` → 2500; historic prices kept (e.g. KES 2,000 in 2023). Unpaid rows get the current fee | paid-or-later status with a missing, zero or negative fee |
| R8 | Issued rows get a signed certificate dated from `issued_on` (so old permits verify as *expired*) | issued without `issued_on`, or issued before applied |
| – | Missing `legacy_id` | always rejected |

Every rejected row goes to the rejects file with its **line number, legacy id and reason**. KRA PINs are *not*
re-checked live during migration (they were validated by the legacy system); re-verification is a separate batch.

## Idempotency
Each migrated application keeps its `legacy_id` (unique). Re-running the same file migrates **0** new rows and
reports them as `already_migrated`, so a failed cut-over can simply be re-run.

## Reconciliation (`app/api/permitpass/migration/reconciliation.sql`)

| Check | Proves |
| --- | --- |
| source rows = accepted + rejected + duplicates | every source row is accounted for |
| accepted rows = migrated applications | nothing lost or added |
| per-state counts match the source | statuses mapped correctly |
| fee total (paid or later) matches the source | money figures intact |
| no duplicate legacy ids | no double import |
| issued rows = migrated certificates; every issued application has a certificate | permits usable |
| no orphan certificates; every application has an owner | referential integrity |
| every migrated application has a `migrate` audit event | traceability |

Tests deliberately **break** the data after migrating (delete a certificate, change a fee, delete a row) and assert
that exactly the right checks fail, so the checks are known to catch real problems.

## Fixture with known answers
`data-migration/legacy/permits_export.csv`: 25 rows → **12 migrated, 12 rejected (one per rule), 1 duplicate
dropped**; 5 issued, 2 approved, 2 paid, 2 submitted, 1 rejected; fee total KES 22,000.
