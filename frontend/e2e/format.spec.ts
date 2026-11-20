import { test, expect } from '@playwright/test';
import { changePct, indexLevel, marketCap } from '../src/lib/format';

test('index levels always show two decimals', () => {
  expect(indexLevel(25800.6)).toBe('25,800.60');
  expect(indexLevel(83919.71)).toBe('83,919.71');
  expect(indexLevel(null)).toBe('—');
});

test('changes parse from numbers or the API strings', () => {
  expect(changePct('+1.12%')).toBe(1.12);
  expect(changePct('-2.02%')).toBe(-2.02);
  expect(changePct(0.5)).toBe(0.5);
  expect(changePct('')).toBeNull();
});

test('market caps read in crore for Indian stocks and B/T for US ones', () => {
  expect(marketCap(3.74e12, true)).toBe('₹3.74 L Cr');   // ₹3,74,000 Cr
  expect(marketCap(6.33e9, true)).toBe('₹633 Cr');
  expect(marketCap(4.5e8, true)).toBe('₹45 Cr');
  expect(marketCap(3.74e12, false)).toBe('$3.74T');
  expect(marketCap(null, true)).toBe('—');
});
