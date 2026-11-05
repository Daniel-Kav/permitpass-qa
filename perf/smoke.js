// k6 smoke test: runs on every CI build. Full load / stress / soak profiles arrive in week 5.
// Targets are written as if a contract required them; justify each in docs/test-strategy.md.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],      // under 1% errors
    http_req_duration: ['p(95)<300'],    // 95% of requests under 300 ms
  },
};

const citizen = { headers: { 'Content-Type': 'application/json', 'X-User-Id': `citizen-${__VU}`, 'X-User-Role': 'citizen' } };

export default function () {
  check(http.get(`${BASE}/health`), { 'health is 200': (r) => r.status === 200 });
  const res = http.post(`${BASE}/applications`, JSON.stringify({ business_name: 'Load Test Ltd', kra_pin: 'A123456789Z' }), citizen);
  check(res, { 'application created': (r) => r.status === 201 });
  sleep(1);
}
