# PermitPass test strategy

> Status: draft (week 1). Finalised in week 2.

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

## Environments
`local` (Docker Compose, seeded) · `ci` (same images, fresh state per job) · optional `staging` on AWS.

## Entry and exit criteria
Entry: build green, seed data loaded, stubs healthy.
Exit (release): no open Critical/High defects; critical-path E2E green; k6 thresholds met;
zero serious axe violations; migration reconciliation exact.
