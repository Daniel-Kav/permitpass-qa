# Mobile tests

| Layer | Where | Runs |
| --- | --- | --- |
| Component tests (Jest + React Native Testing Library) | `app/mobile/__tests__/` | every PR touching the app |
| Device flows (Maestro on an Android emulator) | `tests/mobile/flows/` | PRs touching the app or these flows, nightly, manual |

The Maestro flows drive the **release build** of the app on an Android 12 emulator against the full Compose stack
(API, PostgreSQL, WireMock), so M-Pesa callbacks and KRA checks are real HTTP round trips. They use the same
test-data rules as the portal (`mocks/README.md`).

Run locally (Android emulator running, `make up`):
```bash
cd app/mobile && npx expo run:android --variant release   # or install a built APK
maestro test tests/mobile/flows
```
