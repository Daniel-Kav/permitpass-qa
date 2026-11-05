# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

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
