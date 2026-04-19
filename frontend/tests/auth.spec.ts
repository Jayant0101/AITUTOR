import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/AI Tutor/);
});

test('login page accessibility', async ({ page }) => {
  await page.goto('/auth/login');
  const emailInput = page.locator('input[type="email"]');
  await expect(emailInput).toBeVisible();
  
  const passwordInput = page.locator('input[type="password"]');
  await expect(passwordInput).toBeVisible();
});
