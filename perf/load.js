// LOAD: a normal busy day. ~70% citizens, 20% officers, 10% public verification, ramping to 50 VUs.
// Pass/fail thresholds are the service levels in docs/perf/README.md.
import { sleep } from 'k6';
import { citizenApplies, citizenBrowses, officerWorks, publicVerifies, prepare, markdownSummary, TREND_STATS } from './lib.js';

const S = Number(__ENV.SCALE || 1);           // SCALE=0.2 for a quick check
const HOLD = __ENV.HOLD || '5m';
const stages = (peak) => [
  { duration: '1m', target: Math.max(1, Math.round(peak * S)) },
  { duration: HOLD, target: Math.max(1, Math.round(peak * S)) },
  { duration: '30s', target: 0 },
];

export const options = {
  setupTimeout: '3m',
  summaryTrendStats: TREND_STATS,
  scenarios: {
    citizens: { executor: 'ramping-vus', exec: 'citizens', stages: stages(35) },
    officers: { executor: 'ramping-vus', exec: 'officers', stages: stages(10) },
    public: { executor: 'ramping-vus', exec: 'verifiers', stages: stages(5) },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    'http_req_duration{kind:read}': ['p(95)<300'],
    'http_req_duration{kind:write}': ['p(95)<500'],
    'http_req_duration{kind:public}': ['p(95)<200'],
    payment_settle_ms: ['p(95)<5000'],
  },
};

export const setup = () => prepare(10);
export function citizens(d) { citizenBrowses(d.citizen); citizenApplies(d.citizen); sleep(3); }
export function officers(d) { officerWorks(d.officer); sleep(2); }
export function verifiers(d) { publicVerifies(d.certs); sleep(1); }
export function handleSummary(data) {
  const md = markdownSummary(data, 'Load test');
  return { stdout: md, 'perf-summary.md': md, 'perf-summary.json': JSON.stringify(data) };
}
