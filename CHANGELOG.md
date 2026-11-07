# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [0.5.0] - 2026-11-08: Offline-first mobile

### Added
- **Idempotency-Key** on `POST /applications` and lifecycle actions: retries replay the first answer; per-user keys; a different request with the same key gets 422; concurrent duplicates get 409; outages release the key; 24 h expiry (#47, #49)
- **Mobile offline outbox**: apply without signal, sync automatically and **exactly once** when back online; refusals shown with reasons; per-citizen isolation (#48, #50)
- Tests: 21 API idempotency tests plus a PostgreSQL concurrency test; 20 new mobile tests including *"request arrived, reply lost"*; a Maestro **airplane-mode** flow on the Android emulator

## [0.4.0] - 2026-11-07: Resilience and mobile

### Added
- **Mobile app** (Expo / React Native): log in, apply, pay by M-Pesa with live status, verify permits; accessible labels and targets (#40, #45)
- **Mobile testing**: 20 component tests (Jest + RNTL) and 5 **Maestro** flows on an Android 12 emulator in CI against the full stack (#45)
- **Payments without a callback**: STK Push Query after 2 min, expiry after 10 min, late successes still pay, double payments flagged `refund_due`; background sweeper with `SKIP LOCKED`; admin endpoints (#30, #41)
- **Capacity**: pre-start step, 4 workers, sized DB pool with fast 503s, **load shedding**; stress `peak` input (#36, #42)

### Fixed
- Stale list responses could overwrite the officer queue after the move to multiple workers; found by E2E (#43, #44)
- Citizen page fetched the list twice on every poll (#44)

### Performance
- Stress: **3.7× throughput** (44 → 164 req/s); worst-case latency under overload **60 s → 1.1 s** (#42, `docs/perf/results.md`)

## [0.3.0] - 2026-11-06: Integrations, data and non-functional

### Added
- **KRA PIN verification** over SOAP (3 s timeout, defusedxml); fails closed with 503 if KRA is down (#19, #29)
- **M-Pesa STK push** payments: `payment_pending` state, OAuth, shared-secret callback that is idempotent and row-locked, amount-mismatch flagging, retry after failure (#20, #31)
- **Service virtualisation**: WireMock stubs for KRA and Daraja with test-data rules; M-Pesa stubs call back via webhooks (#29, #31)
- **Contract tests**: real clients vs stubs, no unmatched requests, and fakes proven to match stubs (#29, #31)
- **Legacy data migration**: cleansing rules R1–R8, rejects file, idempotent re-runs, 10 SQL reconciliation checks, CLI that gates on them (#21, #32)
- **Performance**: load, stress and soak k6 profiles with per-kind service levels; nightly and manual workflow (#22, #33)
- **Security**: OWASP ZAP baseline on every PR, strict, with justified ignores (#18, #24)
- **UAT pack**: 12 scripts, entry/exit criteria, sign-off template, `make uat-data` (#23, #37)

### Fixed
- Login form fell back to GET and put the password in the URL; found by ZAP (#25, #27)
- Missing security headers: strict CSP, clickjacking, nosniff, permissions, COOP/COEP/CORP, no-store for API data; found by ZAP (#26, #28)
- Concurrent officer actions raced: duplicate approvals and 500s on issue; found by the load test (#34, #35)

### Known issues
- Payments that never receive a callback stay `payment_pending` (#30)
- A single API worker saturates at about 44 req/s under stress (#36)

## [0.2.0] - 2026-11-06: Core platform

### Added
- **Persistence**: SQLAlchemy 2.0 with PostgreSQL 16 (SQLite for fast tests) (#2, #8)
- **Authentication**: JWT login, PBKDF2-SHA256 password hashing, role and active flag read from the database (#3, #9)
- **Audit trail** for every change, plus listing with state filter and pagination (#4, #10)
- **Signed certificates**: HMAC-SHA256, public verification (valid / invalid / revoked / expired) and revocation (#5, #11)
- **Web portal**: citizen, officer and public verify pages (#6, #12)
- Tests: 164 API tests; 17 Playwright tests on Chromium, Firefox, WebKit and Pixel 7; axe WCAG 2.1 AA scans
- CI: API × {SQLite, PostgreSQL}, E2E × 3 browsers in the official Playwright image, k6 perf gate
- Contributor workflow: CONTRIBUTING, PR template, CODEOWNERS, labels and milestone (#1, #7)

### Fixed
- Timestamps returned without a UTC offset on SQLite, and in the server's time zone on PostgreSQL (#13, #14)

### Changed
- Third-party stubs (M-Pesa, KRA) moved to `integrations-parked/` until v0.3.0 (#7)
- Missing or invalid credentials now return **401** (previously 422 for missing headers) (#9)

## [0.1.0] - 2026-11-05: Scaffold
- FastAPI skeleton, first API tests, WireMock stubs, k6 smoke, Playwright skeleton, CI
