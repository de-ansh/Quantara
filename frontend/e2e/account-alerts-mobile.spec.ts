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

    await page.getByRole('link', { name: 'Portfolios' }).click();
    await expect(page).toHaveURL(/\/portfolios$/);
    await expect.poll(offscreen).toBe(true);
  });
});
