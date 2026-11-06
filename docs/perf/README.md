# Performance testing

Four k6 profiles share the journeys in `perf/lib.js`. Requests are tagged by **kind** so each kind gets its own
threshold.

| Profile | Shape | When it runs | Gate? |
| --- | --- | --- | --- |
| `smoke.js` | 5 VUs, 30 s | every PR (CI) | yes |
| `load.js` | ramps to **50 VUs** (35 citizens, 10 officers, 5 public), holds 5 min | nightly; PRs touching `perf/` (2 min hold); manual | yes |
| `stress.js` | arrival rate rising **5 → 120 journeys/s** in steps | manual | no: finds the breaking point |
| `soak.js` | **20 VUs** for 30 min (or `DURATION`), memory sampled every 10 s | manual | yes |

Run manually: **Actions → Performance → Run workflow**, pick a profile. Locally: `k6 run perf/load.js`
(add `SCALE=0.2 HOLD=30s` for a quick check).

## Service levels (the thresholds)

| Request kind | Examples | Target | Why |
| --- | --- | --- | --- |
| read | list applications, get one, poll payment | p95 < **300 ms** | officers page through queues all day; anything slower feels sluggish |
| write | create, submit, pay, approve, issue | p95 < **500 ms** | includes the KRA check (create) and the STK push (pay); users expect a short wait |
| public | `/verify` from a QR scan | p95 < **200 ms** | used at roadside or counter checks, often on slow mobile data, so server time must be tiny |
| payment settle | STK push → callback → `paid` | p95 < **5 s** | the stub calls back after 1 s; extra time is ours |
| errors | any non-expected status | < **1%** | a failed payment or lost application is costly to the citizen |
| checks | functional assertions inside the journeys | > **99%** | performance doesn't count if the answers are wrong |

Two officers approving the same application at the same moment is normal under load: one gets **409**, and the
scripts treat that as a correct answer (`expectedStatuses(200, 409)`), not an error.

## Results
See [`results.md`](results.md) for the latest recorded runs and findings.
