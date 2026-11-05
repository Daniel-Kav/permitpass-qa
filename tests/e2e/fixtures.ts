// Test data is created through the API (fast, reliable); the browser is used only for the behaviour under test.
import { test as base, expect, APIRequestContext } from '@playwright/test';

export const PASSWORD = process.env.DEMO_PASSWORD || 'PermitPass!2026';
export const USERS = {
  citizen: 'citizen@permitpass.test',
  otherCitizen: 'citizen2@permitpass.test',
  officer: 'officer@permitpass.test',
} as const;
export type UserKey = keyof typeof USERS;

export class Api {
  private tokens = new Map<UserKey, string>();
  constructor(private request: APIRequestContext) {}

  async token(user: UserKey) {
    if (!this.tokens.has(user)) {
      const res = await this.request.post('/auth/login', { data: { email: USERS[user], password: PASSWORD } });
      expect(res.ok(), await res.text()).toBeTruthy();
      this.tokens.set(user, (await res.json()).access_token);
    }
    return this.tokens.get(user)!;
  }

  async as(user: UserKey, method: 'GET' | 'POST', path: string, data?: object) {
    const res = await this.request.fetch(path, { method, data, headers: { Authorization: `Bearer ${await this.token(user)}` } });
    expect(res.ok(), `${method} ${path}: ${await res.text()}`).toBeTruthy();
    return res.json();
  }

  /** A fresh application with a unique name, driven through the given steps. */
  async application(steps: string[] = []) {
    const name = `E2E ${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    const app = await this.as('citizen', 'POST', '/applications', { business_name: name, kra_pin: 'A123456789Z' });
    const who: Record<string, UserKey> = { submit: 'citizen', pay: 'citizen', approve: 'officer', issue: 'officer' };
    for (const step of steps) await this.as(who[step], 'POST', `/applications/${app.id}/${step}`);
    return { id: app.id as string, name };
  }

  async certificate(appId: string) {
    return this.as('citizen', 'GET', `/applications/${appId}/certificate`);
  }
}

export const test = base.extend<{ api: Api }>({
  api: async ({ request }, use) => use(new Api(request)),
});
export { expect };
