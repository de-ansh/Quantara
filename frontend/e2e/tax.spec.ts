import { test, expect } from '@playwright/test';

test('a Zerodha tradebook becomes a harvesting plan', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [] } })
  );
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
  let sent: unknown = null;
  await page.route('**/api/v1/tax/harvest', route => {
    sent = route.request().postDataJSON();
    return route.fulfill({ json: {
      financial_year: '2026-27', realized_short_term: 40000, realized_long_term: 0, tax_so_far: 8320, exemption_left: 125000,
      tax_free_harvest: [{ symbol: 'ITC.NS', bought: '2024-06-01', quantity: 1000, gain: 100000 }],
      tax_free_total: 100000, tax_free_future_saving: 13000,
      loss_harvest: [{ symbol: 'ZOMATO.NS', bought: '2026-08-01', quantity: 100, loss: -5000, long_term: false }],
      loss_harvest_saving: 1040, turning_long_term: [], lots: [], warnings: ['IRFC: sold 100 more shares than the files show being bought'], no_price: [],
    } });
  });

  await page.goto('/tax');
  // Console's columns, a summary line first, an intraday-style duplicate and a non-trade row
  const csv = [
    'Tradebook for ABC123',
    'symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time',
    'ITC,INE154A01025,2024-06-01,NSE,EQ,EQ,buy,false,1000.000000,300.000000,1,1,2024-06-01T10:00:00',
    'ZOMATO,INE758T01015,01-08-2026,NSE,EQ,EQ,BUY,false,100,"300.00",2,2,',
    'M&M,INE101A01026,15-Mar-2025,NSE,EQ,EQ,sell,false,5,2800,3,3,',
    'SOMETHING ODD,,2026-01-01,NSE,EQ,EQ,buy,false,1,1,4,4,',
  ].join('\n');
  await page.getByLabel('Tradebook CSV files').setInputFiles([{ name: 'tradebook.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) }]);

  await expect(page.getByText('This financial year (FY 2026-27) so far')).toBeVisible();
  expect(sent).toEqual({ trades: [
    { symbol: 'ITC', date: '2024-06-01', side: 'buy', quantity: 1000, price: 300 },
    { symbol: 'ZOMATO', date: '2026-08-01', side: 'buy', quantity: 100, price: 300 },
    { symbol: 'M&M', date: '2025-03-15', side: 'sell', quantity: 5, price: 2800 },
  ] });
  await expect(page.getByText(/realise ₹1,00,000 of long-term/)).toBeVisible();
  await expect(page.getByText(/cut this year's tax by ₹1,040/)).toBeVisible();
  await expect(page.getByRole('note')).toContainText('IRFC: sold 100 more shares');
  await expect(page.getByText('1 row skipped')).toBeVisible();
});

test('a tradebook saved as .xlsx is read too, date cells included', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('quantara_user', JSON.stringify({ id: '1', email: 'analyst@quantara.com' }));
  });
  await page.route('**/api/v1/**', route => route.fulfill({ json: {} }));
  await page.route('**/api/v1/watchlist/**', route =>
    route.fulfill({ json: route.request().url().includes('alerts') ? { alerts: [], unread_count: 0 } : { items: [] } })
  );
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ json: { access_token: 'tok' } }));
  let sent: unknown = null;
  await page.route('**/api/v1/tax/harvest', route => {
    sent = route.request().postDataJSON();
    return route.fulfill({ json: {} });
  });

  await page.goto('/tax');
  // e2e/fixtures/tradebook.xlsx: a title row, then Console's columns; ITC's date is a real Excel date cell
  await page.getByLabel('Tradebook CSV files').setInputFiles(new URL('./fixtures/tradebook.xlsx', import.meta.url).pathname);
  await expect.poll(() => sent).toEqual({ trades: [
    { symbol: 'ITC', date: '2024-06-01', side: 'buy', quantity: 1000, price: 300.5 },
    { symbol: 'M&M', date: '2025-03-15', side: 'sell', quantity: 5, price: 2800 },
  ] });
});
