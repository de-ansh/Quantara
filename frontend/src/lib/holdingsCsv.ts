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

// Header names brokers use, compared lower-cased with spaces, dots and brackets removed. Brokers word them
// differently and few document them, so each column is an exact name first, then a looser pattern
const TICKER = ["symbol", "tradingsymbol", "stocksymbol", "nsesymbol", "bsesymbol", "ticker", "instrument"]
const NAME = ["scrip", "scripname", "stock", "stockname", "securityname", "companyname", "name", "security"]
const QUANTITY = ["qty", "quantity", "quantityavailable", "availableqty", "netqty", "holdingqty", "totalqty", "shares", "currentqty", "freeqty", "currentbalance", "currentbal", "freebalance", "freebal"]
const AVG_COST = ["avgcost", "averagecost", "avgprice", "averageprice", "buyavg", "avgbuyprice", "averagebuyprice", "buyprice", "costprice", "avgrate"]
const TICKER_LIKE = /^[A-Z0-9&.^-]{1,20}$/
const ISIN = /^IN[A-Z0-9]{9}\d$/

/** Where each field sits in a header row, or null when it isn't a holdings header. */
function holdingsColumns(header: string[]) {
    const exact = (names: string[]) => names.map(n => header.indexOf(n)).find(i => i >= 0) ?? -1
    const like = (ok: (h: string) => boolean) => header.findIndex(h => h !== "" && ok(h))
    const either = (i: number, j: number) => (i >= 0 ? i : j)
    const ticker = either(exact(TICKER), like(h => h.includes("symbol")))
    const isin = like(h => h.includes("isin"))
    const name = exact(NAME)
    // Zerodha Console splits shares into available, pledged, discrepant…; the free count is what's sellable
    const qty = either(exact(QUANTITY), like(h => /qty|quantity/.test(h) && !/pledge|discrep|block|longterm|t1|collateral|buy|sell|sold/.test(h)))
    const cost = either(exact(AVG_COST), like(h => /avg|average/.test(h) && /cost|price|rate/.test(h) && !/ltp|close|market|current|cmp|sell/.test(h)))
    // No average column (ICICI shows "Value At Cost"): the total spent, divided by the shares
    const spent = like(h => /buyvalue|valueatcost|invested|totalcost|costvalue|investment|amountinvested/.test(h) && !/current|market/.test(h))
    const symbols = [ticker, isin, name].filter(i => i >= 0)
    return symbols.length && qty >= 0 ? { ticker, isin, name, qty, cost, spent } : null
}

export const norm = (s: string) => s.toLowerCase().replace(/[\s._()₹-]/g, "")

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

export const parseNumber = (s: string | undefined) => {
    const n = Number((s ?? "").replace(/[₹$,\s]/g, ""))
    return Number.isFinite(n) ? n : NaN
}

/** Exchange prefixes (NSE:ITC) and series suffixes (ITC-EQ, IRFC-BE) aren't part of the ticker. */
export const cleanSymbol = (s: string) => s.trim().toUpperCase().replace(/^(NSE|BSE):/, "").replace(/-(EQ|BE|BZ|SM|ST)$/, "")

/** A file's contents as CSV text. For .xlsx (Zerodha's default download) that's the first sheet. */
export async function fileAsCsv(file: File): Promise<string> {
    let rows: unknown[][]
    if (/\.xlsx$/i.test(file.name)) {
        const { readSheet } = await import("read-excel-file/browser")  // loaded only when someone picks a spreadsheet
        rows = await readSheet(file)
    } else if (/\.xls$/i.test(file.name)) {
        // Many brokers' ".xls" is really an HTML table or tab-separated text; a true binary .xls isn't readable here
        const text = await file.text()
        if (/<table/i.test(text)) {
            const doc = new DOMParser().parseFromString(text, "text/html")
            rows = [...doc.querySelectorAll("tr")].map(tr => [...tr.querySelectorAll("th, td")].map(td => td.textContent?.trim() ?? ""))
        } else if (text.includes("\t") && !text.includes("\0")) {
            rows = text.split(/\r?\n/).map(l => l.split("\t"))
        } else {
            throw new Error("This is an old binary .xls file. Open it in Excel or Google Sheets and save it as .xlsx or CSV.")
        }
    } else {
        return file.text()
    }
    const cell = (v: unknown) =>
        v == null ? "" : `"${(v instanceof Date ? v.toISOString().slice(0, 10) : String(v)).replace(/[\r\n]+/g, " ").replace(/"/g, '""')}"`
    return rows.map(r => r.map(cell).join(",")).join("\n")
}

export function parseHoldingsCsv(text: string): HoldingsImport {
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter(l => l.trim())
    // Some exports open with a few summary lines; the header is the first row naming a symbol and a quantity
    const headerAt = lines.findIndex(l => holdingsColumns(splitCsvLine(l).map(norm)) !== null)
    if (headerAt < 0) {
        throw new Error("Couldn't find a header row with a symbol column and a quantity column.")
    }
    const at = holdingsColumns(splitCsvLine(lines[headerAt]).map(norm))!

    const merged = new Map<string, { shares: number; spent: number; costed: number }>()
    const skipped: string[] = []
    for (const line of lines.slice(headerAt + 1)) {
        const cells = splitCsvLine(line)
        const cellAt = (i: number) => (i >= 0 ? cells[i] ?? "" : "")
        const label = [at.ticker, at.isin, at.name].map(cellAt).find(c => c.trim()) ?? ""
        if (!label || /^total/i.test(label.trim())) continue  // blank or a totals row
        // A ticker if the file has one, else the ISIN (the server maps it), else a name that happens to be a ticker
        const ticker = cleanSymbol(cellAt(at.ticker)), isin = cellAt(at.isin).trim().toUpperCase(), name = cleanSymbol(cellAt(at.name))
        const symbol = TICKER_LIKE.test(ticker) ? ticker : ISIN.test(isin) ? isin : TICKER_LIKE.test(name) ? name : ""
        const shares = parseNumber(cells[at.qty])
        if (!symbol) { skipped.push(`${label.trim()}: not a ticker symbol`); continue }
        if (!(shares > 0)) { skipped.push(`${symbol}: no quantity`); continue }
        const cost = at.cost >= 0 ? parseNumber(cells[at.cost]) : at.spent >= 0 ? parseNumber(cells[at.spent]) / shares : 0
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
