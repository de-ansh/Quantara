/** Number formats shared by every page, so the same figure never reads two ways. */

/** An index level: always two decimals, Indian digit grouping ("25,800.60", "83,919.71"). */
export const indexLevel = (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** "+1.12%" from 1.12 or from the API's "+1.12%" string; null when unknown. */
export const changePct = (v: number | string | null | undefined): number | null => {
    if (v === null || v === undefined || v === "") return null
    const n = typeof v === "number" ? v : Number(String(v).replace(/[%+\s]/g, ""))
    return Number.isFinite(n) ? n : null
}

/** "20 Nov" from "2026-11-20", read as a calendar day (no time-zone shift). */
export const shortDay = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number)
    return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
}

/** Today's date in India as "YYYY-MM-DD", the form NAV dates come in. */
export const todayInIndia = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" })

/** "NAV of 20 Nov" when a fund's price isn't today's (AMFI publishes once a day, after close); else null. */
export const staleNav = (priceDate: string | null | undefined) =>
    priceDate && priceDate !== todayInIndia() ? `NAV of ${shortDay(priceDate)}` : null
