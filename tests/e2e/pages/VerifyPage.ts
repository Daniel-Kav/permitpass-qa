import { Page, expect } from '@playwright/test';

export class VerifyPage {
  constructor(private page: Page) {}

  readonly result = () => this.page.locator('#result .result');

  async goto() { await this.page.goto('/verify.html'); }

  async verify(number: string, sig: string) {
    await this.page.getByLabel('Certificate number').fill(number);
    await this.page.getByLabel('Security code').fill(sig);
    await this.page.getByRole('button', { name: 'Verify' }).click();
  }

  async expectStatus(status: 'valid' | 'invalid' | 'revoked' | 'expired') {
    await expect(this.result()).toHaveAttribute('data-status', status);
  }
}
