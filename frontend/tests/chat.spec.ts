import { test, expect } from '@playwright/test';

test('chat interface redirects to login if unauthenticated', async ({ page }) => {
  await page.goto('/chat');
  await expect(page).toHaveURL(/\/auth\/login/);
});

test('dashboard redirects to login if unauthenticated', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/auth\/login/);
});
