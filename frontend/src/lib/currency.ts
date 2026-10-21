/**
 * Multi-market currency and ticker formatting utility.
 */

export function isIndianAsset(ticker?: string): boolean {
  if (!ticker) return false
  const t = ticker.toUpperCase()
  return t.endsWith(".NS") || t.endsWith(".BO") || t.includes(".NS") || t.includes(".BO")
}

export function getCurrencySymbol(ticker?: string): string {
  return isIndianAsset(ticker) ? "₹" : "$"
}

export function cleanTickerDisplay(ticker?: string): string {
  if (!ticker) return ""
  return ticker.replace(/\.(NS|BO)$/i, "")
}

export function getMarketLabel(ticker?: string): string {
  if (!ticker) return "US"
  const t = ticker.toUpperCase()
  if (t.endsWith(".NS")) return "NSE"
  if (t.endsWith(".BO")) return "BSE"
  return "NYSE/NASDAQ"
}

export function formatAssetPrice(val: number | string | null | undefined, ticker?: string): string {
  if (val === null || val === undefined || val === "") return "—"
  const sym = getCurrencySymbol(ticker)

  if (typeof val === "string") {
    // If already contains currency symbol, return as is
    if (val.startsWith("$") || val.startsWith("₹")) return val
    const parsed = parseFloat(val.replace(/[^0-9.-]+/g, ""))
    if (isNaN(parsed)) return val
    return `${sym}${parsed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return `${sym}${val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
