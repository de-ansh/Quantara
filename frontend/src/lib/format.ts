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

/** Market cap the way readers expect: ₹ in crore (lakh crore when huge), $ in B/T. */
export const marketCap = (v: number | null | undefined, indian: boolean) => {
    if (v === null || v === undefined || !(v > 0)) return "—"
    if (indian) {
        const crore = v / 1e7
        return crore >= 1e5
            ? `₹${(crore / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 2 })} L Cr`
            : `₹${crore.toLocaleString("en-IN", { maximumFractionDigits: crore >= 100 ? 0 : 1 })} Cr`
    }
    const [div, unit] = v >= 1e12 ? [1e12, "T"] : v >= 1e9 ? [1e9, "B"] : [1e6, "M"]
    return `$${(v / div).toLocaleString("en-US", { maximumFractionDigits: 2 })}${unit}`
}
