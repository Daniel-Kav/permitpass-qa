// A tiny in-memory stand-in for the PermitPass API, installed as global.fetch.
// Follows the same test-data rules as the real stubs (mocks/README.md) for the cases these tests use.
import type { Application } from '../src/api';

type Handler = (method: string, path: string, body: any, headers: Record<string, string>) => [number, any] | undefined;

export function installFakeApi(initial: Partial<Application>[] = []) {
  let apps: Application[] = initial.map((a, i) => ({
    id: `id-${i}`, business_name: `Duka ${i}`, kra_pin: 'A123456789Z', state: 'draft', fee_kes: 2500,
    created_at: '2026-11-07T09:00:00+00:00', rejection_reason: null, payment_note: null, ...a,
  }));
  const calls: { method: string; path: string; body: any }[] = [];
  let override: Handler | null = null;

  const route = (method: string, path: string, body: any, headers: Record<string, string>): [number, any] => {
    const o = override?.(method, path, body, headers);
    if (o) return o;
    if (path === '/auth/login') {
      if (body.password !== 'PermitPass!2026') return [401, { detail: 'Incorrect email or password' }];
      return [200, { access_token: 'tok', role: body.email.startsWith('officer') ? 'officer' : 'citizen' }];
    }
    if (headers.Authorization !== 'Bearer tok' && !path.startsWith('/verify/')) return [401, { detail: 'Not authenticated' }];
    if (path === '/applications?limit=100') return [200, { items: apps }];
    if (path === '/applications' && method === 'POST') {
      if (!/^[AP]\d{9}[A-Z]$/.test(body.kra_pin)) return [422, { detail: [{ loc: ['body', 'kra_pin'], msg: 'String should match pattern' }] }];
      if (body.kra_pin.includes('999999999')) return [422, { detail: 'KRA PIN is not registered' }];
      const a = { ...apps[0], id: `id-${apps.length}`, business_name: body.business_name, kra_pin: body.kra_pin, state: 'draft' as const };
      apps = [a, ...apps];
      return [201, a];
    }
    const m = path.match(/^\/applications\/([^/]+)\/(submit|pay|certificate)$/);
    if (m) {
      const a = apps.find((x) => x.id === m[1])!;
      if (m[2] === 'submit') a.state = 'submitted';
      if (m[2] === 'pay') {
        if (!/^(?:\+?254|0)[17]\d{8}$/.test(body.phone)) return [422, { detail: [{ loc: ['body', 'phone'], msg: 'String should match pattern' }] }];
        a.state = 'payment_pending';
      }
      if (m[2] === 'certificate') return [200, { number: 'PP-2026-ABCDEF12', signature: 'sig123', expires_at: '2027-11-07T09:00:00+00:00' }];
      return [200, a];
    }
    const v = path.match(/^\/verify\/([^?]+)\?sig=(.*)$/);
    if (v) return [200, v[2] === 'sig123' ? { status: 'valid', business_name: 'Kibanda Coffee House', expires_at: '2027-11-07T09:00:00+00:00' } : { status: 'invalid' }];
    return [404, { detail: 'Not found' }];
  };

  global.fetch = jest.fn(async (url: any, init: any = {}) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, '');
    const body = init.body ? JSON.parse(init.body) : undefined;
    const method = init.method ?? 'GET';
    calls.push({ method, path, body });
    const [status, data] = route(method, path, body, init.headers ?? {});
    // Serialise like a real network would, so the screen never shares objects with the 'server'
    const wire = data === undefined ? undefined : JSON.parse(JSON.stringify(data));
    return { ok: status < 400, status, json: async () => wire } as Response;
  }) as any;

  return {
    calls,
    apps: () => apps,
    set(id: string, patch: Partial<Application>) { Object.assign(apps.find((a) => a.id === id)!, patch); },
    override(h: Handler | null) { override = h; },
  };
}
