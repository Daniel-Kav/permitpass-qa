// End-to-end journeys through the web portal. Traceability: US-11.
import { test, expect } from '../fixtures';
import { LoginPage } from '../pages/LoginPage';
import { CitizenPage } from '../pages/CitizenPage';
import { OfficerPage } from '../pages/OfficerPage';
import { VerifyPage } from '../pages/VerifyPage';

test('citizen applies and pays, officer approves and issues, public verifies', async ({ browser }) => {
  const name = `Duka ${Date.now().toString(36)}`;

  // Citizen
  const citizenCtx = await browser.newContext();
  const c = await citizenCtx.newPage();
  await new LoginPage(c).loginAs('citizen');
  const citizen = new CitizenPage(c);
  await citizen.expectLoaded();
  await citizen.create(name, 'a123456789z');           // lower-case is normalised
  await expect(citizen.status()).toContainText(`${name} created as a draft`);
  await citizen.submit(name);
  await citizen.expectState(name, 'submitted');
  await citizen.pay(name);
  await citizen.expectState(name, 'payment_pending');
  await expect(citizen.row(name)).toContainText('Check your phone');
  await expect(citizen.row(name).locator('.badge')).toHaveText('paid', { timeout: 15_000 });   // M-Pesa callback
  await expect(citizen.status()).toContainText(`Payment received for ${name}`);

  // Officer, in a separate session
  const officerCtx = await browser.newContext();
  const o = await officerCtx.newPage();
  await new LoginPage(o).loginAs('officer');
  const officer = new OfficerPage(o);
  await officer.expectLoaded();
  await officer.act('Approve', name);
  await expect(officer.status()).toContainText(`${name}: now approved`);
  await officer.filter('Approved, ready to issue');
  await officer.act('Issue permit', name);
  await expect(officer.status()).toContainText(`${name}: now issued`);

  // Citizen sees the certificate and follows its verification link
  await c.reload();
  await citizen.expectState(name, 'issued');
  await citizen.row(name).getByRole('link', { name: /Certificate PP-/ }).click();
  await new VerifyPage(c).expectStatus('valid');
  await expect(c.getByText(name)).toBeVisible();

  await citizenCtx.close();
  await officerCtx.close();
});

test('officer rejects with a reason and the citizen sees it', async ({ page, api, browser }) => {
  const app = await api.application(['submit', 'pay']);
  await new LoginPage(page).loginAs('officer');
  const officer = new OfficerPage(page);
  await officer.withReason('Reject', app.name, 'KRA PIN does not match business');
  await expect(officer.status()).toContainText(`${app.name}: now rejected`);

  const ctx = await browser.newContext();
  const c = await ctx.newPage();
  await new LoginPage(c).loginAs('citizen');
  await expect(new CitizenPage(c).row(app.name)).toContainText('Rejected: KRA PIN does not match business');
  await ctx.close();
});

test('reject needs a reason: an empty reason is refused and nothing changes', async ({ page, api }) => {
  const app = await api.application(['submit', 'pay']);
  await new LoginPage(page).loginAs('officer');
  const officer = new OfficerPage(page);
  await page.getByRole('button', { name: `Reject ${app.name}` }).click();
  await officer.row(app.name).getByRole('button', { name: 'Confirm reject' }).click();
  await expect(officer.row(app.name).locator('.badge')).toHaveText('paid');
});

test('revoked permit shows as revoked on the public verify page', async ({ page, api, request }) => {
  const app = await api.application(['submit', 'pay', 'approve', 'issue']);
  const cert = await api.certificate(app.id);
  await new LoginPage(page).loginAs('officer');
  const officer = new OfficerPage(page);
  await officer.filter('Issued');
  await officer.withReason('Revoke', app.name, 'Business closed');
  await expect(officer.status()).toContainText(`${app.name}: now revoked`);

  const verify = new VerifyPage(page);
  await verify.goto();
  await verify.verify(cert.number, cert.signature);
  await verify.expectStatus('revoked');
});

test('a forged security code is reported as not valid', async ({ page, api }) => {
  const app = await api.application(['submit', 'pay', 'approve', 'issue']);
  const cert = await api.certificate(app.id);
  const verify = new VerifyPage(page);
  await verify.goto();
  await verify.verify(cert.number, cert.signature.slice(0, -1) + (cert.signature.endsWith('A') ? 'B' : 'A'));
  await verify.expectStatus('invalid');
  await expect(page.getByText(app.name)).toHaveCount(0);   // reveals nothing
});

test.describe('login and access control', () => {
  test('wrong password shows one generic error', async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login('citizen@permitpass.test', 'not-the-password');
    await expect(login.error()).toHaveText('Incorrect email or password');
    await expect(page).toHaveURL('/');
  });

  test('citizen cannot open the officer queue', async ({ page }) => {
    await new LoginPage(page).loginAs('citizen');
    await new CitizenPage(page).expectLoaded();
    await page.goto('/queue.html');
    await expect(page).toHaveURL(/\/my\.html$/);
  });

  test('pages that need login send anonymous visitors to the login page', async ({ page }) => {
    await page.goto('/my.html');
    await expect(page).toHaveURL('/');
  });

  test('citizen only sees their own applications', async ({ page, api }) => {
    const mine = await api.application();
    const res = await api.as('otherCitizen', 'POST', '/applications', { business_name: `Not mine ${Date.now()}`, kra_pin: 'P000000000A' });
    await new LoginPage(page).loginAs('citizen');
    await expect(new CitizenPage(page).row(mine.name)).toBeVisible();
    await expect(page.getByText(res.business_name)).toHaveCount(0);
  });

  test('log out ends the session', async ({ page }) => {
    await new LoginPage(page).loginAs('citizen');
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL('/');
    await page.goto('/my.html');
    await expect(page).toHaveURL('/');
  });
});

