import { test, expect } from '@playwright/test';

test.describe('Dashboard E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // A remembered profile plus a (mocked) refresh cookie restores the session
    await page.addInitScript(() => {
      window.localStorage.setItem(
        'quantara_user',
        JSON.stringify({ id: '1', email: 'analyst@quantara.com' })
      );
    });

    // Session restore: the httpOnly refresh cookie is exchanged for an access token
    await page.route('**/api/v1/auth/refresh', route =>
      route.fulfill({ json: { access_token: 'mocked_jwt_token_xyz', token_type: 'bearer' } })
    );

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
              reasoning_metadata: { risk_score: 31.5 },
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

  test('dashboard shows the market, ideas with plain columns, and signals in words', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible();

    const ideas = page.getByRole('region', { name: /Ideas for a moderate investor/ });
    const aaplRow = ideas.getByRole('row', { name: /AAPL/ });
    await expect(aaplRow).toContainText('88.0'); // match score
    await expect(aaplRow).toContainText('Low · 31.5'); // risk, in words and number
    await expect(aaplRow).toContainText('Strong'); // signal score above 70

    const signals = page.getByRole('region', { name: 'Recent signals' });
    await expect(signals).toContainText('AAPL · Bullish trend');
    await expect(signals).toContainText('Neutral'); // direction in words, not only colour (no direction in its data)
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

test('dashboard shows each portfolio with its holdings and their news', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [] } })
  );
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
  const holding = (over: object) => ({ kind: 'stock', sector: null, currency: 'INR', avg_cost: 0, price: 0, cost_value: 0,
    unrealized_pnl: null, unrealized_pnl_pct: null, day_change: null, weight_by_value: null, shares: 1, ...over });
  await page.route('**/api/v1/portfolio/updates', route => route.fulfill({ json: { portfolios: [{
    portfolio_id: 7, name: 'Core',
    performance: {
      portfolio_id: 7, prices_as_of: null, weight_only_tickers: [],
      totals: [{ currency: 'INR', market_value: 9100, cost_value: 8000, unrealized_pnl: 1100, unrealized_pnl_pct: 13.75, day_change: 90, sector_allocation: {} }],
      holdings: [
        holding({ ticker: 'TCS.NS', name: 'TCS', market_value: 4000, day_change: -40, unrealized_pnl_pct: 5 }),
        holding({ ticker: 'ITC.NS', name: 'ITC', market_value: 4100, day_change: 100, unrealized_pnl_pct: 36.67 }),
        holding({ kind: 'fund', ticker: '200001', name: 'Example Flexi Cap Fund - Direct Plan - Growth', market_value: 1000, day_change: 30 }),
      ],
    },
    updates: { 'ITC.NS': [
      { kind: 'verdict', day: '2026-11-20', text: 'Verdict changed: Hold → Buy', tone: 'good', upcoming: false },
      { kind: 'event', day: '2026-11-25', text: 'Board meeting on results', tone: 'neutral', upcoming: true },
    ] },
  }] } }));

  await page.goto('/');
  const core = page.getByRole('article', { name: 'Core' });
  await expect(core).toContainText('₹9,100.00');
  await expect(core).toContainText('Today +₹90.00');
  await expect(core).toContainText('1 with news');
  // The holding with news comes first, then the biggest movers
  const rows = core.getByRole('listitem').filter({ has: page.getByRole('link') });
  await expect(rows.first()).toContainText('ITC.NS');
  await expect(rows.first()).toContainText('Verdict changed: Hold → Buy');
  await expect(rows.first()).toContainText('25 Nov');
  await expect(core).toContainText('Example Flexi Cap Fund - Direct Plan - Growth');
  await expect(core.getByText('+2.50%').first()).toBeVisible();  // ITC: 100 on 4,000
});
