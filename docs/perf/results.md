# Performance results

Environment for all runs: GitHub-hosted `ubuntu-latest` (2 vCPU), Docker Compose stack (one uvicorn worker,
PostgreSQL 16, WireMock for KRA and M-Pesa with 1 s callback webhooks). Numbers are server time plus loopback
network, not end-user experience on mobile data.

## v0.3.0: load (50 VUs, 70/20/10 mix)

### Run 1: **failed**, and found a defect
| | Result | Target |
| --- | --- | --- |
| Failed requests | **1.21%** ❌ | < 1% |
| Checks passed | **98.69%** ❌ | > 99% |
| Write p95 | 21 ms ✅ | < 500 ms |

Latency was far inside target, yet requests failed. The cause was concurrent officers racing on the same
application: duplicate approvals and 500s on issue. Raised as **#34** (High), reproduced deterministically,
fixed with a row lock in **#35**, and covered by a concurrency regression test on PostgreSQL.

### Run 2: after #35 ✅
| Request kind | median | p95 | p99 | max | Target (p95) |
| --- | --- | --- | --- | --- | --- |
| read | 9 ms | 20 ms | 30 ms | 65 ms | < 300 ms ✅ |
| write | 11 ms | 25 ms | 37 ms | 217 ms | < 500 ms ✅ |
| public verify | 4 ms | 12 ms | 19 ms | 48 ms | < 200 ms ✅ |
| payment settle (STK → callback → paid) | | 1,297 ms | | | < 5 s ✅ |

7,771 requests at 31.7/s · **0.00% failed** · **100% checks**. The row lock costs about 4 ms at p95 on writes.

## v0.3.0: stress (arrival rate 5 → 120 journeys/s, 1-minute steps)

| | Result |
| --- | --- |
| Requests | 16,464 (plateau ≈ **44 req/s**) |
| Failed | 2.53% (timeouts) |
| p95 read / write / public | 357 / 365 / 309 ms |
| **p99** | **60 s** (k6's request timeout) |
| VUs | hit the 400 maximum; iterations dropped |

**Finding:** above about 30 journeys/s the single worker saturates. Requests then *queue* rather than fail fast,
so the tail goes to 60 s while the median stays around 10 ms: some users wait a minute and others get instant
answers. Throughput doesn't grow past about 44 req/s. Tracked in **#36**: multiple workers (start-up seeding
must move to a pre-start step first), pool sizing, and load shedding with fast 503s. Acceptance: knee ≥ 2× and
p99 < 5 s under overload.

The load profile (the expected busy day) runs at 32 req/s, below the knee, which is why it passes. The headroom
is small, which is exactly what a stress test is for.

## v0.3.0: soak (20 VUs × 30 min) ✅

| Request kind | median | p95 | p99 | max | Target |
| --- | --- | --- | --- | --- | --- |
| read | 6 ms | 12 ms | 32 ms | 158 ms | p95 < 300, p99 < 800 ✅ |
| write | 7 ms | 16 ms | 26 ms | 167 ms | p95 < 500 ✅ |
| payment settle | | 1,290 ms | | | < 5 s ✅ |

22,613 requests at 12.3/s · **0.00% failed** · **100% checks** · tokens issued once in setup stayed valid for
the whole run (`ACCESS_TOKEN_MINUTES=240` for perf only). Container CPU and memory samples are in the run's job
summary and the `perf-soak-*` artifact (`perf-stats.csv`).

*Gap found while writing this up:* the soak profile had no threshold on `public` requests, so they didn't show
in the summary. Added `p95 < 200 ms` to match the load profile.

## How to reproduce
**Actions → Performance → Run workflow** → choose the profile. Load also runs nightly.

## v0.4.0: capacity after #42 (4 workers, sized pool, load shedding)

Same runner type and same `stress.js`. Before = v0.3.0, one worker.

| Stress run | Throughput | Failed | p95 read / write | p99 | max | VUs needed |
| --- | --- | --- | --- | --- | --- | --- |
| **Before**, to 120/s | plateau ≈ 44 req/s | 2.53% (60 s timeouts) | 357 / 365 ms | **60 s** | 60 s | 400 (maxed) |
| **After**, to 120/s | 68.5 req/s, still rising with load | **0.00%** | 9 / 14 ms | 15–44 ms | 192 ms | 62 |
| **After**, to 300/s | **164 req/s** (3.7×) | 10.58% shed as fast 503s | 524 / 629 ms | **663–809 ms** | **1.1 s** | 260 |

**What changed in behaviour:** before, overload meant *queueing*: a few users waited a minute while others were
served instantly. Now a worker that already has 32 requests in flight answers `503 Retry-After: 2` at once, so
everyone else stays fast and nobody waits a minute. At 120 journeys/s (4× the old knee) there is no degradation
at all; the new knee lies between 120 and 300 journeys/s.

#36 acceptance: knee ≥ 2× ✅ (> 4×) · p99 under overload < 5 s ✅ (≤ 0.8 s, max 1.1 s).

The 4-worker change also exposed a client-side race (stale list responses rendering last), caught by E2E and fixed
in #44 (#43).