test('invalid KRA PIN is explained to the citizen', async ({ page }) => {
  await new LoginPage(page).loginAs('citizen');
  const citizen = new CitizenPage(page);
  await citizen.create('Bad Pin Ltd', 'B123');
  await expect(citizen.status()).toHaveClass(/error/);
  await expect(citizen.status()).toContainText('kra_pin');
});

test('a cancelled M-Pesa payment is explained and can be retried', async ({ page, api }) => {
  const app = await api.application(['submit']);
  await new LoginPage(page).loginAs('citizen');
  const citizen = new CitizenPage(page);
  await citizen.pay(app.name, '0700000032');                     // stub: user cancels on the phone
  await expect(citizen.row(app.name).locator('.badge')).toHaveText('submitted', { timeout: 15_000 });
  await expect(citizen.row(app.name)).toContainText('Payment failed: Request cancelled by user (M-Pesa code 1032)');
  await expect(citizen.status()).toContainText('did not go through');
  await citizen.pay(app.name);                                    // retry with a normal number
  await expect(citizen.row(app.name).locator('.badge')).toHaveText('paid', { timeout: 15_000 });
});

test('an invalid M-Pesa number is refused before any payment starts', async ({ page, api }) => {
  const app = await api.application(['submit']);
  await new LoginPage(page).loginAs('citizen');
  const citizen = new CitizenPage(page);
  await citizen.pay(app.name, '0812345678');
  await expect(citizen.status()).toHaveClass(/error/);
  await citizen.expectState(app.name, 'submitted');
});

test('a KRA PIN that is not registered is refused with a clear message', async ({ page }) => {
  // A999999999Z is "NotFound" in the KRA stub (mocks/README.md)
  await new LoginPage(page).loginAs('citizen');
  const citizen = new CitizenPage(page);
  const name = `Ghost Traders ${Date.now().toString(36)}`;
  await citizen.create(name, 'A999999999Z');
  await expect(citizen.status()).toHaveText('KRA PIN is not registered');
  await expect(citizen.row(name)).toHaveCount(0);
});

test.describe('without JavaScript', () => {
  test.use({ javaScriptEnabled: false });

  test('submitting the login form never puts the password in the URL (#25)', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Email').fill('citizen@permitpass.test');
    await page.getByLabel('Password').fill('PermitPass!2026');
    await Promise.all([page.waitForLoadState(), page.getByRole('button', { name: 'Log in' }).click()]);
    expect(page.url()).not.toContain('password');
    expect(page.url()).not.toContain('PermitPass');
  });
});

test('officer queue always shows the list for the selected filter, even if responses arrive out of order (#43)', async ({ page, api }) => {
  const paid = await api.application(['submit', 'pay']);
  const approved = await api.application(['submit', 'pay', 'approve']);
  await new LoginPage(page).loginAs('officer');
  const officer = new OfficerPage(page);
  await expect(officer.row(paid.name)).toBeVisible();

  // Hold the next "paid" list response for 1.5 s, so it arrives AFTER the "approved" one
  let held = false;
  await page.route(/\/applications\?state=paid/, async (route) => {
    if (!held) { held = true; await new Promise((r) => setTimeout(r, 1500)); }
    await route.continue();
  });
  await officer.act('Approve', paid.name);           // triggers a refresh of the paid list (held)
  await officer.filter('Approved, ready to issue');  // user moves on before it returns
  await page.waitForTimeout(2000);                   // the stale paid response has now arrived

  await expect(page.getByLabel('Status')).toHaveValue('approved');
  await expect(officer.row(approved.name)).toBeVisible();
  await expect(officer.row(approved.name).getByRole('button', { name: `Issue permit ${approved.name}` })).toBeVisible();
});

test('while a payment is pending, the citizen page polls with one request per refresh', async ({ page, api }) => {
  const app = await api.application(['submit']);
  await new LoginPage(page).loginAs('citizen');
  const citizen = new CitizenPage(page);
  const lists: number[] = [];
  page.on('request', (r) => { if (/\/applications\?limit=100$/.test(r.url())) lists.push(Date.now()); });
  await citizen.pay(app.name, '0700000000');            // never answers, so the page keeps polling
  await expect(citizen.row(app.name).locator('.badge')).toHaveText('payment_pending');
  const before = lists.length;
  await page.waitForTimeout(4500);                      // about two polling intervals
  const polled = lists.length - before;
  expect(polled).toBeGreaterThanOrEqual(2);
  expect(polled).toBeLessThanOrEqual(3);                // was double before the fix
});
