import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should redirect unauthenticated users to login page', async ({ page }) => {
    // Mock API requests to return 401 Unauthorized so redirect is triggered
    await page.route('**/api/v1/**', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
    });

    // Navigate to dashboard root
    await page.goto('/');
    
    // Expect redirection to login
    await expect(page).toHaveURL(/\/login/);
    
    // Check that institutional login title is present
    await expect(page.getByText('Institutional Login')).toBeVisible();
  });

  test('should display login fields and allow typing credentials', async ({ page }) => {
    await page.goto('/login');
    
    // Selectors for work email and access key
    const emailInput = page.locator('#email');
    const passwordInput = page.locator('#password');
    const submitBtn = page.locator('button[type="submit"]');
    
    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(submitBtn).toBeVisible();
    
    // Fill credentials
    await emailInput.fill('analyst@quantara.com');
    await passwordInput.fill('secure_token_1234');
    
    // Verify values typed
    await expect(emailInput).toHaveValue('analyst@quantara.com');
    await expect(passwordInput).toHaveValue('secure_token_1234');
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');
    
    // Mock the backend auth endpoint to return 401 Unauthorized
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid credentials provided' }),
      });
    });

    await page.locator('#email').fill('wrong@quantara.com');
    await page.locator('#password').fill('wrongpassword');
    await page.locator('button[type="submit"]').click();
    
    // Verify error message container appears
    const errorContainer = page.locator('text=Request failed with status code 401');
    await expect(errorContainer).toBeVisible();
  });
});
