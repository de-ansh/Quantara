import { test, expect, type Page } from '@playwright/test';

async function signedIn(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [{ ticker: 'TCS.NS' }] } })
  );
  await page.route('**/api/v1/stocks/search**', route => route.fulfill({ json: { stocks: [], total_count: 0 } }));
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
}

test('markets shows live sections and says when a feed is down', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/market/overview', route => route.fulfill({ json: {
    indices: [{ name: 'NIFTY 50', last: 25044.65, change: 58, change_pct: 0.23 }],
    sector_indices: [{ name: 'NIFTY IT', last: 100, change: 1, change_pct: 1 }],
    breadth: { advances: 231, declines: 266, unchanged: 4 },
    flows: null,
    gainers: [{ ticker: 'TCS.NS', name: 'TCS', price: 3000, change_pct: 2.5 }],
    losers: [], sectors: [{ sector: 'Technology', stocks: 20, avg_change_pct: 0.5, avg_pe: 28.1 }],
  } }));
  await page.route('**/api/v1/market/themes', route => route.fulfill({ json: [
    { name: 'Defence', avg_change_pct: 1.1, members: [{ ticker: 'HAL.NS', name: 'HAL', change_pct: 1.1, return_1y_pct: null }] },
  ] }));
  await page.goto('/markets');
  await expect(page.getByText('25,044.65')).toBeVisible();
  await expect(page.getByText('231 up')).toBeVisible();
  await expect(page.getByText('Institutional flows unavailable from NSE right now.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'TCS', exact: true })).toHaveAttribute('href', '/research/TCS.NS');
  await page.getByText('Defence').click();
  await expect(page.getByRole('link', { name: 'HAL', exact: true })).toBeVisible();
});

test('events filter to the watchlist and switch tabs', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/market/events', route => route.fulfill({ json: {
    earnings: [
      { ticker: 'TCS.NS', company: 'Tata Consultancy', date: '2026-11-20', detail: null },
      { ticker: 'XYZ.NS', company: 'Xyz Ltd', date: '2026-11-21', detail: null },
    ],
    corporate_actions: [{ ticker: 'ITC.NS', company: 'ITC', subject: 'Dividend - Rs 5', kind: 'Dividend', ex_date: '2026-11-12', record_date: null }],
    ipos: null,
  } }));
  await page.goto('/events');
  await expect(page.getByText('Xyz Ltd')).toBeVisible();
  await page.getByLabel('Watchlist only').check();
  await expect(page.getByText('Xyz Ltd')).toHaveCount(0);
  await expect(page.getByText('Tata Consultancy')).toBeVisible();
  await page.getByLabel('Watchlist only').uncheck();
  await page.getByRole('button', { name: 'Corporate actions' }).click();
  await expect(page.getByText('Dividend - Rs 5')).toBeVisible();
  await page.getByRole('button', { name: 'IPOs' }).click();
  await expect(page.getByText('Unavailable from NSE right now.')).toBeVisible();
});

test('calculators compute known values and reject bad input', async ({ page }) => {
  await signedIn(page);
  await page.goto('/calculators');
  await expect(page.getByText('₹23,23,391')).toBeVisible(); // 10k a month, 12%, 10 years
  await page.getByRole('button', { name: 'Lumpsum' }).click();
  await expect(page.getByText('₹3,10,585')).toBeVisible();
  await page.getByLabel('Years').fill('0');
  await expect(page.getByText('Enter valid values')).toBeVisible();
  await page.getByRole('button', { name: 'CAGR' }).click();
  await expect(page.getByText('20.11%')).toBeVisible();
});

test('a chat can be shared after a warning, and read without signing in', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/chat/stream', route => route.fulfill({ body: 'Moderate risk.', contentType: 'text/plain' }));
  let shared = false;
  await page.route('**/api/v1/chat/share', route => { shared = true; return route.fulfill({ json: { token: 'tok123', messages: [], created_at: '2026-11-10T00:00:00' } }); });
  await page.goto('/calculators');
  await page.getByRole('button', { name: 'Open research assistant' }).click();
  await page.getByLabel('Message').fill('Is TCS risky?');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByText('Moderate risk.')).toBeVisible();
  await page.getByRole('button', { name: 'Share this chat' }).click();
  expect(shared).toBe(false);
  await expect(page.getByText('including anything about your holdings')).toBeVisible();
  await page.getByRole('button', { name: 'Create link' }).click();
  await expect(page.getByLabel('Share link')).toHaveValue(/\/shared\/tok123$/);
});

