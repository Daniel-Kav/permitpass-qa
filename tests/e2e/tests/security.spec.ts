// The portal must work under its own Content-Security-Policy, with no violations. Traceability: US-24 (#26).
import { test, expect } from '../fixtures';
import { LoginPage } from '../pages/LoginPage';

test.beforeEach(async ({ page }) => {
  // Record any CSP violation the browser reports
  await page.addInitScript(() => {
    (window as any).__cspViolations = [];
    document.addEventListener('securitypolicyviolation', (e) =>
      (window as any).__cspViolations.push(`${e.violatedDirective} ${e.blockedURI}`));
  });
});

const violations = (page: import('@playwright/test').Page) => page.evaluate(() => (window as any).__cspViolations);

test('citizen and officer pages run with zero CSP violations', async ({ page, api }) => {
  const app = await api.application(['submit', 'pay']);
  await new LoginPage(page).loginAs('citizen');
  await expect(page.getByRole('row', { name: new RegExp(app.name) })).toBeVisible();   // JS ran and rendered
  expect(await violations(page)).toEqual([]);

  await page.getByRole('button', { name: 'Log out' }).click();
  await new LoginPage(page).login('officer@permitpass.test', 'PermitPass!2026');
  await expect(page.getByRole('button', { name: `Approve ${app.name}` })).toBeVisible();
  expect(await violations(page)).toEqual([]);
});

test('verify page runs with zero CSP violations', async ({ page, api }) => {
  const app = await api.application(['submit', 'pay', 'approve', 'issue']);
  const cert = await api.certificate(app.id);
  await page.goto(`/verify.html?n=${cert.number}&sig=${cert.signature}`);
  await expect(page.locator('#result .result')).toHaveAttribute('data-status', 'valid');
  expect(await violations(page)).toEqual([]);
});

test('the portal refuses to be framed by another site', async ({ page }) => {
  const res = await page.request.get('/');
  expect(res.headers()['x-frame-options']).toBe('DENY');
  expect(res.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
});
