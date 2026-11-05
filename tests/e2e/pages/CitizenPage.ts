import { Page, expect } from '@playwright/test';

export class CitizenPage {
  constructor(private page: Page) {}

  readonly heading = () => this.page.getByRole('heading', { name: 'My applications', level: 1 });
  readonly status = () => this.page.getByRole('status');
  row(name: string) { return this.page.getByRole('row', { name: new RegExp(name) }); }

  async expectLoaded() { await expect(this.heading()).toBeVisible(); }

  async create(name: string, kraPin: string) {
    await this.page.getByLabel('Business name').fill(name);
    await this.page.getByLabel('KRA PIN').fill(kraPin);
    await this.page.getByRole('button', { name: 'Create application' }).click();
  }

  async submit(name: string) { await this.page.getByRole('button', { name: `Submit ${name}` }).click(); }
  async pay(name: string) { await this.page.getByRole('button', { name: new RegExp(`^Pay KES \\d+ for ${name}$`) }).click(); }
  async expectState(name: string, state: string) { await expect(this.row(name).locator('.badge')).toHaveText(state); }
}