test('shared chat page needs no login', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.fulfill({ status: 401, json: { detail: 'no' } }));
  await page.route('**/api/v1/chat/shared/abc', route => route.fulfill({ json: {
    token: 'abc', created_at: '2026-11-10T00:00:00',
    messages: [{ role: 'user', content: 'Is TCS risky?' }, { role: 'assistant', content: 'Moderate **risk**.' }],
  } }));
  await page.goto('/shared/abc');
  await expect(page.getByText('Is TCS risky?')).toBeVisible();
  await expect(page).toHaveURL(/\/shared\/abc$/);
});

test('saved screens restore their filters', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/screens/', route => route.fulfill({ json: [
    { id: 1, name: 'My value', filters: { roe_min: '18', _market: 'india', _pe: '30', _beta: '1.5', _signals: '' }, sort: '-roe' },
  ] }));
  await page.goto('/explorer');
  await page.getByRole('button', { name: 'My value', exact: true }).click();
  await expect(page.getByLabel('Min ROE %')).toHaveValue('18');
});


test('an IPO can be analysed with a clear call, pros and cons', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/market/events', route => route.fulfill({ json: {
    earnings: [], corporate_actions: [],
    ipos: [{ symbol: 'STEEL', company: 'Steel Co Limited', status: 'Open', start_date: '2026-11-10', end_date: '2026-11-12', listing_date: null, price: 'Rs.78 to Rs.82', segment: 'EQ', subscribed_times: 3.2 }],
  } }));
  let asked = '';
  await page.route('**/api/v1/market/ipos/STEEL/analysis**', route => { asked = route.request().url(); return route.fulfill({ json: {
    issue: { company: 'Steel Co Limited', industry: 'Steel', price_range: 'Rs. 78 to Rs. 82', lot: '182 Equity Shares', fresh_issue_crore: 183.06, offer_for_sale_crore: null, offer_for_sale_share: 0, subscription: { qib: 35.5, total: 60.8 }, rhp_url: 'https://nsearchives.nseindia.com/content/ipo/RHP_STEEL.zip' },
    summary: 'Makes coated steel.', financials: 'Revenue up 20% a year.', valuation: '19.5x vs peers at 28x.',
    pros: ['Institutions bid 35.5x their quota'], cons: ['Cyclical demand'],
    recommendation: 'Apply', reasoning: 'Cheaper than peers with strong demand.', confidence: 72, read_prospectus: true,
  } }); });
  await page.goto('/events');
  await page.getByRole('button', { name: 'IPOs' }).click();
  await page.getByRole('button', { name: 'Analyze' }).click();
  await expect(page.getByText('Cheaper than peers with strong demand.')).toBeVisible();
  await expect(page.getByText('Institutions bid 35.5x their quota')).toBeVisible();
  await expect(page.getByText('Qualified', { exact: false })).toHaveCount(0);
  await expect(page.getByText('Institutions (QIB) 35.5x · Total 60.8x')).toBeVisible();
  expect(asked).toContain('series=EQ');
});


test('filings feed filters by category and search', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/market/filings**', route => route.fulfill({ json: [
    { ticker: 'COCHINSHIP.NS', company: 'Cochin Shipyard Limited', category: 'Updates', summary: 'Receipt of order for refit of a naval vessel.', filed_at: '2026-11-11 14:20:42', pdf_url: 'https://nsearchives.nseindia.com/a.pdf' },
    { ticker: 'TCS.NS', company: 'Tata Consultancy Services', category: 'Press Release', summary: 'Partnership announced.', filed_at: '2026-11-11 13:00:00', pdf_url: null },
  ] }));
  await page.goto('/filings');
  await expect(page.getByText('Receipt of order for refit of a naval vessel.')).toBeVisible();
  await page.getByRole('button', { name: /Press Release/ }).click();
  await expect(page.getByText('Receipt of order for refit')).toHaveCount(0);
  await expect(page.getByText('Partnership announced.')).toBeVisible();
  await page.getByRole('button', { name: /Press Release/ }).click();
  await page.getByLabel('Search filings').fill('naval');
  await expect(page.getByText('Partnership announced.')).toHaveCount(0);
});

