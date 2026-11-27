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
  await page.route('**/api/v1/audit/logs**', route => route.fulfill({ json: { logs: [], total_count: 0 } }));
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
}

test('price alert form creates an alert for the ticker', async ({ page }) => {
  await signedIn(page);
  const alerts: Record<string, unknown>[] = [];
  await page.route('**/api/v1/alerts/price/**', async route => {
    const req = route.request();
    if (req.method() === 'POST') {
      const body = req.postDataJSON();
      const created = { id: alerts.length + 1, triggered_at: null, triggered_price: null, ...body };
      alerts.push(created);
      return route.fulfill({ status: 201, json: created });
    }
    return route.fulfill({ json: alerts });
  });

  await page.goto('/research/NVDA');
  await page.getByLabel('Direction').selectOption('above');
  await page.getByLabel('Target price').fill('250');
  await page.getByRole('button', { name: 'Set alert' }).click();

  await expect(page.getByText('above $250')).toBeVisible();
  expect(alerts).toEqual([expect.objectContaining({ ticker: 'NVDA', direction: 'above', target_price: 250 })]);
});

test('a numbers-only Avoid shows as Weak numbers; the AI verdict keeps Avoid', async ({ page }) => {
  await signedIn(page);
  let basis: 'data' | 'ai' = 'data';
  await page.route('**/api/v1/recommendations/NVDA/verdict', route => route.fulfill({ json: {
    verdict: 'Avoid', final_score: 35, reasons: [], missing: basis === 'data' ? ['research report'] : [],
    user_risk_level: 'Moderate', basis, pros: [], cons: ['Weak return on equity (5.0%)'],
  } }));

  await page.goto('/research/NVDA');
  const card = page.getByRole('region', { name: 'Verdict' });
  await expect(card.getByText('Weak numbers', { exact: true })).toBeVisible();
  await expect(card.getByText(/not a call to sell/)).toBeVisible();

  basis = 'ai';
  await page.reload();
  await expect(card.getByText('Avoid', { exact: true })).toBeVisible();
  await expect(card.getByText(/not a call to sell/)).toHaveCount(0);
});

test('account saves your horizon and preferred sectors, and ideas mark those sectors', async ({ page }) => {
  await signedIn(page);
  let profile = { id: 1, email: 'analyst@quantara.com', risk_level: 'Moderate', volatility_tolerance: 50, investment_horizon: 60, sector_preferences: {} };
  let saved: Record<string, unknown> | null = null;
  await page.route('**/api/v1/users/me', route => route.fulfill({ json: profile }));
  await page.route('**/api/v1/users/risk-profile', route => {
    saved = route.request().postDataJSON();
    profile = { ...profile, ...saved };
    return route.fulfill({ json: profile });
  });
  const idea = (ticker: string, sector: string) => ({ ticker, rank: 1, explanation: '', reasoning_metadata: { risk_score: 30, stock_sector: sector },
    scores: { research_score: 80, signal_score: 50, risk_alignment_score: 80, macro_fit_score: 50, final_score: 75 } });
  await page.route('**/api/v1/recommendations', route => route.fulfill({ json: {
    recommendations: [idea('ENERGY1.NS', 'Energy'), idea('BANK1.NS', 'Financials')], total_count: 2, user_risk_level: 'Moderate' } }));

  await page.goto('/account');
  await expect(page.getByLabel("When you'll need the money")).toHaveValue('60');
  await page.getByLabel("When you'll need the money").fill('18');
  await page.getByRole('button', { name: 'Energy' }).click();
  await expect(page.getByRole('button', { name: 'Energy' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Save risk profile' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved.' })).toBeVisible();
  expect(saved).toMatchObject({ investment_horizon: 18, sector_preferences: { Energy: 1 } });

  await page.goto('/');
  const ideas = page.getByRole('region', { name: /Ideas for/ });
  await expect(ideas.getByRole('row', { name: /ENERGY1/ })).toContainText('your sector');
  await expect(ideas.getByRole('row', { name: /BANK1/ })).not.toContainText('your sector');
});

test('account deletion needs password and confirmation, then signs out', async ({ page }) => {
  await signedIn(page);
  let deleteBody: unknown = null;
  await page.route('**/api/v1/users/me', route => {
    if (route.request().method() === 'DELETE') {
      deleteBody = route.request().postDataJSON();
      return route.fulfill({ status: 204, body: '' });
    }
    return route.fulfill({ json: { id: 1, email: 'analyst@quantara.com', risk_level: 'Moderate', volatility_tolerance: 50, investment_horizon: 12, sector_preferences: {} } });
  });

  await page.goto('/account');
  await page.getByRole('button', { name: 'Delete account' }).click();
  const confirm = page.getByRole('button', { name: 'Permanently delete' });
  await expect(confirm).toBeDisabled();
  await page.getByLabel('Confirm with your password').fill('password');
  await expect(confirm).toBeDisabled(); // still needs the checkbox
  await page.getByLabel('I understand this cannot be undone').check();
  await confirm.click();

  await expect(page).toHaveURL(/\/login/);
  expect(deleteBody).toEqual({ password: 'password' });
});

test.describe('phone layout', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  test('navigation is a drawer that closes after choosing a page', async ({ page }) => {
    await signedIn(page);
    await page.route('**/api/v1/portfolio/', route => route.fulfill({ json: { portfolios: [], total_count: 0 } }));
    await page.goto('/');

    const nav = page.locator('aside').first();
    const offscreen = async () => (await nav.boundingBox())!.x + (await nav.boundingBox())!.width <= 0;
    expect(await offscreen()).toBe(true);

    await page.getByRole('button', { name: 'Open navigation' }).click();
    await expect.poll(async () => (await nav.boundingBox())!.x).toBe(0);

    await page.getByRole('link', { name: 'Portfolios', exact: true }).click();
    await expect(page).toHaveURL(/\/portfolios$/);
    await expect.poll(offscreen).toBe(true);
  });
});
