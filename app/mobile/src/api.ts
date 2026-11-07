// Thin client for the PermitPass API. The mobile app uses exactly the same endpoints as the web portal.
// Android emulators reach the host machine at 10.0.2.2.
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000';

export type State = 'draft' | 'submitted' | 'payment_pending' | 'paid' | 'approved' | 'issued' | 'rejected' | 'revoked';

export interface Application {
  id: string;
  business_name: string;
  kra_pin: string;
  state: State;
  fee_kes: number;
  created_at: string;
  rejection_reason: string | null;
  payment_note: string | null;
}

export interface Certificate { number: string; signature: string; expires_at: string }
export interface Verdict { status: 'valid' | 'invalid' | 'revoked' | 'expired'; business_name?: string; expires_at?: string }

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function errorText(body: any, status: number): string {
  if (body?.detail && typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map((d: any) => `${d.loc?.slice(-1)[0] ?? 'field'}: ${d.msg}`).join('; ');
  return `Request failed (${status})`;
}

export async function request<T>(path: string, opts: { method?: string; body?: unknown; token?: string } = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: opts.method ?? 'GET', headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body) });
  } catch {
    throw new ApiError('Cannot reach PermitPass. Check your connection and try again.', 0);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(errorText(data, res.status), res.status);
  return data as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: string }>('/auth/login', { method: 'POST', body: { email: email.trim(), password } }),
  list: (token: string) => request<{ items: Application[] }>('/applications?limit=100', { token }).then((p) => p.items),
  create: (token: string, business_name: string, kra_pin: string) =>
    request<Application>('/applications', { method: 'POST', token, body: { business_name, kra_pin } }),
  submit: (token: string, id: string) => request<Application>(`/applications/${id}/submit`, { method: 'POST', token }),
  pay: (token: string, id: string, phone: string) =>
    request<Application>(`/applications/${id}/pay`, { method: 'POST', token, body: { phone: phone.replace(/\s+/g, '') } }),
  certificate: (token: string, id: string) => request<Certificate>(`/applications/${id}/certificate`, { token }),
  verify: (number: string, sig: string) =>
    request<Verdict>(`/verify/${encodeURIComponent(number.trim())}?sig=${encodeURIComponent(sig.trim())}`),
};
