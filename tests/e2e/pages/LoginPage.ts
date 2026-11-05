import { Page, expect } from '@playwright/test';
import { PASSWORD, USERS, UserKey } from '../fixtures';

export class LoginPage {
  constructor(private page: Page) {}

  readonly email = () => this.page.getByLabel('Email');
  readonly password = () => this.page.getByLabel('Password');
  readonly error = () => this.page.getByRole('alert');

  async goto() {
    await this.page.goto('/');
    await expect(this.page.getByRole('heading', { name: 'Log in' })).toBeVisible();
  }

  async login(email: string, password: string) {
    await this.email().fill(email);
    await this.password().fill(password);
    await this.page.getByRole('button', { name: 'Log in' }).click();
  }

  async loginAs(user: UserKey) {
    await this.goto();
    await this.login(USERS[user], PASSWORD);
  }
}
