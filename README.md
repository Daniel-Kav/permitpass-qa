# PermitPass QA

A hands-on QA portfolio built around **PermitPass**, a small permit-application service (Kenyan business permits:
KRA PIN validation, M-Pesa payment, officer approval, signed certificates). The app is deliberately small; the
**test system around it** is the point.

**v0.2.0 at a glance:** 164 API tests (run on SQLite *and* PostgreSQL) · 17 browser tests × 4 browsers ·
axe accessibility scans on every page · k6 performance gate · every change through issue → branch → PR → CI → merge.

[![CI](https://github.com/Daniel-Kav/permitpass-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/Daniel-Kav/permitpass-qa/actions/workflows/ci.yml)

## The portal

| Citizen | Officer |
| --- | --- |
| ![Citizen applications](docs/screenshots/citizen.png) | ![Officer queue with a rejection reason](docs/screenshots/officer.png) |
| **Log in** | **Public verification** |
| ![Login](docs/screenshots/login.png) | ![Verify a permit](docs/screenshots/verify.png) |

## Quick start

```bash
pip install -r tests/api/requirements.txt
make test-api        # API tests on in-memory SQLite, no Docker needed
DATABASE_URL=postgresql+psycopg://user:pass@localhost/db make test-api   # same suite on PostgreSQL

make up              # API + PostgreSQL 16 + WireMock (Docker), portal at http://localhost:8000
make test-e2e        # Playwright on Chromium, Firefox, WebKit and Pixel 7
make perf-smoke      # k6 (needs k6 installed)
```

## What's covered, and where

| QA skill | Where it lives | Status |
| --- | --- | --- |
| Test strategy, risk-based planning | `docs/test-strategy.md` | Live |
| Requirements traceability | `docs/traceability.csv` | Live |
| State-transition testing (permit lifecycle) | `tests/api/test_lifecycle.py` | Done |
| Role-based access + IDOR checks | `tests/api/test_rbac.py` | Done |
| Authentication + token attacks (expired, forged, `alg: none`) | `tests/api/test_auth.py` | Done |
| Audit trail, listing and pagination boundaries | `tests/api/test_audit.py`, `test_listing.py` | Done |
| Signed certificates: decision table, expiry boundary, tamper tests | `tests/api/test_certificates.py` | Done |
| Equivalence partitioning / boundary values | `tests/api/test_validation.py` | Done |
| Service virtualisation: KRA SOAP, M-Pesa Daraja with callback webhooks | `mocks/` | Done |
| Contract tests: real clients vs stubs, zero unmatched requests, fakes == stubs | `tests/contract/` | Done |
| Web E2E (Page Object Model), cross-browser, accessibility (axe, WCAG 2.1 AA) | `tests/e2e/` | Done |
| Mobile (Expo + Maestro, offline sync) | `app/mobile/`, `tests/mobile/` | v0.3.0 |
| Performance: smoke gate, load / stress / soak with service levels | `perf/`, [`docs/perf/`](docs/perf/README.md) | Done: found #34 and #36 |
| Security: auth/token attacks, IDOR, tamper tests | `tests/api/` | Done |
| Security (OWASP ZAP baseline) | CI | v0.3.0 |
| Data migration: cleansing rules, rejects, idempotency, SQL reconciliation | `data-migration/`, [`docs/data-migration.md`](docs/data-migration.md) | Done |
| Defect management | `.github/ISSUE_TEMPLATE/`, `docs/defects/` | In use: see [#13](https://github.com/Daniel-Kav/permitpass-qa/issues/13) → [#14](https://github.com/Daniel-Kav/permitpass-qa/pull/14) |
| UAT: 12 scripts (★ must-pass), entry/exit criteria, sign-off, data seed | [`docs/uat/`](docs/uat/README.md), `scripts/seed_uat.py` | Done |
| CI/CD quality gates | `.github/workflows/ci.yml` | Live: API × 2 DBs, E2E × 3 browsers, perf |
| Bash automation | `scripts/`, `Makefile` | Live |

## Demo users (local only)

`make up` seeds these accounts (`SEED_DEMO_USERS=true`, never in a real environment). Password for all: `PermitPass!2026`.

| Email | Role |
| --- | --- |
| citizen@permitpass.test | citizen |
| citizen2@permitpass.test | citizen |
| officer@permitpass.test | officer |
| admin@permitpass.test | admin |

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"citizen@permitpass.test","password":"PermitPass!2026"}' | jq -r .access_token)
curl -s localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

## Permit lifecycle

```
draft --submit--> submitted --pay--> payment_pending --(M-Pesa callback)--> paid --approve--> approved --issue--> issued --revoke--> revoked
                      |  ^                    |
                      |  +--- cancelled / failed / wrong amount
                      +----reject (from submitted or paid) ---> rejected   (officer, reason required)
```

| Action | Citizen | Officer | Admin |
| --- | --- | --- | --- |
| create / submit / pay | ✅ (own only) | ❌ | ❌ |
| approve / reject / issue / revoke | ❌ | ✅ | ❌ |
| verify a certificate | public, no login | | |

## Layout

```
app/api/           FastAPI service under test
app/mobile/        Expo app (week 5)
tests/api/         pytest: lifecycle, RBAC, validation
tests/contract/    consumer/provider contracts
tests/e2e/         Playwright + axe (pages/ = page objects, fixtures.ts = API data setup)
app/api/permitpass/web/  portal pages (plain HTML/JS, served by FastAPI)
tests/mobile/      Maestro flows
mocks/             WireMock stubs + test-data rules (see mocks/README.md)
perf/              k6 scripts
data-migration/    legacy CSV fixture with known answers (importer + SQL in app/api/permitpass/migration/)
postman/           manual/exploratory API collection
docs/              strategy, traceability, defects, UAT
```

## How this repo is run

Every change is an issue, a short-lived branch, a pull request with a testing checklist, and a merge once CI is green.
Browse the [merged pull requests](https://github.com/Daniel-Kav/permitpass-qa/pulls?q=is%3Apr+is%3Amerged) and the
[v0.2.0 milestone](https://github.com/Daniel-Kav/permitpass-qa/milestone/1?closed=1) to see the history.

```
main ─●────●─────────●──────────●───────────●──────────────●──────────●──── v0.2.0
       \   / \       / \        / \         / \            / \        /
        chore   persistence  jwt-auth   audit-and-listing  certificates  web-portal → fix/utc-timestamps
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md): issue → branch → PR → CI → merge.

## License
MIT
