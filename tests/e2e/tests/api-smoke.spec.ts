// Week-1 placeholder that runs against the API until the web app lands in week 3.
// Rules for this suite: page objects in ../pages, web-first assertions only, no fixed sleeps.
import { test, expect } from '@playwright/test';

const API = process.env.API_URL || 'http://localhost:8000';

test('API health endpoint responds', async ({ request }) => {
  const res = await request.get(`${API}/health`);
  expect(res.ok()).toBeTruthy();
  expect(await res.json()).toEqual({ status: 'ok' });
});
