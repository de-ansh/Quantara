import { test, expect } from '@playwright/test';
import { changePct, indexLevel } from '../src/lib/format';

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
