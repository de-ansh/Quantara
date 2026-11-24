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
        { kind: 'fund', ticker: '200001', name: 'Example Flexi Cap Fund - Direct Plan - Growth', sector: 'Equity Scheme - Flexi Cap Fund',
          currency: 'INR', shares: 20, avg_cost: 40, price: 50, market_value: 1000, cost_value: 800, unrealized_pnl: 200,
          unrealized_pnl_pct: 25, day_change: 10, weight_by_value: 11.1, price_date: '2020-01-03' },
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
  // A fund: named, not linked to a stock page, valued at NAV
  const fund = page.getByRole('row', { name: /Example Flexi Cap Fund/ });
  await expect(fund).toContainText('Mutual fund · Equity Scheme - Flexi Cap Fund');
  await expect(fund).toContainText('₹1,000.00');
  await expect(fund.getByRole('link')).toHaveCount(0);
  await expect(fund).toContainText('NAV of 3 Jan');  // an old NAV says so, instead of passing for today's move

  // Worst performer first; clicking the header flips the order
  const firstHolding = () => page.getByRole('rowheader').first();
  await expect(firstHolding()).toContainText('TCS.NS');  // +14.29%, below the fund (+25%) and AAPL (+33.33%)
  await page.getByRole('button', { name: 'Gain or loss' }).click();
  await expect(firstHolding()).toContainText('AAPL');
  await expect(page.getByRole('columnheader', { name: 'Gain or loss' })).toHaveAttribute('aria-sort', 'descending');
});

test('portfolios page totals every portfolio and shows each one\'s value, today and gain or loss', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  const portfolio = (id: number, name: string) => ({ id, name, description: null, initial_investment: 5000, positions: [], funds: [], created_at: now, updated_at: now });
  await page.route('**/api/v1/portfolio/', route => route.fulfill({
    json: { portfolios: [portfolio(1, 'Stocks'), portfolio(2, 'Funds'), portfolio(3, 'Ideas')], total_count: 3 },
  }));
  const totals = (mv: number, cost: number, day: number) => [{ currency: 'INR', market_value: mv, cost_value: cost,
    unrealized_pnl: mv - cost, unrealized_pnl_pct: ((mv - cost) / cost) * 100, day_change: day, sector_allocation: {} }];
  const perf = (id: number, t: object[]) => ({ portfolio_id: id, prices_as_of: now, weight_only_tickers: [], holdings: [], totals: t });
  await page.route('**/api/v1/portfolio/updates', route => route.fulfill({ json: { portfolios: [
    { portfolio_id: 1, name: 'Stocks', updates: {}, performance: perf(1, totals(9000, 10000, -300)) },
    { portfolio_id: 2, name: 'Funds', updates: {}, performance: perf(2, totals(6000, 5000, 60)) },
    { portfolio_id: 3, name: 'Ideas', updates: {}, performance: perf(3, []) },  // weights only: not valued
  ] } }));

  await page.goto('/portfolios');
  const all = page.getByRole('region', { name: 'All 2 portfolios together' });
  await expect(all).toContainText('₹15,000.00');   // 9,000 + 6,000
  await expect(all).toContainText('-₹240.00');     // -300 + 60
  await expect(all).toContainText('0.00%');        // -1,000 + 1,000: even overall
  const stocks = page.getByRole('region', { name: 'Stocks' });
  await expect(stocks).toContainText('₹9,000.00');
  await expect(stocks).toContainText('-₹1,000.00');
  await expect(stocks).toContainText('-10.00%');
  await expect(stocks).not.toContainText('invested');
  await expect(page.getByRole('region', { name: 'Ideas' })).toContainText(/5,000\s*invested/);  // no share counts: what was put in
});

test('a portfolio shows its asset mix and what is out of balance, with how much to move', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [
    { id: 7, name: 'Core', description: null, initial_investment: 1000, positions: [], funds: [], created_at: now, updated_at: now }], total_count: 1 } }));
  await page.route('**/api/v1/portfolio/7/performance', route => route.fulfill({ json: { portfolio_id: 7, prices_as_of: now, weight_only_tickers: [],
    holdings: [{ kind: 'stock', ticker: 'EXAMPLE.NS', name: 'Example Ltd', sector: 'Banks', currency: 'INR', shares: 5, avg_cost: 100, price: 100,
      market_value: 500, cost_value: 500, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, weight_by_value: 50 }],
    totals: [{ currency: 'INR', market_value: 1000, cost_value: 1000, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, sector_allocation: {} }] } }));
  await page.route('**/api/v1/portfolio/7/balance', route => route.fulfill({ json: { portfolio_id: 7, risk_level: null,
    mix: { INR: { equity: 75, cash: 25 } },
    flags: [{ kind: 'stock', title: 'Example Ltd is 50% of this portfolio', detail: 'Selling this much brings it to 20%.', currency: 'INR', ticker: 'EXAMPLE.NS', amount: 375 }] } }));

  await page.goto('/portfolios/7');
  const balance = page.getByRole('region', { name: 'Balance check' });
  await expect(balance).toContainText('75% equity · 25% cash');
  await expect(balance.getByRole('link', { name: 'Example Ltd is 50% of this portfolio' })).toHaveAttribute('href', '/research/EXAMPLE.NS');
  await expect(balance).toContainText('About ₹375.00');
  await expect(balance.getByRole('link', { name: 'Account' })).toBeVisible();  // no risk profile yet
  await expect(balance.getByRole('note')).toContainText('not investment advice');
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
  await expect(page.getByText('over 1Y')).toBeVisible();
  await expect(page.getByText('+12.50%')).toBeVisible();

  await page.getByRole('button', { name: '5Y' }).click();
  await expect(page.getByText('+140.10%')).toBeVisible();
  expect(ranges).toEqual(['1Y', '5Y']);
});

test('an NSE stock shows its shareholding pattern with quarter-on-quarter change', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/stocks/TCS.NS/shareholding', route => route.fulfill({ json: [
    { quarter: '2026-09-30', promoter_pct: 71.77, fii_pct: 9.01, dii_pct: 13.57, mf_pct: 5.65, retail_pct: 5.65, shareholders: 2579099 },
    { quarter: '2026-06-30', promoter_pct: 71.77, fii_pct: 10.11, dii_pct: 12.4, mf_pct: 5.1, retail_pct: 5.72, shareholders: 2600000 },
  ] }));
  await page.goto('/research/TCS.NS');
  const card = page.getByRole('region', { name: 'Shareholding pattern' });
  await expect(card).toBeVisible();
  await expect(card.getByRole('row', { name: /Foreign institutions/ })).toContainText('-1.10');
  await expect(card.getByRole('row', { name: /Domestic institutions/ })).toContainText('+1.17');
  await expect(card).toContainText('25,79,099 shareholders');
});
