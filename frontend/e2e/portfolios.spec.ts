import { test, expect, type Page } from '@playwright/test';

const STOCK = {
  ticker: 'AAPL', name: 'Apple Inc.', price: '$189.42', cap: '$2.94T',
  risk: 14, signal: 'High', status: 'up',
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
  test('imports holdings from a broker CSV export, then saves them', async ({ page }) => {
    const state = await mockApi(page);
    await page.goto('/portfolios');
    await page.getByRole('button', { name: 'New portfolio' }).first().click();

    // Zerodha-style export: quoted thousands, a series suffix, the same stock twice, a zero-quantity row
    const csv = [
      'Instrument,Qty.,Avg. cost,LTP,Cur. val,P&L',
      'ITC,10,"400.00",412.3,"4,123.00",123',
      'M&M,5,"2,800.50",3000,"15,000.00",997.5',
      'IRFC-BE,100,120,130,13000,1000',
      'ITC,10,420,412.3,4123,-77',
      'GOLDBEES,0,50,55,0,0',
    ].join('\n');
    await page.getByLabel('Import holdings CSV').setInputFiles({ name: 'holdings.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });

    await expect(page.getByRole('status')).toContainText('Imported 3 holdings');
    await expect(page.getByRole('status')).toContainText('GOLDBEES: no quantity');
    await page.getByRole('button', { name: 'Save portfolio' }).click();

    await expect(page.getByText('My holdings')).toBeVisible();
    expect(state.posted).toEqual([{
      name: 'My holdings', description: null, initial_investment: 34203,  // 20 x 410 + 5 x 2800.5 + 100 x 120 = 34,202.5
      positions: [
        { ticker: 'ITC', weight: 0, shares: 20, cost_basis: 410 },
        { ticker: 'M&M', weight: 0, shares: 5, cost_basis: 2800.5 },
        { ticker: 'IRFC', weight: 0, shares: 100, cost_basis: 120 },
      ],
      funds: [],
    }]);
  });

  test('a Groww holdings statement (names and ISINs, no symbols) imports by ISIN', async ({ page }) => {
    const state = await mockApi(page);
    await page.goto('/portfolios');
    await page.getByRole('button', { name: 'New portfolio' }).first().click();
    const csv = [
      'Name,A Person',
      'Invested Value,10000.0',
      'Stock Name,ISIN,Quantity,Average buy price,Buy value,Closing price,Closing value,Unrealised P&L',
      'ITC LIMITED,INE154A01025,10.0,400.0,4000.0,410.0,4100.0,100.0',
      'INFOSYS LIMITED,INE009A01021,4.0,1500.0,6000.0,1450.0,5800.0,-200.0',
    ].join('\n');
    await page.getByLabel('Import holdings CSV').setInputFiles({ name: 'holdings.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
    await expect(page.getByRole('status')).toContainText('Imported 2 holdings');
    await page.getByRole('button', { name: 'Save portfolio' }).click();
    await expect(page.getByText('My holdings')).toBeVisible();
    // The server maps each ISIN to its NSE listing when it saves
    expect((state.posted[0] as { positions: unknown }).positions).toEqual([
      { ticker: 'INE154A01025', weight: 0, shares: 10, cost_basis: 400 },
      { ticker: 'INE009A01021', weight: 0, shares: 4, cost_basis: 1500 },
    ]);
  });

  test('an ".xls" that is really an HTML table imports, and a binary .xls says how to fix it', async ({ page }) => {
    const state = await mockApi(page);
    await page.goto('/portfolios');
    await page.getByRole('button', { name: 'New portfolio' }).first().click();
    const html = '<html><body><table><tr><th>Stock Name</th><th>ISIN</th><th>Qty</th><th>Avg Cost Price</th></tr>' +
      '<tr><td>ITC LTD</td><td>INE154A01025</td><td>10</td><td>400.00</td></tr></table></body></html>';
    await page.getByLabel('Import holdings CSV').setInputFiles({ name: 'holdings.xls', mimeType: 'application/vnd.ms-excel', buffer: Buffer.from(html) });
    await expect(page.getByRole('status')).toContainText('Imported 1 holding');
    await page.getByLabel('Import holdings CSV').setInputFiles({ name: 'old.xls', mimeType: 'application/vnd.ms-excel', buffer: Buffer.from([0xd0, 0xcf, 0x11, 0xe0, 0, 0, 0, 0]) });
    await expect(page.getByRole('alert')).toHaveText(/save it as .xlsx or CSV/);
    expect(state.posted).toEqual([]);
  });

  test('a Groww mutual funds file becomes fund holdings, matched by scheme name', async ({ page }) => {
    const state = await mockApi(page);
    let asked: unknown = null;
    await page.route('**/api/v1/portfolio/funds/match', route => {
      asked = route.request().postDataJSON();
      return route.fulfill({ json: { matches: [
        { scheme_code: 200001, name: 'Example Flexi Cap Fund - Direct Plan - Growth', nav: 50 },
        null,
      ] } });
    });
    await page.goto('/portfolios');
    await page.getByRole('button', { name: 'New portfolio' }).first().click();
    // Groww: personal details first, funds by name only, the same fund in two folios
    const csv = [
      'Name,A Person',
      'Total Investments,Current Portfolio Value',
      'Scheme Name,AMC,Category,Sub-category,Folio No.,Source,Units,Invested Value,Current Value,Returns,XIRR',
      'Example Flexi Cap Fund Direct Growth,Example Mutual Fund,Equity,Flexi Cap,111,Groww,10.5,420,525,105,9%',
      'Example Flexi Cap Fund Direct Growth,Example Mutual Fund,Equity,Flexi Cap,222,Groww,9.5,380,475,95,9%',
      'Unknown Fund Direct Growth,Some AMC,Debt,Liquid,333,Groww,1,100,101,1,5%',
    ].join('\n');
    await page.getByLabel('Import holdings CSV').setInputFiles({ name: 'funds.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });

    await expect(page.getByRole('status')).toContainText('Imported 1 mutual fund');
    await expect(page.getByRole('status')).toContainText('Unknown Fund Direct Growth: not a ticker symbol or a mutual fund we could match');
    expect(asked).toEqual({ funds: [
      { isin: null, name: 'Example Flexi Cap Fund Direct Growth' },
      { isin: null, name: 'Unknown Fund Direct Growth' },
    ] });
    await expect(page.getByText('Example Flexi Cap Fund - Direct Plan - Growth')).toBeVisible();
    await page.getByRole('button', { name: 'Save portfolio' }).click();
    await expect(page.getByText('My holdings')).toBeVisible();
    expect(state.posted).toEqual([{
      name: 'My holdings', description: null, initial_investment: 800, positions: [],
      funds: [{ scheme_code: 200001, units: 20, cost_basis: 40 }],  // two folios: 20 units for 800
    }]);
  });

  test('a file without symbol and quantity columns explains itself', async ({ page }) => {
    await mockApi(page);
    await page.goto('/portfolios');
    await page.getByRole('button', { name: 'New portfolio' }).first().click();
    await page.getByLabel('Import holdings CSV').setInputFiles({ name: 'x.csv', mimeType: 'text/csv', buffer: Buffer.from('Date,Amount\n2026-01-01,5') });
    await expect(page.getByRole('alert')).toHaveText(/symbol column and a quantity column/);
  });

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
      { name: 'Retirement', description: null, initial_investment: 100000, positions: [{ ticker: 'AAPL', weight: 1, shares: 0, cost_basis: 0 }], funds: [] },
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
