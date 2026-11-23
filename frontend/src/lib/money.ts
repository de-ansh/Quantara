import type { CurrencyTotals } from "@/hooks/usePortfolios"

/** Amounts and changes for holdings views: "+₹1,234.50", "-$20.00", "+3.20%". */
const SYMBOL = { USD: "$", INR: "₹" } as const

export const money = (v: number | null | undefined, currency: "USD" | "INR", signed = false) => {
    if (v === null || v === undefined) return "—"
    const sign = signed && v > 0 ? "+" : v < 0 ? "-" : ""
    return `${sign}${SYMBOL[currency]}${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`)
export const tone = (v: number | null | undefined) => (!v ? "text-muted-foreground" : v > 0 ? "text-q-risk-low" : "text-q-risk-high")

/** Today's move as a percent of yesterday's value. */
export const dayPct = (value: number | null, change: number | null) =>
    change !== null && value !== null && value - change > 0 ? (change / (value - change)) * 100 : null

/** Add up several portfolios' totals, one row per currency (rupees and dollars are never summed). */
export function sumTotals(groups: CurrencyTotals[][]): CurrencyTotals[] {
    const by = new Map<CurrencyTotals["currency"], CurrencyTotals>()
    for (const t of groups.flat()) {
        const s = by.get(t.currency) ?? { ...t, market_value: 0, cost_value: 0, unrealized_pnl: 0, day_change: 0, sector_allocation: {} }
        by.set(t.currency, {
            ...s,
            market_value: s.market_value + t.market_value,
            cost_value: s.cost_value + t.cost_value,
            unrealized_pnl: s.unrealized_pnl + t.unrealized_pnl,
            day_change: s.day_change + t.day_change,
        })
    }
    return [...by.values()].map(t => ({ ...t, unrealized_pnl_pct: t.cost_value ? (t.unrealized_pnl / t.cost_value) * 100 : null }))
}
