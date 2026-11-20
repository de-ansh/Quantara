/** Amounts and changes for holdings views: "+₹1,234.50", "-$20.00", "+3.20%". */
const SYMBOL = { USD: "$", INR: "₹" } as const

export const money = (v: number | null | undefined, currency: "USD" | "INR", signed = false) => {
    if (v === null || v === undefined) return "—"
    const sign = signed && v > 0 ? "+" : v < 0 ? "-" : ""
    return `${sign}${SYMBOL[currency]}${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`)
export const tone = (v: number | null | undefined) => (!v ? "text-muted-foreground" : v > 0 ? "text-q-risk-low" : "text-q-risk-high")
