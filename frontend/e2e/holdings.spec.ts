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

test('the portfolios page checks the balance of all portfolios together and says where to sell', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  const portfolio = (id: number, name: string) => ({ id, name, description: null, initial_investment: 5000, positions: [], funds: [], created_at: now, updated_at: now });
  await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [portfolio(1, 'Broker A'), portfolio(2, 'Broker B')], total_count: 2 } }));
  const totals = [{ currency: 'INR', market_value: 1000, cost_value: 1000, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, sector_allocation: {} }];
  const perf = (id: number) => ({ portfolio_id: id, prices_as_of: now, weight_only_tickers: [], holdings: [], totals });
  await page.route('**/api/v1/portfolio/updates', route => route.fulfill({ json: { portfolios: [
    { portfolio_id: 1, name: 'Broker A', updates: {}, performance: perf(1) },
    { portfolio_id: 2, name: 'Broker B', updates: {}, performance: perf(2) },
  ] } }));
  await page.route('**/api/v1/portfolio/balance**', route => route.fulfill({ json: { portfolio_id: null, risk_level: 'Moderate',
    target: { equity: 70, debt: 20, cash: 5, gold: 5, max_stock: 20, max_sector: 35, is_default: true }, mix: { INR: { equity: 100 } },
    flags: [{ kind: 'stock', title: 'Example Ltd is 60% of all your portfolios', detail: 'Selling this much brings it to 20%.', currency: 'INR', ticker: 'EXAMPLE.NS', amount: 1000 }],
    plan: [{ action: 'sell', asset_class: 'equity', amount: 600, currency: 'INR', ticker: 'EXAMPLE.NS', name: 'Example Ltd', reason: 'over your company limit', gain: 50, held_in: ['Broker A', 'Broker B'] },
      { action: 'add', asset_class: 'debt', amount: 600, currency: 'INR', ticker: null, name: null, reason: 'below target', gain: null, held_in: [] }] } }));

  await page.goto('/portfolios');
  const all = page.getByRole('region', { name: 'Balance across all portfolios' });
  await expect(all).toContainText('Example Ltd is 60% of all your portfolios');
  await expect(all).toContainText('over your company limit · in Broker A, Broker B');
  await expect(all).toContainText('a debt fund or bond ETF');
});

test('a portfolio shows its mix against the target, a rebalancing plan, new money and a saved target', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [
    { id: 7, name: 'Core', description: null, initial_investment: 1000, positions: [], funds: [], created_at: now, updated_at: now }], total_count: 1 } }));
  await page.route('**/api/v1/portfolio/7/performance', route => route.fulfill({ json: { portfolio_id: 7, prices_as_of: now, weight_only_tickers: [],
    holdings: [{ kind: 'stock', ticker: 'EXAMPLE.NS', name: 'Example Ltd', sector: 'Banks', currency: 'INR', shares: 5, avg_cost: 100, price: 100,
      market_value: 500, cost_value: 500, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, weight_by_value: 50 }],
    totals: [{ currency: 'INR', market_value: 1000, cost_value: 1000, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, sector_allocation: {} }] } }));
  let target = { equity: 70, debt: 20, cash: 5, gold: 5, max_stock: 20, max_sector: 35, is_default: true };
  const requested: string[] = [];
  await page.route('**/api/v1/portfolio/7/balance**', route => {
    const money = new URL(route.request().url()).searchParams.get('new_money');
    requested.push(money ?? '');
    return route.fulfill({ json: { portfolio_id: 7, risk_level: 'Moderate', target, mix: { INR: { equity: 90, cash: 10 } },
      flags: [{ kind: 'stock', title: 'Example Ltd is 50% of this portfolio', detail: 'Selling this much brings it to 20%.', currency: 'INR', ticker: 'EXAMPLE.NS', amount: 375 }],
      plan: money ? [{ action: 'add', asset_class: 'debt', amount: 500, currency: 'INR', ticker: null, name: null, reason: 'below target', gain: null }]
        : [{ action: 'sell', asset_class: 'equity', amount: 200, currency: 'INR', ticker: 'EXAMPLE.NS', name: 'Example Ltd', reason: 'over your company limit', gain: 40 },
           { action: 'add', asset_class: 'debt', amount: 200, currency: 'INR', ticker: null, name: null, reason: 'below target', gain: null }] } });
  });
  let saved: unknown = null;
  await page.route('**/api/v1/portfolio/target-mix', route => {
    saved = route.request().postDataJSON();
    target = { ...(saved as typeof target), is_default: false };
    return route.fulfill({ json: target });
  });

  await page.goto('/portfolios/7');
  const balance = page.getByRole('region', { name: 'Balance check' });
  await expect(balance).toContainText('90% target 70%');
  await expect(balance).toContainText('starting point for a Moderate investor');
  await expect(balance.getByRole('link', { name: 'Example Ltd is 50% of this portfolio' })).toHaveAttribute('href', '/research/EXAMPLE.NS');
  await expect(balance).toContainText('About ₹375.00');
  await expect(balance).toContainText('over your company limit');
  await expect(balance).toContainText('(gain ₹40.00)');
  await expect(balance).toContainText('a debt fund or bond ETF');
  await expect(balance).toContainText('import your tradebook for real figures');
  await expect(balance.getByRole('note')).toContainText('not investment advice');

  await balance.getByLabel('Adding new money?').fill('500');
  await balance.getByRole('button', { name: 'Update plan' }).click();
  await expect(balance).toContainText('your ₹500.00');
  await expect(balance).not.toContainText('over your company limit');
  expect(requested).toContain('500');

  await balance.getByRole('button', { name: 'Change target' }).click();
  const form = balance.getByRole('form', { name: 'Target mix' });
  await form.getByLabel('equity').fill('60');
  await expect(form).toContainText('Total 90%');
  await expect(form.getByRole('button', { name: 'Save target' })).toBeDisabled();
  await form.getByLabel('debt').fill('30');
  await form.getByRole('button', { name: 'Save target' }).click();
  await expect.poll(() => saved).toEqual({ equity: 60, debt: 30, cash: 5, gold: 5, max_stock: 20, max_sector: 35 });
  await expect(balance).toContainText('Your saved target');
});

