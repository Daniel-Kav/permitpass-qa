import { Page, expect } from '@playwright/test';

export class OfficerPage {
  constructor(private page: Page) {}

  readonly heading = () => this.page.getByRole('heading', { name: 'Officer queue', level: 1 });
  readonly status = () => this.page.getByRole('status');
  row(name: string) { return this.page.getByRole('row', { name: new RegExp(name) }); }

  async expectLoaded() { await expect(this.heading()).toBeVisible(); }
  async filter(label: string) { await this.page.getByLabel('Status').selectOption({ label }); }

  async act(action: 'Approve' | 'Issue permit', name: string) {
    await this.page.getByRole('button', { name: `${action} ${name}` }).click();
  }

  async withReason(action: 'Reject' | 'Revoke', name: string, reason: string) {
    await this.page.getByRole('button', { name: `${action} ${name}` }).click();
    const row = this.row(name);
    await row.getByLabel('Reason').fill(reason);
    await row.getByRole('button', { name: `Confirm ${action.toLowerCase()}` }).click();
  }
}
