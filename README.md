# PermitPass QA

A hands-on QA portfolio built around **PermitPass**, a small permit-application service (Kenyan business permits:
KRA PIN validation, M-Pesa payment, officer approval, signed certificates). The app is deliberately small; the
**test system around it** is the point.

[![CI](https://github.com/Daniel-Kav/permitpass-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/Daniel-Kav/permitpass-qa/actions/workflows/ci.yml)

## Quick start

```bash
pip install -r tests/api/requirements.txt
make test-api        # API tests on in-memory SQLite, no Docker needed
DATABASE_URL=postgresql+psycopg://user:pass@localhost/db make test-api   # same suite on PostgreSQL

make up              # API + PostgreSQL 16 (Docker)
make test-e2e        # Playwright
make perf-smoke      # k6 (needs k6 installed)
```

## What's covered, and where

| QA skill | Where it lives | Status |
| --- | --- | --- |
| Test strategy, risk-based planning | `docs/test-strategy.md` | Draft |
| Requirements traceability | `docs/traceability.csv` | Live |
| State-transition testing (permit lifecycle) | `tests/api/test_lifecycle.py` | Done |
| Role-based access + IDOR checks | `tests/api/test_rbac.py` | Done |
| Authentication + token attacks (expired, forged, `alg: none`) | `tests/api/test_auth.py` | Done |
| Audit trail, listing and pagination boundaries | `tests/api/test_audit.py`, `test_listing.py` | Done |
| Signed certificates: decision table, expiry boundary, tamper tests | `tests/api/test_certificates.py` | Done |
| Equivalence partitioning / boundary values | `tests/api/test_validation.py` | Done |
| Service virtualisation (M-Pesa REST, KRA SOAP) | `integrations-parked/` | Parked (later milestone) |
| Contract tests | `tests/contract/` | Week 4 |
| Web E2E, cross-browser, accessibility (axe) | `tests/e2e/` | Skeleton |
| Mobile (Expo + Maestro, offline sync) | `app/mobile/`, `tests/mobile/` | Week 5 |
| Performance (k6 smoke / load / stress / soak) | `perf/` | Smoke ready |
| Security (OWASP ZAP baseline) | CI | Week 5 |
| Data migration + SQL reconciliation | `data-migration/` | Week 4 |
| Defect management | `.github/ISSUE_TEMPLATE/`, `docs/defects/` | Ready |
| UAT scripts and sign-off | `docs/uat/` | Week 6 |
| CI/CD quality gates | `.github/workflows/ci.yml` | Live |
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
draft --submit--> submitted --pay--> paid --approve--> approved --issue--> issued --revoke--> revoked
                      |                |                                     (signed certificate)   (reason required)
                      +----reject------+---> rejected   (officer, reason required)
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
tests/e2e/         Playwright + axe
tests/mobile/      Maestro flows
integrations-parked/ WireMock stubs, parked for a later milestone
perf/              k6 scripts
data-migration/    legacy → new schema + reconciliation SQL
postman/           manual/exploratory API collection
docs/              strategy, traceability, defects, UAT
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md): issue → branch → PR → CI → merge.

## License
MIT
