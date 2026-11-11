import { test, expect, type Page } from '@playwright/test';

const analysis = {
  ticker: 'TCS.NS', overall_risk_score: 60, risk_level: 'Moderate', risk_band: '34-66',
  components: {
    volatility_score: 40, beta_score: 50, leverage_score: 30,
    earnings_stability_score: 70, sector_risk_score: 45, valuation_risk_score: 80,
  },
  component_weights: { volatility: 0.2, beta: 0.15, leverage: 0.2, earnings_stability: 0.15, sector: 0.1, valuation: 0.2 },
  explanation: 'TCS.NS has an overall risk score of 60.0.',
  max_drawdown: -0.48,
  drawdown_series: [
    { time: "Jan '26", historical: 100, projected: null },
    { time: "Jun '26", historical: 52, projected: 52 },
    { time: '+1M (Shock)', historical: null, projected: 45 },
  ],
  scenarios: [
    { id: 'a', name: 'Mild Rate Rise', type: 'Macro', impact_pct: -3, status: 'neg', factor_breakdown: { market_beta: -3 }, narrative: null },
    { id: 'b', name: 'Severe Slowdown', type: 'Macro', impact_pct: -25, status: 'neg', factor_breakdown: { market_beta: -25 }, narrative: null },
  ],
  factor_sensitivities: { market_beta: 0.9 },
  assumed_inputs: ['pe_ratio'],
};

async function open(page: Page, risk: object) {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [] } })
  );
  await page.route('**/api/v1/stocks/search**', route => route.fulfill({
    json: { stocks: Array.from({ length: 200 }, (_, i) => ({ ticker: `T${i}.NS` })), total_count: 200 },
  }));
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
  await page.route('**/api/v1/stocks/TCS.NS/risk', route => route.fulfill({ json: risk }));
  await page.route('**/api/v1/stocks/TCS.NS/correlation', route => route.fulfill({
    json: { ticker: 'TCS.NS', sector: 'IT', benchmark_ticker: '^NSEI', benchmark_correlation: 0.6, peers: [] },
  }));
  await page.goto('/risk/TCS.NS');
}

test('breakdown adds up, explains the drawdown floor and exports', async ({ page }) => {
  await open(page, analysis);
  await expect(page.getByTestId('factor-valuation')).toContainText('80.0/100 × 20% = +16.0 pts');
  await expect(page.getByTestId('factor-valuation')).toContainText('Estimated');
  await expect(page.getByTestId('factor-beta')).not.toContainText('Estimated');
  // weighted factors total 52.5, the score is 60
  await expect(page.getByText('Factors add up to 52.5. Raised by 7.5')).toBeVisible();
  await expect(page.getByRole('button', { name: /Severe Slowdown/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: /\bT11$/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /\bT12$/ })).toHaveCount(0);

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Data' }).click();
  expect((await download).suggestedFilename()).toBe('risk-TCS.NS.csv');
});

test('no price history means no drawdown numbers or chart', async ({ page }) => {
  await open(page, { ...analysis, assumed_inputs: ['price_history'] });
  await expect(page.getByText('No price history for TCS.NS yet.')).toBeVisible();
  await expect(page.getByTestId('factor-volatility')).toContainText('Estimated');
  await expect(page.locator('.recharts-responsive-container')).toHaveCount(0);
});

test('a failed request offers a retry instead of empty scores', async ({ page }) => {
  await open(page, analysis);
  await page.route('**/api/v1/stocks/NOPE.NS/risk', route => route.fulfill({ status: 500, json: { detail: 'x' } }));
  await page.route('**/api/v1/stocks/NOPE.NS/correlation', route => route.fulfill({ status: 500, json: { detail: 'x' } }));
  await page.goto('/risk/NOPE.NS');
  await expect(page.getByRole('alert')).toContainText('Could not load risk data', { timeout: 20000 });
});