test('declared results show growth and leaderboards', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/market/events', route => route.fulfill({ json: { earnings: [], corporate_actions: [], ipos: [] } }));
  const r = (ticker: string, profit: number, yoy: number) => ({ ticker, name: ticker, sector: 'Technology', market_cap: 1e12, quarter_end: '2026-09-30', filed_at: '2026-10-09T06:36:12', consolidated: true,
    revenue: 7.3188e11, profit, eps: 38.4, revenue_yoy_pct: 8.2, profit_yoy_pct: yoy, revenue_qoq_pct: 1.2, profit_qoq_pct: 2.0, pdf_url: null });
  await page.route('**/api/v1/market/earnings**', route => route.fulfill({ json: [r('TCS.NS', 1.3934e11, 12.5), r('WEAK.NS', 2e9, -30), r('TINY.NS', 1e6, 900)] }));
  await page.goto('/events');
  await page.getByRole('button', { name: 'Declared results' }).click();
  await expect(page.getByText('₹73,188 Cr').first()).toBeVisible();
  const growth = page.locator('div', { has: page.getByRole('heading', { name: 'Biggest profit growth (YoY)' }) }).last();
  await expect(growth.getByRole('link', { name: 'TCS' })).toBeVisible();
  await expect(growth.getByRole('link', { name: 'TINY' })).toHaveCount(0); // profit under ₹10 Cr
});

test('concalls list transcripts and open an AI summary', async ({ page }) => {
  await signedIn(page);
  const call = (ticker: string, kind: string, summary: string) => ({
    ticker, company: `${ticker.replace(".NS", "")} Ltd`, kind, summary, filed_at: '2026-11-12 11:20:33', pdf_url: `https://nsearchives.nseindia.com/corporate/${ticker}.pdf`,
  });
  await page.route('**/api/v1/market/concalls?**', route => route.fulfill({ json: [
    call('SBCL.NS', 'transcript', 'Transcript of earnings call -Q2 FY 2026-27'),
    call('SHILCTECH.NS', 'schedule', 'Schedule of meet'),
  ] }));
  await page.route('**/api/v1/market/concalls/SBCL/summary', route => route.fulfill({ json: {
    ...call('SBCL.NS', 'transcript', 'Revenue grew on export demand.'), quarter: 'Q2 FY27', tone: 'Positive',
    guidance: '20% revenue growth next year.', highlights: ['Exports up 30%'], concerns: ['Copper prices'],
  } }));
  await page.goto('/concalls');
  await expect(page.getByText('SBCL Ltd')).toBeVisible();
  await expect(page.getByText('SHILCTECH Ltd')).toHaveCount(0);  // transcripts tab by default
  await page.getByRole('button', { name: /^All/ }).click();
  await expect(page.getByText('SHILCTECH Ltd')).toBeVisible();
  await page.getByRole('button', { name: 'AI summary' }).click();
  await expect(page.getByText('Positive tone')).toBeVisible();
  await expect(page.getByText('20% revenue growth next year.')).toBeVisible();
  await expect(page.getByText('Copper prices')).toBeVisible();
});

test('deals filter by investor and side, with totals', async ({ page }) => {
  await signedIn(page);
  const deal = (ticker: string, client: string, side: string, value: number) => ({
    ticker, company: `${ticker.replace(".NS", "")} Ltd`, deal_date: '2026-11-11', kind: 'block', client, side, quantity: 1000, price: value / 1000, value,
  });
  await page.route('**/api/v1/market/deals?**', route => route.fulfill({ json: [
    deal('CPPLUS.NS', 'MOTILAL OSWAL MUTUAL FUND', 'BUY', 349_000_000),
    deal('COHANCE.NS', 'JASUB PROPERTY HOLDINGS LLP', 'SELL', 94_000_000),
  ] }));
  await page.goto('/deals');
  await expect(page.getByText('bought ₹34.9 Cr')).toBeVisible();
  await page.getByLabel('Search deals').fill('motilal');
  await expect(page.getByText('COHANCE Ltd')).toHaveCount(0);
  await expect(page.getByText('CPPLUS Ltd')).toBeVisible();
  await page.getByLabel('Search deals').fill('');
  await page.getByRole('button', { name: 'Sells', exact: true }).click();
  await expect(page.getByText('CPPLUS Ltd')).toHaveCount(0);
  await expect(page.getByText('1 deals')).toBeVisible();
});

