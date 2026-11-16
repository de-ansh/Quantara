/** Read a broker's tradebook export (CSV): one row per executed buy or sell. */
import { cleanSymbol, norm, parseNumber, splitCsvLine } from "@/lib/holdingsCsv"

export interface TradeRow {
    symbol: string
    date: string // YYYY-MM-DD
    side: "buy" | "sell"
    quantity: number
    price: number
}

// Zerodha Console: symbol, trade_date, trade_type, quantity, price; the rest are common variants
const SYMBOL = ["symbol", "tradingsymbol", "instrument", "scrip", "scripname", "stock", "stockname", "nsesymbol"]
const DATE = ["tradedate", "date", "tradetime", "orderexecutiontime", "executiontime", "transactiondate"]
const SIDE = ["tradetype", "type", "buysell", "side", "transactiontype", "action"]
const QUANTITY = ["quantity", "qty", "tradedquantity", "tradedqty", "tradeqty"]
const PRICE = ["price", "tradeprice", "tradedprice", "rate", "avgprice", "averageprice"]
const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

/** ISO (2024-03-15, with or without a time), or Indian day-first (15-03-2024, 15/03/2024, 15-Mar-2024). */
export function parseTradeDate(raw: string): string | null {
    const s = raw.trim()
    let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s)
    if (m) return `${m[1]}-${m[2]}-${m[3]}`
    m = /^(\d{1,2})[-/ ](\d{1,2}|[A-Za-z]{3})[a-z]*[-/ ](\d{4})/.exec(s)
    if (!m) return null
    const month = /\d/.test(m[2]) ? Number(m[2]) : MONTHS.indexOf(m[2].toLowerCase()) + 1
    const day = Number(m[1])
    if (!(month >= 1 && month <= 12 && day >= 1 && day <= 31)) return null
    return `${m[3]}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
}

const side = (raw: string): "buy" | "sell" | null => {
    const s = raw.trim().toLowerCase()
    if (["buy", "b", "bought", "purchase"].includes(s)) return "buy"
    if (["sell", "s", "sold", "sale"].includes(s)) return "sell"
    return null
}

/** Trades from one file, plus a reason for each row that couldn't be read. */
export function parseTradebookCsv(text: string): { trades: TradeRow[]; skipped: string[] } {
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter(l => l.trim())
    const headerAt = lines.findIndex(l => {
        const cols = splitCsvLine(l).map(norm)
        return [SYMBOL, DATE, SIDE, QUANTITY, PRICE].every(names => cols.some(c => names.includes(c)))
    })
    if (headerAt < 0) {
        throw new Error("Couldn't find a header row with symbol, date, buy/sell type, quantity and price columns.")
    }
    const header = splitCsvLine(lines[headerAt]).map(norm)
    const col = (names: string[]) => names.map(n => header.indexOf(n)).find(i => i >= 0) ?? -1
    const [sym, day, kind, qty, px] = [col(SYMBOL), col(DATE), col(SIDE), col(QUANTITY), col(PRICE)]

    const trades: TradeRow[] = []
    const skipped: string[] = []
    for (const [i, line] of lines.slice(headerAt + 1).entries()) {
        const c = splitCsvLine(line)
        const symbol = cleanSymbol(c[sym] ?? "")
        const date = parseTradeDate(c[day] ?? "")
        const s = side(c[kind] ?? "")
        const quantity = parseNumber(c[qty])
        const price = parseNumber(c[px])
        if (!symbol) continue
        const where = `row ${headerAt + i + 2} (${symbol})`
        if (!/^[A-Z0-9&.^-]{1,20}$/.test(symbol)) skipped.push(`${where}: not a ticker symbol`)
        else if (!date) skipped.push(`${where}: unreadable date`)
        else if (!s) skipped.push(`${where}: not a buy or sell`)
        else if (!(quantity > 0) || !(price >= 0)) skipped.push(`${where}: no quantity or price`)
        else trades.push({ symbol, date, side: s, quantity, price })
    }
    return { trades, skipped }
}
