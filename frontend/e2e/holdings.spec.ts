import { test, expect, type Page } from '@playwright/test';

async function signedIn(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [] } })
  );
  await page.route('**/api/v1/stocks/search**', route => route.fulfill({ json: { stocks: [], total_count: 0 } }));
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
}

test('holdings page shows value, P&L and separate currency totals', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  await page.route('**/api/v1/portfolio/', route => route.fulfill({
    json: { portfolios: [{ id: 7, name: 'Core', description: null, initial_investment: 100000, positions: [], created_at: now, updated_at: now }], total_count: 1 },
  }));
  await page.route('**/api/v1/portfolio/7/performance', route => route.fulfill({
    json: {
      portfolio_id: 7,
      prices_as_of: now,
      weight_only_tickers: ['GLD'],
      holdings: [
        { ticker: 'AAPL', name: 'Apple', sector: 'Technology', currency: 'USD', shares: 10, avg_cost: 150, price: 200,
          market_value: 2000, cost_value: 1500, unrealized_pnl: 500, unrealized_pnl_pct: 33.33, day_change: 100, weight_by_value: 100 },
        { ticker: 'TCS.NS', name: 'TCS', sector: 'IT', currency: 'INR', shares: 2, avg_cost: 3500, price: 4000,
          market_value: 8000, cost_value: 7000, unrealized_pnl: 1000, unrealized_pnl_pct: 14.29, day_change: -200, weight_by_value: 100 },
      ],
      totals: [
        { currency: 'INR', market_value: 8000, cost_value: 7000, unrealized_pnl: 1000, unrealized_pnl_pct: 14.29, day_change: -200, sector_allocation: { IT: 100 } },
        { currency: 'USD', market_value: 2000, cost_value: 1500, unrealized_pnl: 500, unrealized_pnl_pct: 33.33, day_change: 100, sector_allocation: { Technology: 100 } },
      ],
    },
  }));

  await page.goto('/portfolios/7');

  await expect(page.getByRole('heading', { name: 'Core' })).toBeVisible();
  await expect(page.getByText('USD holdings')).toBeVisible();
  await expect(page.getByText('INR holdings')).toBeVisible();
  const aapl = page.getByRole('row', { name: /AAPL/ });
  await expect(aapl).toContainText('$2,000.00');
  await expect(aapl).toContainText('+$500.00');
  await expect(page.getByRole('row', { name: /TCS\.NS/ })).toContainText('-₹200.00');
  await expect(page.getByText('Not valued (weight only, no share count): GLD')).toBeVisible();
});

test('stock detail shows a price chart with range switching', async ({ page }) => {
  await signedIn(page);
  const ranges: string[] = [];
  await page.route('**/api/v1/stocks/AAPL/history**', route => {
    const range = new URL(route.request().url()).searchParams.get('range') ?? '';
    ranges.push(range);
    return route.fulfill({
      json: { ticker: 'AAPL', range, change_pct: range === '5Y' ? 140.1 : 12.5,
        points: [{ date: '2026-01-02', close: 300 }, { date: '2026-06-01', close: 337.5 }] },
    });
  });

  await page.goto('/research/AAPL');
  await expect(page.getByText('Price History')).toBeVisible();
  await expect(page.getByText('+12.50%')).toBeVisible();

  await page.getByRole('button', { name: '5Y' }).click();
  await expect(page.getByText('+140.10%')).toBeVisible();
  expect(ranges).toEqual(['1Y', '5Y']);
});
