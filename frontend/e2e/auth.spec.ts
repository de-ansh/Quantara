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

  test('should redirect unauthenticated users attempting to access /risk and /simulation', async ({ page }) => {
    // Navigate directly to private routes without token in storage
    await page.goto('/risk');
    await expect(page).toHaveURL(/\/login/);

    await page.goto('/simulation');
    await expect(page).toHaveURL(/\/login/);
  });

  test('should allow user to open profile dropdown and log out', async ({ page }) => {
    // Inject mock authenticated session in localStorage before loading
    await page.addInitScript(() => {
      localStorage.setItem('quantara_token', 'mock_jwt_token_123');
      localStorage.setItem(
        'quantara_user',
        JSON.stringify({
          id: '1',
          email: 'analyst@quantara.com',
          risk_level: 'Moderate',
          volatility_tolerance: 60.0,
        })
      );
    });

    // Mock API requests
    await page.route('**/api/v1/**', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
    });

    await page.goto('/');
    await expect(page).toHaveURL('/');

    // Click profile dropdown trigger
    const userTrigger = page.getByText('analyst');
    await expect(userTrigger).toBeVisible();
    await userTrigger.click();

    // Verify dropdown content
    await expect(page.getByText('Account Profile')).toBeVisible();
    const logoutBtn = page.getByText('Sign Out Session');
    await expect(logoutBtn).toBeVisible();

    // Click logout
    await logoutBtn.click();

    // Should redirect to login and clear token
    await expect(page).toHaveURL(/\/login/);
    const token = await page.evaluate(() => localStorage.getItem('quantara_token'));
    expect(token).toBeNull();
  });
});

