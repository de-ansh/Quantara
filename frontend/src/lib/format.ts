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
