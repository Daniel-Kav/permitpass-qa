// Automated accessibility scan (WCAG 2.1 AA rules via axe-core) on every page. Traceability: US-21.
import AxeBuilder from '@axe-core/playwright';
import { test, expect } from '../fixtures';
import { LoginPage } from '../pages/LoginPage';

const scan = async (page: import('@playwright/test').Page) => {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  const blocking = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(blocking.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
};

test('login page', async ({ page }) => {
  await page.goto('/');
  await scan(page);
});

test('login page with an error showing', async ({ page }) => {
  const login = new LoginPage(page);
  await login.goto();
  await login.login('x@y.z', 'nope');
  await expect(login.error()).toBeVisible();
  await scan(page);
});

test('citizen applications page with data', async ({ page, api }) => {
  await api.application(['submit']);
  await new LoginPage(page).loginAs('citizen');
  await expect(page.getByRole('row').nth(1)).toBeVisible();
  await scan(page);
});

test('citizen page with the M-Pesa payment form open', async ({ page, api }) => {
  const app = await api.application(['submit']);
  await new LoginPage(page).loginAs('citizen');
  await page.getByRole('button', { name: new RegExp(`^Pay KES \\d+ for ${app.name}$`) }).click();
  await expect(page.getByLabel('M-Pesa phone number')).toBeFocused();
  await scan(page);
});

test('officer queue with a reason form open', async ({ page, api }) => {
  const app = await api.application(['submit', 'pay']);
  await new LoginPage(page).loginAs('officer');
  await page.getByRole('button', { name: `Reject ${app.name}` }).click();
  await expect(page.getByLabel('Reason')).toBeFocused();
  await scan(page);
});

test('verify page with a result', async ({ page, api }) => {
  const app = await api.application(['submit', 'pay', 'approve', 'issue']);
  const cert = await api.certificate(app.id);
  await page.goto(`/verify.html?n=${cert.number}&sig=${cert.signature}`);
  await expect(page.locator('#result .result')).toBeVisible();
  await scan(page);
});

test('login works with the keyboard alone', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');                                  // skip link
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.getByLabel('Email').focus();
  await page.keyboard.type('citizen@permitpass.test');
  await page.keyboard.press('Tab');
  await page.keyboard.type('PermitPass!2026');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/my\.html$/);
});
