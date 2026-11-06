// STRESS: keep raising the arrival rate until the system degrades, to find where and how it breaks.
// Thresholds here are *markers*, not gates: the point is to see which one fails first and at what rate.
import { citizenApplies, citizenBrowses, publicVerifies, prepare, markdownSummary, TREND_STATS } from './lib.js';

const PEAK = Number(__ENV.PEAK_RATE || 120);   // journeys per second at the top
const STEP = __ENV.STEP || '1m';

export const options = {
  setupTimeout: '3m',
  summaryTrendStats: TREND_STATS,
  scenarios: {
    rising: {
      executor: 'ramping-arrival-rate',
      exec: 'mixed',
      startRate: 5, timeUnit: '1s',
      preAllocatedVUs: 50, maxVUs: 400,
      stages: [0.1, 0.25, 0.5, 0.75, 1].map((f) => ({ duration: STEP, target: Math.round(PEAK * f) }))
        .concat([{ duration: '30s', target: 0 }]),
    },
  },
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.05', abortOnFail: false }],
    'http_req_duration{kind:read}': ['p(95)<1000'],
    'http_req_duration{kind:write}': ['p(95)<1500'],
    'http_req_duration{kind:public}': ['p(95)<1000'],
    dropped_iterations: ['count<1'],
  },
};

export const setup = () => prepare(5);
export function mixed(d) {
  const r = Math.random();
  if (r < 0.5) citizenBrowses(d.citizen);
  else if (r < 0.8) publicVerifies(d.certs);
  else citizenApplies(d.citizen);
}
export function handleSummary(data) {
  const md = markdownSummary(data, `Stress test (to ${PEAK} journeys/s)`);
  return { stdout: md, 'perf-summary.md': md, 'perf-summary.json': JSON.stringify(data) };
}
