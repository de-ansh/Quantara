import { test, expect } from '@playwright/test';

test.describe('Dashboard E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Inject mock credentials in localStorage to bypass authentication check
    await page.addInitScript(() => {
      window.localStorage.setItem('quantara_token', 'mocked_jwt_token_xyz');
      window.localStorage.setItem(
        'quantara_user',
        JSON.stringify({ id: '1', email: 'analyst@quantara.com' })
      );
    });

    // Mock API requests for dashboard data
    await page.route('**/api/v1/market/status', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          vix: { value: 13.84, change_percent: -2.1 },
          alerts: [{ title: 'System Running Normally', severity: 'low' }],
        }),
      });
    });

    await page.route('**/api/v1/recommendations', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          recommendations: [
            {
              ticker: 'AAPL',
              rank: 1,
              scores: {
                research_score: 95,
                signal_score: 85,
                risk_alignment_score: 90,
                macro_fit_score: 80,
                final_score: 88,
              },
              explanation: 'Top stock pick.',
              reasoning_metadata: {},
            },
          ],
          total_count: 1,
          user_risk_level: 'MODERATE',
        }),
      });
    });

    await page.route('**/api/v1/signals', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          signals: [
            {
              id: 1,
              ticker: 'AAPL',
              signal_type: 'BULLISH_TREND',
              strength: 80,
              confidence: 90,
              timestamp: '2026-06-26T12:00:00Z',
              metadata: {},
            },
          ],
          total_count: 1,
        }),
      });
    });
  });

  test('should load the dashboard with correct metrics and mocked data', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Verify Title
    await expect(page.getByText('QUANTARA').first()).toBeVisible();

    // Verify Portfolio Risk Card
    await expect(page.locator('text=Portfolio Risk Score')).toBeVisible();

    // Verify Opportunities Table
    await expect(page.locator('table')).toBeVisible();
    await expect(page.locator('table').locator('text=AAPL').first()).toBeVisible();

    // Verify Signals
    await expect(page.locator('text=AAPL: BULLISH TREND Detected')).toBeVisible();
  });

  test('should navigate to Settings page and check theme toggles', async ({ page }) => {
    await page.goto('/');
    
    // Click Settings Link in navigation layout
    // Locate the settings link or icon by href or role
    const settingsLink = page.locator('a[href="/settings"]');
    await settingsLink.click();

    // Verify we navigated to Settings
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.locator('h1')).toContainText('System Settings');

    // Verify theme controls are present
    const lightThemeBtn = page.locator('text=Aero Light');
    const darkThemeBtn = page.locator('text=Institutional Dark');
    
    await expect(lightThemeBtn).toBeVisible();
    await expect(darkThemeBtn).toBeVisible();

    // Toggle theme to Aero Light
    await lightThemeBtn.click();
    
    // Check if the html/body class reflects light theme or localStorage holds light theme
    const activeThemeText = page.locator('text=Current visual theme:');
    await expect(activeThemeText).toContainText('LIGHT');
  });
});
