import { test, expect, type Page } from '@playwright/test';

const risk = (ticker: string, score: number, beta: number) => ({
  ticker, overall_risk_score: score, risk_level: 'Moderate', risk_band: '34-66',
  components: {
    volatility_score: 40, beta_score: 50, leverage_score: 30,
    earnings_stability_score: 70, sector_risk_score: 45, valuation_risk_score: 55,
  },
  explanation: '', max_drawdown: -0.2, drawdown_series: [],
  scenarios: [{ id: 'x', name: 'X', type: 'Shock', impact_pct: -12.5, status: 'neg', factor_breakdown: {}, narrative: null }],
  factor_sensitivities: { market_beta: beta }, assumed_inputs: [],
});

async function signedIn(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [] } })
  );
  await page.route('**/api/v1/stocks/search**', route => route.fulfill({ json: { stocks: [], total_count: 0 } }));
  await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [], total_count: 0 } }));
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
}

test('compares two stocks with real correlation data', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/v1/stocks/AAPL/risk', route => route.fulfill({ json: risk('AAPL', 30, 1.21) }));
  await page.route('**/api/v1/stocks/MSFT/risk', route => route.fulfill({ json: risk('MSFT', 25, 0.95) }));
  const simulate = page.waitForRequest('**/api/v1/portfolio/simulate');
  await page.route('**/api/v1/portfolio/simulate', route => route.fulfill({
    json: {
      asset_volatilities: { AAPL: 0.24, MSFT: 0.2 },
      correlation_matrix: { AAPL: { AAPL: 1, MSFT: 0.61 }, MSFT: { AAPL: 0.61, MSFT: 1 } },
      estimated_tickers: [],
    },
  }));

  await page.goto('/compare?tickers=AAPL,MSFT');

  const body = (await simulate).postDataJSON();
  expect(body.stocks).toEqual([{ ticker: 'AAPL', weight: 0.5 }, { ticker: 'MSFT', weight: 0.5 }]);
  const betaRow = page.getByRole('row', { name: /^Beta/ });
  await expect(betaRow).toContainText('1.21');
  await expect(betaRow).toContainText('0.95');
  await expect(page.getByRole('row', { name: /Annualized volatility/ })).toContainText('24.0%');
  await expect(page.getByRole('cell', { name: '0.61' }).first()).toBeVisible();
});

test('Explorer selection opens Simulation with those tickers', async ({ page }) => {
  await signedIn(page);
  const simulate = page.waitForRequest('**/api/v1/portfolio/simulate');
  await page.route('**/api/v1/portfolio/simulate', route => route.fulfill({ status: 503, json: { detail: 'offline' } }));
  await page.goto('/simulation?tickers=AAPL,TCS.NS');
  expect((await simulate).postDataJSON().stocks).toEqual([
    { ticker: 'AAPL', weight: 0.5 },
    { ticker: 'TCS.NS', weight: 0.5 },
  ]);

  const sidebar = page.locator('aside');
  await expect(sidebar.getByText('AAPL', { exact: true })).toBeVisible();
  await expect(sidebar.getByText('TCS.NS', { exact: true })).toBeVisible();
  await expect(sidebar.getByText('NVDA', { exact: true })).toHaveCount(0); // default preset not used
});
