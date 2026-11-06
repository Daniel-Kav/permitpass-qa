-- Reconciliation queries. Each returns one number; reconcile.py compares it with the source.
-- Plain SQL that runs unchanged on PostgreSQL and SQLite.

-- name: migrated_applications
SELECT COUNT(*) FROM applications WHERE legacy_id IS NOT NULL;

-- name: migrated_by_state
SELECT state, COUNT(*) FROM applications WHERE legacy_id IS NOT NULL GROUP BY state;

-- name: migrated_fee_total
SELECT COALESCE(SUM(fee_kes), 0) FROM applications
WHERE legacy_id IS NOT NULL AND state IN ('paid', 'approved', 'issued');

-- name: duplicate_legacy_ids
SELECT COUNT(*) FROM (SELECT legacy_id FROM applications WHERE legacy_id IS NOT NULL
                      GROUP BY legacy_id HAVING COUNT(*) > 1) d;

-- name: migrated_certificates
SELECT COUNT(*) FROM certificates c JOIN applications a ON a.id = c.application_id WHERE a.legacy_id IS NOT NULL;

-- name: issued_without_certificate
SELECT COUNT(*) FROM applications a LEFT JOIN certificates c ON c.application_id = a.id
WHERE a.state = 'issued' AND c.number IS NULL;

-- name: orphan_certificates
SELECT COUNT(*) FROM certificates c LEFT JOIN applications a ON a.id = c.application_id WHERE a.id IS NULL;

-- name: applications_without_owner
SELECT COUNT(*) FROM applications a LEFT JOIN users u ON u.id = a.owner_id WHERE u.id IS NULL;

-- name: migrated_without_audit
SELECT COUNT(*) FROM applications a
WHERE a.legacy_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM audit_events e WHERE e.application_id = a.id AND e.action = 'migrate');
