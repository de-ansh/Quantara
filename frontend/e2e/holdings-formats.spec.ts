import { test, expect } from '@playwright/test';
import { parseHoldingsCsv } from '../src/lib/holdingsCsv';

// Holdings exports as each broker words them. Few brokers document their columns, so these come from
// sample files and guides; the reader matches loosely so a reworded header still lands
const BROKERS: [string, string[], { ticker: string; shares: number; cost: number }[]][] = [
  ['Zerodha Kite', ['Instrument,Qty.,Avg. cost,LTP,Cur. val,P&L', 'ITC,10,400,410,4100,100'],
    [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['Zerodha Console', ['Holdings statement', 'Symbol,ISIN,Sector,Quantity Available,Quantity Discrepant,Quantity Long Term,Quantity Pledged (Margin),Quantity Pledged (Loan),Average Price,Previous Closing Price,Unrealized P&L',
    'ITC,INE154A01025,FMCG,10,0,10,0,0,400,410,100'], [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['Groww', ['Stock Name,ISIN,Quantity,Average buy price,Buy value,Closing price,Closing value,Unrealised P&L',
    'ITC LIMITED,INE154A01025,10,400,4000,410,4100,100'], [{ ticker: 'INE154A01025', shares: 10, cost: 400 }]],
  ['Upstox', ['Scrip,Quantity,Average Price,Exchange', 'ITC,10,400,NSE'], [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['Angel One', ['Symbol,ISIN,Quantity,Avg Price,LTP,Current Value,P&L', 'ITC-EQ,INE154A01025,10,400,410,4100,100'],
    [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['ICICI Direct', ['Stock Symbol,Company Name,ISIN Code,Qty,Average Cost Price,Current Market Price,Value At Cost',
    'ITC,ITC LIMITED,INE154A01025,10,400,410,4000'], [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['ICICI Direct, no average', ['Company Name,ISIN Code,Qty,Value At Cost,Realized Profit / Loss', 'ITC LIMITED,INE154A01025,10,4000,0'],
    [{ ticker: 'INE154A01025', shares: 10, cost: 400 }]],
  ['HDFC Securities', ['Stock Name,ISIN,Quantity,Avg Cost Price,Market Price,Market Value', 'ITC LTD,INE154A01025,10,400,410,4100'],
    [{ ticker: 'INE154A01025', shares: 10, cost: 400 }]],
  ['Kotak Securities', ['Security Name,ISIN,Qty,Avg. Buy Price (Rs.),LTP (Rs.),Mkt Value (Rs.)', 'ITC LTD,INE154A01025,10,"400.00",410,"4,100.00"'],
    [{ ticker: 'INE154A01025', shares: 10, cost: 400 }]],
  ['Dhan', ['Name,Symbol,Qty,Avg Cost,LTP,Current Value', 'ITC Ltd,ITC,10,400,410,4100'], [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['5paisa', ['Symbol,Exch,Qty,Avg Rate,LTP,Market Value', 'ITC,NSE,10,400,410,4100'], [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['Fyers', ['Symbol,Qty,Buy Avg,LTP,P&L', 'NSE:ITC-EQ,10,400,410,100'], [{ ticker: 'ITC', shares: 10, cost: 400 }]],
  ['Depository statement', ['ISIN,Security Name,Current Bal,Free Bal,Value', 'INE154A01025,ITC LIMITED,10,10,4100'],
    [{ ticker: 'INE154A01025', shares: 10, cost: 0 }]],
];

for (const [broker, lines, want] of BROKERS) {
  test(`reads a ${broker} holdings export`, () => {
    const { holdings, skipped } = parseHoldingsCsv(lines.join('\n'));
    expect(skipped).toEqual([]);
    expect(holdings).toMatchObject(want);
    expect(holdings).toHaveLength(want.length);
  });
}
