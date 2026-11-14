/** Read a broker's holdings export (CSV) into symbol, quantity and average cost per share. */

export interface ImportedHolding {
    ticker: string
    shares: number
    cost: number // average cost per share; 0 when the file has none
}

export interface HoldingsImport {
    holdings: ImportedHolding[]
    skipped: string[] // human-readable reasons, one per dropped row
}

// Header names brokers use, compared lower-cased with spaces and dots removed
const SYMBOL = ["instrument", "symbol", "tradingsymbol", "stocksymbol", "scrip", "scripname", "stock", "stockname", "nsesymbol", "ticker"]
const QUANTITY = ["qty", "quantity", "quantityavailable", "availableqty", "netqty", "holdingqty", "totalqty", "shares"]
const AVG_COST = ["avgcost", "averagecost", "avgprice", "averageprice", "buyavg", "avgbuyprice", "averagebuyprice", "buyprice", "costprice", "avgrate"]

const norm = (s: string) => s.toLowerCase().replace(/[\s._()₹-]/g, "")

/** Split one CSV line, honouring double quotes ("1,234.50" stays one field). */
export function splitCsvLine(line: string): string[] {
    const out: string[] = []
    let field = ""
    let quoted = false
    for (let i = 0; i < line.length; i++) {
        const c = line[i]
        if (quoted) {
            if (c === '"' && line[i + 1] === '"') { field += '"'; i++ }
            else if (c === '"') quoted = false
            else field += c
        } else if (c === '"') quoted = true
        else if (c === ",") { out.push(field.trim()); field = "" }
        else field += c
    }
    out.push(field.trim())
    return out
}

const number = (s: string | undefined) => {
    const n = Number((s ?? "").replace(/[₹$,\s]/g, ""))
    return Number.isFinite(n) ? n : NaN
}

/** Exchange-series suffixes on NSE symbols (ITC-EQ, IRFC-BE) aren't part of the ticker. */
const cleanSymbol = (s: string) => s.trim().toUpperCase().replace(/-(EQ|BE|BZ|SM|ST)$/, "")

export function parseHoldingsCsv(text: string): HoldingsImport {
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter(l => l.trim())
    // Some exports open with a few summary lines; the header is the first row naming a symbol and a quantity
    const headerAt = lines.findIndex(l => {
        const cols = splitCsvLine(l).map(norm)
        return cols.some(c => SYMBOL.includes(c)) && cols.some(c => QUANTITY.includes(c))
    })
    if (headerAt < 0) {
        throw new Error("Couldn't find a header row with a symbol column and a quantity column.")
    }
    const header = splitCsvLine(lines[headerAt]).map(norm)
    const pick = (names: string[]) => names.map(n => header.indexOf(n)).find(i => i >= 0) ?? -1
    const [symCol, qtyCol, costCol] = [pick(SYMBOL), pick(QUANTITY), pick(AVG_COST)]

    const merged = new Map<string, { shares: number; spent: number; costed: number }>()
    const skipped: string[] = []
    for (const line of lines.slice(headerAt + 1)) {
        const cells = splitCsvLine(line)
        const symbol = cleanSymbol(cells[symCol] ?? "")
        const shares = number(cells[qtyCol])
        if (!symbol || /^total/i.test(symbol)) continue  // blank or a totals row
        if (!/^[A-Z0-9&.^-]{1,20}$/.test(symbol)) { skipped.push(`${symbol}: not a ticker symbol`); continue }
        if (!(shares > 0)) { skipped.push(`${symbol}: no quantity`); continue }
        const cost = costCol >= 0 ? number(cells[costCol]) : 0
        const row = merged.get(symbol) ?? { shares: 0, spent: 0, costed: 0 }
        // The same stock on two lines (e.g. pledged and free shares): add up, averaging the cost over the
        // shares that have one, so a line without a cost doesn't drag the average down
        const known = cost > 0
        merged.set(symbol, {
            shares: row.shares + shares,
            spent: row.spent + (known ? shares * cost : 0),
            costed: row.costed + (known ? shares : 0),
        })
    }
    const holdings = [...merged].map(([ticker, { shares, spent, costed }]) => ({
        ticker, shares, cost: costed > 0 ? Math.round((spent / costed) * 100) / 100 : 0,
    }))
    return { holdings, skipped }
}
