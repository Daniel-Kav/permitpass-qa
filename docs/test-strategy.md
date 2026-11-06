# PermitPass test strategy

> Status: live, as of v0.3.0.

## Scope
Permit lifecycle, payments (M-Pesa), KRA PIN validation (SOAP), signed certificates and QR verification,
role permissions, data migration, performance, mobile offline sync, accessibility and browser coverage.

## Risk-based priorities
| Risk area | Why it matters | Coverage depth |
| --- | --- | --- |
| Payments | Wrong or double charge; permit issued unpaid | Deepest |
| Certificates and QR | Forged or revoked permit passes verification | Deepest |
| Role permissions | Citizen approves own permit; data leaks between users | Deep |
| Data migration | Lost or duplicated legacy records | Deep |
| Performance | Portal fails at deadline peaks | Targeted |
| Mobile offline sync | Duplicate or lost submissions | Targeted |
| Accessibility, browsers | Citizens locked out | Broad |

## Test levels
Roughly 70% unit/API, 20% integration/contract, 10% E2E by test count.

## Techniques
State-transition testing (lifecycle), decision tables (approval rules), equivalence partitioning
and boundary values (KRA PIN, business name, fees, dates).

## Defect handling
Defects are raised with the issue template and get a severity from `docs/defects/severity.md`. They are fixed on a `fix/` branch,
with the regression test committed first so the PR history shows red → green (example: #13 → #14).

## What runs in CI
| Job | What it proves |
| --- | --- |
| `api-tests (sqlite)`, `api-tests (postgres)` | Rules, roles, auth, audit, certificates, validation on both engines; PostgreSQL runs with a non-UTC session time zone |
| `e2e (chromium / firefox / webkit)` | Browser journeys + axe accessibility against the real Compose stack |
| `perf-smoke` | p95 < 300 ms and < 1% errors under 5 virtual users |

## Integrations
External systems are virtualised with WireMock (). Unit tests use in-process fakes that follow the same
test-data rules; a contract test fails if a fake and its stub ever disagree. KRA and M-Pesa failures **fail closed**:
nothing is stored, and the user gets a clear 503 with .

## Environments
`local` (Docker Compose, seeded) · `ci` (same images, fresh state per job) · optional `staging` on AWS.

## Entry and exit criteria
Entry: build green, seed data loaded, stubs healthy.
Exit (release): no open Critical/High defects; critical-path E2E green; k6 thresholds met;
zero serious axe violations; migration reconciliation exact.