test('indices open their constituents and ETFs filter by category', async ({ page }) => {
  await signedIn(page);
  const index = (name: string, category: string) => ({
    name, category, last: 25240.6, change_pct: -0.06, pe: 20.59, pb: 3.1, dividend_yield: 1.35, year_high: 26373.2,
    year_low: 22179.9, return_30d: 12.87, return_1y: -2.45, advances: 20, declines: 30,
  });
  await page.route('**/api/v1/market/indices', route => route.fulfill({ json: [
    index('NIFTY 50', 'Broad Market Indices'), index('NIFTY BANK', 'Sectoral Indices'),
  ] }));
  await page.route('**/api/v1/market/indices/NIFTY%2050', route => route.fulfill({ json: { index: null, members: [
    { ticker: 'TCS.NS', name: 'Tata Consultancy', sector: 'IT', price: 3100, change_pct: 3.33, pe: 24, market_cap: 1e13, return_1y_pct: -20 },
  ] } }));
  await page.route('**/api/v1/market/etfs', route => route.fulfill({ json: [
    { symbol: 'SILVERBEES', underlying: 'Domestic price of Silver', category: 'Silver', price: 171.78, change_pct: -2.86, nav: 176.66,
      premium_pct: -2.76, traded_value: 4.185e9, year_high: 360, year_low: 143.65, return_30d: -15.24, return_1y: 19.45 },
    { symbol: 'NIFTYBEES', underlying: 'Nifty 50 Index', category: 'Broad market', price: 280, change_pct: 0.1, nav: 280.4,
      premium_pct: -0.15, traded_value: 1.71e9, year_high: 300, year_low: 240, return_30d: 5, return_1y: -2 },
  ] }));
  await page.goto('/indices');
  await page.getByRole('button', { name: 'Sectoral Indices' }).click();
  await expect(page.getByRole('button', { name: 'NIFTY 50', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'All', exact: true }).click();
  await page.getByRole('button', { name: 'NIFTY 50', exact: true }).click();
  await expect(page.getByRole('link', { name: 'TCS', exact: true })).toBeVisible();
  await expect(page.getByText('1 stocks, largest first')).toBeVisible();

  await page.getByRole('tab', { name: 'ETFs' }).click();
  await expect(page.getByText('₹419 Cr')).toBeVisible();
  await expect(page.getByText('-2.76%')).toBeVisible();
  await page.getByRole('button', { name: /^Broad market/ }).click();
  await expect(page.getByText('SILVERBEES')).toHaveCount(0);
  await expect(page.getByText('NIFTYBEES')).toBeVisible();
});

test('technical presets send their filters and the table shows RSI and traded value', async ({ page }) => {
  await signedIn(page);
  const seen: URLSearchParams[] = [];
  await page.route('**/api/v1/stocks/search**', route => {
    seen.push(new URL(route.request().url()).searchParams);
    return route.fulfill({ json: { total_count: 1, stocks: [{
      ticker: 'HOT.NS', name: 'Hot Ltd', price: '₹100.00', cap: '₹1,000 Cr', risk: 50, signal: 'Neutral', status: 'up',
      pe: 20, beta: 1, rsi_14: 76.4, from_high_52w_pct: -1.2, turnover_1d: 9.5e9, tracked: true,
    }] } });
  });
  await page.goto('/explorer');
  await page.getByRole('button', { name: 'Most traded', exact: true }).click();
  await expect(page.getByLabel('Min avg traded value (₹ Cr/day)')).toHaveValue('100');
  await expect.poll(() => seen.some(p => p.get('turnover_min_cr') === '100' && p.get('sort') === '-turnover')).toBe(true);
  const row = page.getByRole('row', { name: /HOT\.NS/ });
  await expect(row).toContainText('76');
  await expect(row).toContainText('-1.2%');
  await expect(row).toContainText('₹950 Cr');
});

test('markets lists the most traded stocks', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/market/overview', route => route.fulfill({ json: {
    indices: null, sector_indices: null, breadth: null, flows: null, gainers: [], losers: [], sectors: [],
    most_traded: [{ ticker: 'HDFCBANK.NS', name: 'HDFC Bank', price: 980, change_pct: 0.5, turnover: 2.1e10 }],
  } }));
  await page.route('**/api/v1/market/themes', route => route.fulfill({ json: [] }));
  await page.goto('/markets');
  await expect(page.getByText('Most traded')).toBeVisible();
  await expect(page.getByText('₹2,100 Cr')).toBeVisible();
});
