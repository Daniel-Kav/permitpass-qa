// Shared journeys for the k6 profiles. Requests are tagged by `kind` (read / write / auth / public)
// so thresholds can be set per kind. Test data is created through the API, like the E2E suite.
import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Trend } from 'k6/metrics';

export const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const PASSWORD = __ENV.DEMO_PASSWORD || 'PermitPass!2026';
const JSON_HDR = { 'Content-Type': 'application/json' };

export const TREND_STATS = ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'];

export const paymentSettleTime = new Trend('payment_settle_ms', true);

export function login(email) {
  const r = http.post(`${BASE}/auth/login`, JSON.stringify({ email, password: PASSWORD }), { headers: JSON_HDR, tags: { kind: 'auth' } });
  if (!check(r, { 'login ok': (x) => x.status === 200 })) fail(`login failed for ${email}: ${r.status}`);
  return r.json('access_token');
}

const auth = (token, kind) => ({ headers: { ...JSON_HDR, Authorization: `Bearer ${token}` }, tags: { kind } });
const uniq = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;  // __VU and __ITER are undefined in setup()

/** Create, submit and pay for one application. Returns its id, or null if a step failed. */
export function citizenApplies(token, { waitForPayment = false } = {}) {
  const create = http.post(`${BASE}/applications`, JSON.stringify({ business_name: `Load Duka ${uniq()}`, kra_pin: 'A123456789Z' }), auth(token, 'write'));
  if (!check(create, { 'application created': (r) => r.status === 201 })) return null;
  const id = create.json('id');
  sleep(1);
  const submit = http.post(`${BASE}/applications/${id}/submit`, null, auth(token, 'write'));
  check(submit, { 'submitted': (r) => r.status === 200 });
  sleep(1);
  const pay = http.post(`${BASE}/applications/${id}/pay`, JSON.stringify({ phone: '0712345678' }), auth(token, 'write'));
  check(pay, { 'STK push started': (r) => r.status === 200 && r.json('state') === 'payment_pending' });
  if (waitForPayment) {
    const t0 = Date.now();
    for (let i = 0; i < 20; i++) {
      sleep(0.5);
      if (http.get(`${BASE}/applications/${id}`, auth(token, 'read')).json('state') === 'paid') {
        paymentSettleTime.add(Date.now() - t0);
        return id;
      }
    }
    check(null, { 'payment settled within 10 s': () => false });
  }
  return id;
}

export function citizenBrowses(token) {
  const r = http.get(`${BASE}/applications?limit=20`, auth(token, 'read'));
  check(r, { 'list ok': (x) => x.status === 200 });
}

/** An officer works the queue: list paid applications, approve one, issue one. */
export function officerWorks(token) {
  const paid = http.get(`${BASE}/applications?state=paid&limit=20`, auth(token, 'read'));
  check(paid, { 'queue ok': (r) => r.status === 200 });
  const items = paid.status === 200 ? paid.json('items') : [];
  if (items.length) {
    const pick = items[Math.floor(Math.random() * items.length)];
    // Two officers may pick the same one: 409 is a correct, expected answer here
    const r = http.post(`${BASE}/applications/${pick.id}/approve`, null,
      { ...auth(token, 'write'), responseCallback: http.expectedStatuses(200, 409) });
    check(r, { 'approve ok or already taken': (x) => x.status === 200 || x.status === 409 });
  }
  sleep(1);
  const approved = http.get(`${BASE}/applications?state=approved&limit=5`, auth(token, 'read'));
  const ready = approved.status === 200 ? approved.json('items') : [];
  if (ready.length) {
    const r = http.post(`${BASE}/applications/${ready[0].id}/issue`, null,
      { ...auth(token, 'write'), responseCallback: http.expectedStatuses(200, 409) });
    check(r, { 'issue ok or already taken': (x) => x.status === 200 || x.status === 409 });
  }
}

/** Anyone checking a permit's QR code. No login. */
export function publicVerifies(certs) {
  const c = certs[Math.floor(Math.random() * certs.length)];
  const r = http.get(`${BASE}/verify/${c.number}?sig=${c.signature}`, { tags: { kind: 'public' } });
  check(r, { 'verify says valid': (x) => x.status === 200 && x.json('status') === 'valid' });
}

/** setup(): tokens for both roles plus some issued certificates for the verify journey. */
export function prepare(nCerts = 10) {
  const citizen = login('citizen@permitpass.test');
  const officer = login('officer@permitpass.test');
  const certs = [];
  for (let i = 0; i < nCerts; i++) {
    const id = citizenApplies(citizen, { waitForPayment: true });
    if (!id) continue;
    http.post(`${BASE}/applications/${id}/approve`, null, auth(officer, 'setup'));
    http.post(`${BASE}/applications/${id}/issue`, null, auth(officer, 'setup'));
    const c = http.get(`${BASE}/applications/${id}/certificate`, auth(citizen, 'setup'));
    if (c.status === 200) certs.push({ number: c.json('number'), signature: c.json('signature') });
  }
  if (!certs.length) fail('setup could not create any certificates');
  return { citizen, officer, certs };
}

/** Markdown summary for the GitHub job summary and docs/perf. */
export function markdownSummary(data, title) {
  const m = data.metrics;
  const v = (name, stat) => (m[name] && m[name].values[stat] !== undefined ? m[name].values[stat] : NaN);
  const ms = (x) => (Number.isNaN(x) ? '–' : `${x.toFixed(0)} ms`);
  const rows = ['read', 'write', 'public'].map((k) => {
    const n = `http_req_duration{kind:${k}}`;
    return `| ${k} | ${ms(v(n, 'med'))} | ${ms(v(n, 'p(95)'))} | ${ms(v(n, 'p(99)'))} | ${ms(v(n, 'max'))} |`;
  });
  const thresholds = Object.entries(m).flatMap(([name, metric]) =>
    Object.entries(metric.thresholds || {}).map(([t, r]) => `| \`${name}\` | \`${t}\` | ${r.ok ? '✅ pass' : '❌ FAIL'} |`));
  return [
    `## ${title}`,
    '',
    `Requests: **${v('http_reqs', 'count')}** (${v('http_reqs', 'rate').toFixed(1)}/s) · failed: **${(v('http_req_failed', 'rate') * 100).toFixed(2)}%** · checks passed: **${(v('checks', 'rate') * 100).toFixed(2)}%** · peak VUs: **${v('vus_max', 'max')}**`,
    '',
    '| Request kind | median | p95 | p99 | max |', '| --- | --- | --- | --- | --- |', ...rows,
    '',
    `Payment settle time (STK push → callback → paid): p95 ${ms(v('payment_settle_ms', 'p(95)'))}`,
    '',
    '| Metric | Threshold | Result |', '| --- | --- | --- |', ...thresholds,
    '',
  ].join('\n');
}
