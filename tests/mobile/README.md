# Mobile tests

| Layer | Where | Runs |
| --- | --- | --- |
| Component tests (Jest + React Native Testing Library) | `app/mobile/__tests__/` | every PR touching the app |
| Device flows (Maestro on an Android emulator), incl. **airplane mode** for offline sync | `tests/mobile/flows/` | PRs touching the app or these flows, nightly, manual |

The Maestro flows drive the **release build** of the app on an Android 12 emulator against the full Compose stack
(API, PostgreSQL, WireMock), so M-Pesa callbacks and KRA checks are real HTTP round trips. They use the same
test-data rules as the portal (`mocks/README.md`).

Run locally (Android emulator running, `make up`):
```bash
cd app/mobile && npx expo run:android --variant release   # or install a built APK
maestro test tests/mobile/flows
```

## Offline sync (#48)
Applications created without a connection go to an on-device **outbox** (AsyncStorage) and are sent oldest-first
when NetInfo reports the connection is back, on app start, and every 15 s. Each item keeps one
**Idempotency-Key** for life, so the API replays rather than duplicates (#47). `outbox.test.ts` covers ordering,
backoff, refusals, persistence and per-user isolation; `offline.test.tsx` covers the screens, including *"the
request arrived but the reply was lost"*; `06_offline_apply.yaml` toggles airplane mode on the emulator.
