/**
 * Display name for the numbers-only call (the API still sends "Avoid").
 * In the 2023–25 backtest its Avoids did no worse than the median stock, so it describes the numbers
 * instead of reading as a sell call. The AI verdict's Avoid is unaffected.
 */
export const WEAK_NUMBERS = "Weak numbers"

export function dataCallLabel(call: string): string {
    return call === "Avoid" ? WEAK_NUMBERS : call
}
