// SOAK: steady, moderate load for a long time, to surface leaks, slow drifts and token-expiry problems.
// The workflow samples container memory alongside (perf/sample-stats.sh).
import { sleep } from 'k6';
import { citizenApplies, citizenBrowses, officerWorks, publicVerifies, prepare, markdownSummary, TREND_STATS } from './lib.js';

export const options = {
  setupTimeout: '3m',
  summaryTrendStats: TREND_STATS,
  scenarios: {
    citizens: { executor: 'constant-vus', exec: 'citizens', vus: Number(__ENV.VUS || 15), duration: __ENV.DURATION || '30m' },
    officers: { executor: 'constant-vus', exec: 'officers', vus: 3, duration: __ENV.DURATION || '30m' },
    public: { executor: 'constant-vus', exec: 'verifiers', vus: 2, duration: __ENV.DURATION || '30m' },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    'http_req_duration{kind:read}': ['p(95)<300', 'p(99)<800'],
    'http_req_duration{kind:write}': ['p(95)<500'],
    'http_req_duration{kind:public}': ['p(95)<200'],
  },
};

export const setup = () => prepare(10);
export function citizens(d) { citizenBrowses(d.citizen); citizenApplies(d.citizen); sleep(5); }
export function officers(d) { officerWorks(d.officer); sleep(3); }
export function verifiers(d) { publicVerifies(d.certs); sleep(2); }
export function handleSummary(data) {
  const md = markdownSummary(data, `Soak test (${__ENV.DURATION || '30m'})`);
  return { stdout: md, 'perf-summary.md': md, 'perf-summary.json': JSON.stringify(data) };
}