test('a portfolio imports its tradebook and the plan shows the tax split, the wait hint and the total tax', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [
    { id: 7, name: 'Core', description: null, initial_investment: 1000, positions: [], funds: [], created_at: now, updated_at: now }], total_count: 1 } }));
  await page.route('**/api/v1/portfolio/7/performance', route => route.fulfill({ json: { portfolio_id: 7, prices_as_of: now, weight_only_tickers: [],
    holdings: [{ kind: 'stock', ticker: 'EXAMPLE.NS', name: 'Example Ltd', sector: 'Banks', currency: 'INR', shares: 5, avg_cost: 100, price: 100,
      market_value: 500, cost_value: 500, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, weight_by_value: 50 }],
    totals: [{ currency: 'INR', market_value: 1000, cost_value: 1000, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, sector_allocation: {} }] } }));
  let imported = false;
  await page.route('**/api/v1/portfolio/7/balance**', route => route.fulfill({ json: { portfolio_id: 7, risk_level: 'Moderate',
    target: { equity: 70, debt: 20, cash: 5, gold: 5, max_stock: 20, max_sector: 35, is_default: true }, mix: { INR: { equity: 100 } }, flags: [],
    plan_tax: imported ? 1250 : null, exemption_left: imported ? 100000 : null,
    plan: [{ action: 'sell', asset_class: 'equity', amount: 300, currency: 'INR', ticker: 'EXAMPLE.NS', name: 'Example Ltd', reason: 'long-term gain, taxed at 12.5%',
      gain: 60, short_term_gain: imported ? 10 : null, long_term_gain: imported ? 50 : null, wait_until: imported ? '2030-07-01' : null },
      { action: 'add', asset_class: 'debt', amount: 300, currency: 'INR', ticker: null, name: null, reason: 'below target', gain: null }] } }));
  let sent: { trades: unknown[] } | null = null;
  await page.route('**/api/v1/portfolio/7/trades', route => {
    if (route.request().method() === 'PUT') {
      sent = route.request().postDataJSON();
      imported = true;
      return route.fulfill({ json: { imported_at: now, trades: 2, first_trade: '2028-01-05', excluded: [], warnings: [], xirr: 14.2,
        gaps: [{ ticker: 'OTHER.NS', portfolio_shares: 10, tradebook_shares: 4 }] } });
    }
    return route.fulfill({ json: null });
  });

  await page.goto('/portfolios/7');
  const balance = page.getByRole('region', { name: 'Balance check' });
  await expect(balance).toContainText('import your tradebook for real figures');
  const tradebook = page.getByRole('region', { name: 'Tradebook' });
  await expect(tradebook).toContainText('assumes the worst');

  await tradebook.getByLabel('Tradebook files').setInputFiles({ name: 'tradebook.csv', mimeType: 'text/csv', buffer: Buffer.from(
    'symbol,trade_date,trade_type,quantity,price\nEXAMPLE,2028-01-05,buy,4,80\nEXAMPLE,2029-08-01,buy,1,90\n') });
  await expect(tradebook).toContainText('+14.20%');
  await expect(tradebook).toContainText('OTHER.NS: 10 held, 4 in the tradebook');
  expect(sent!.trades).toHaveLength(2);
  await expect(balance).toContainText('Short-term +₹10.00 · long-term +₹50.00');
  await expect(balance).toContainText('part turns long-term on');
  await expect(balance).toContainText('₹1,250.00');
  await expect(balance).toContainText(/₹1,?00,000\.00 of long-term gains is still tax-free/);  // grouping follows the browser locale
});

