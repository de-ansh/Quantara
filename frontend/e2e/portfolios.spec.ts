import { test, expect, type Page } from '@playwright/test';

const STOCK = {
  ticker: 'AAPL', name: 'Apple Inc.', price: '$189.42', cap: '$2.94T',
  risk: 14, signal: 'High', alpha: '+12.4%', status: 'up',
};

/** In-memory fake of the portfolio and watchlist APIs. */
async function mockApi(page: Page) {
  const state = { portfolios: [] as Record<string, unknown>[], watchlist: [] as typeof STOCK[], posted: [] as unknown[] };

  await page.addInitScript(() => {
    window.localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });

  // Session restore: the httpOnly refresh cookie is exchanged for an access token
  await page.route('**/api/v1/auth/refresh', route =>
    route.fulfill({ json: { access_token: 'mocked_jwt_token_xyz', token_type: 'bearer' } })
  );

  await page.route('**/api/v1/portfolio/**', async route => {
    const req = route.request();
    const id = Number(req.url().split('/portfolio/')[1]) || null;
    if (req.method() === 'GET') {
      return route.fulfill({ json: { portfolios: state.portfolios, total_count: state.portfolios.length } });
    }
    if (req.method() === 'POST') {
      const body = req.postDataJSON();
      state.posted.push(body);
      const now = new Date().toISOString();
      const created = { id: state.portfolios.length + 1, user_id: 1, created_at: now, updated_at: now, ...body };
      state.portfolios.push(created);
      return route.fulfill({ status: 201, json: created });
    }
    if (req.method() === 'DELETE' && id) {
      state.portfolios = state.portfolios.filter(p => p.id !== id);
      return route.fulfill({ status: 204, body: '' });
    }
    return route.fallback();
  });

  await page.route('**/api/v1/watchlist/**', async route => {
    const req = route.request();
    if (req.url().includes('/watchlist/alerts')) {
      return route.fulfill({ json: { alerts: [], unread_count: 0 } });
    }
    if (req.method() === 'POST') {
      state.watchlist = [STOCK];
      return route.fulfill({ status: 201, json: { items: state.watchlist } });
    }
    if (req.method() === 'DELETE') {
      state.watchlist = [];
      return route.fulfill({ status: 204, body: '' });
    }
    return route.fulfill({ json: { items: state.watchlist } });
  });

  await page.route('**/api/v1/stocks/search**', route =>
    route.fulfill({ json: { stocks: [STOCK], total_count: 1 } })
  );

  return state;
}

test.describe('Portfolios', () => {
  test('creates a portfolio and lists it', async ({ page }) => {
    const state = await mockApi(page);
    await page.goto('/portfolios');

    await expect(page.getByText('No portfolios yet')).toBeVisible();
    await page.getByRole('button', { name: 'New portfolio' }).first().click();

    await page.getByPlaceholder('Core growth').fill('Retirement');
    await page.getByLabel('Ticker').fill('aapl');
    await page.getByRole('spinbutton', { name: /Weight for/ }).fill('100');
    await page.getByRole('button', { name: 'Save portfolio' }).click();

    await expect(page.getByText('Retirement')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Simulate' })).toBeVisible();
    expect(state.posted).toEqual([
      { name: 'Retirement', description: null, initial_investment: 100000, positions: [{ ticker: 'AAPL', weight: 1, shares: 0, cost_basis: 0 }] },
    ]);
  });

  test('rejects weights that do not total 100%', async ({ page }) => {
    const state = await mockApi(page);
    await page.goto('/portfolios');
    await page.getByRole('button', { name: 'New portfolio' }).first().click();

    await page.getByPlaceholder('Core growth').fill('Half');
    await page.getByLabel('Ticker').fill('AAPL');
    await page.getByRole('spinbutton', { name: /Weight for/ }).fill('50');
    await page.getByRole('button', { name: 'Save portfolio' }).click();

    await expect(page.getByRole('alert')).toContainText('must total 100%');
    expect(state.posted).toEqual([]);
  });
});

test.describe('Watchlist', () => {
  test('starring a stock in Explorer adds it to the watchlist', async ({ page }) => {
    const state = await mockApi(page);
    await page.goto('/explorer');

    const star = page.getByRole('button', { name: 'Add AAPL to watchlist' }).first();
    await star.click();

    await expect(page.getByRole('button', { name: 'Remove AAPL from watchlist' }).first()).toHaveAttribute('aria-pressed', 'true');
    expect(state.watchlist.map(w => w.ticker)).toEqual(['AAPL']);
  });
});