test('the balance check shows the biggest exposures counting what funds own', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [
    { id: 7, name: 'Core', description: null, initial_investment: 1000, positions: [], funds: [], created_at: now, updated_at: now }], total_count: 1 } }));
  await page.route('**/api/v1/portfolio/7/performance', route => route.fulfill({ json: { portfolio_id: 7, prices_as_of: now, weight_only_tickers: [],
    holdings: [{ kind: 'stock', ticker: 'EXAMPLE.NS', name: 'Example Ltd', sector: 'Banks', currency: 'INR', shares: 5, avg_cost: 100, price: 100,
      market_value: 500, cost_value: 500, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, weight_by_value: 50 }],
    totals: [{ currency: 'INR', market_value: 1000, cost_value: 1000, unrealized_pnl: 0, unrealized_pnl_pct: 0, day_change: 0, sector_allocation: {} }] } }));
  await page.route('**/api/v1/portfolio/7/balance**', route => route.fulfill({ json: { portfolio_id: 7, risk_level: 'Moderate',
    target: { equity: 70, debt: 20, cash: 5, gold: 5, max_stock: 20, max_sector: 35, is_default: true }, mix: { INR: { equity: 80, debt: 20 } },
    flags: [{ kind: 'stock', title: 'Example Ltd is 30% of this portfolio, counting your funds', detail: "That's ₹500 directly and ₹100 through 1 fund (Example Fund).", currency: 'INR', ticker: 'EXAMPLE.NS', amount: 100 }],
    plan: [], exposures: [
      { name: 'Example Ltd', ticker: 'EXAMPLE.NS', direct: 500, via_funds: 100, funds: ['Example Fund'], pct: 30 },
      { name: 'Unlisted Co', ticker: null, direct: 0, via_funds: 50, funds: ['Example Fund'], pct: 2.5 }],
    funds_looked_through: ['Example Fund'], funds_not_looked_through: ['Newer Fund'], holdings_as_of: '2030-01-31' } }));

  await page.goto('/portfolios/7');
  const balance = page.getByRole('region', { name: 'Balance check' });
  await expect(balance).toContainText('Example Ltd is 30% of this portfolio, counting your funds');
  const row = balance.getByRole('row', { name: /Example Ltd/ });
  await expect(row).toContainText('₹500.00');
  await expect(row).toContainText('₹100.00');
  await expect(row).toContainText('via Example Fund');
  await expect(balance.getByRole('row', { name: /Unlisted Co/ })).toContainText('2.5%');
  await expect(balance).toContainText('from portfolios published for');
  await expect(balance).toContainText('Not yet looked through: Newer Fund');
});

test('a stock page shows your position across portfolios, and nothing when you hold none', async ({ page }) => {
  await signedIn(page);
  const now = new Date().toISOString();
  const holding = (shares: number, cost: number, mv: number, day: number) => ({ kind: 'stock', ticker: 'EXAMPLE.NS', name: 'Example Ltd',
    sector: null, currency: 'INR', shares, avg_cost: cost / shares, price: mv / shares, market_value: mv, cost_value: cost,
    unrealized_pnl: mv - cost, unrealized_pnl_pct: ((mv - cost) / cost) * 100, day_change: day, weight_by_value: null });
  const perf = (id: number, holdings: object[]) => ({ portfolio_id: id, prices_as_of: now, weight_only_tickers: [], holdings, totals: [] });
  await page.route('**/api/v1/portfolio/updates', route => route.fulfill({ json: { portfolios: [
    { portfolio_id: 1, name: 'Long term', updates: {}, performance: perf(1, [holding(10, 1000, 1200, 20)]) },
    { portfolio_id: 2, name: 'Trading', updates: {}, performance: perf(2, [holding(30, 3000, 2800, -10)]) },
  ] } }));

  await page.goto('/research/EXAMPLE.NS');
  const mine = page.getByRole('region', { name: 'Your position' });
  await expect(mine).toContainText('40 shares at ₹100.00 average cost');
  await expect(mine).toContainText('₹4,000.00');   // 1,200 + 2,800
  await expect(mine).toContainText('+₹10.00');     // 20 - 10 today
  await expect(mine).toContainText('₹0.00');       // +200 - 200: even overall
  await expect(mine.getByRole('link', { name: 'Trading' })).toHaveAttribute('href', '/portfolios/2');

  await page.goto('/research/OTHER.NS');
  await expect(page.getByRole('heading', { name: 'Key numbers' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Your position' })).toHaveCount(0);
});

test('a stock page shows what you own of it through your funds, even with no shares held directly', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/portfolio/updates', route => route.fulfill({ json: { portfolios: [] } }));
  await page.route('**/api/v1/portfolio/exposure/FUNDED.NS', route => route.fulfill({ json: { ticker: 'FUNDED.NS', via_funds: 1500,
    funds: [{ name: 'Example Fund - Direct Plan - Growth', amount: 1000, weight: 4.5 }, { name: 'Other Fund', amount: 500, weight: 2 }],
    holdings_as_of: '2030-01-31' } }));

  await page.goto('/research/FUNDED.NS');
  const mine = page.getByRole('region', { name: 'Your position' });
  await expect(mine).toContainText("You don't hold it directly, only through your funds");
  await expect(mine).toContainText('Through your funds: ₹1,500.00');
  await expect(mine).toContainText('Example Fund: ₹1,000.00 (4.5% of the fund)');
  await expect(mine).toContainText('From fund portfolios published for');
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
