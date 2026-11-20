/** Read a broker's tradebook export (CSV): one row per executed buy or sell. */
import { cleanSymbol, norm, parseNumber, splitCsvLine } from "@/lib/holdingsCsv"

export interface TradeRow {
    symbol: string
    date: string // YYYY-MM-DD
    side: "buy" | "sell"
    quantity: number
    price: number
}

// Zerodha Console: symbol, trade_date, trade_type, quantity, price; the rest are common variants.
// ISIN comes after ticker columns and before names: the server maps it to a ticker (Groww has no symbol column)
const SYMBOL = ["symbol", "tradingsymbol", "nsesymbol", "isin", "instrument", "scrip", "scripname", "stock", "stockname"]
const DATE = ["tradedate", "date", "tradetime", "orderexecutiontime", "executiontime", "transactiondate"]
const SIDE = ["tradetype", "type", "buysell", "side", "transactiontype", "action"]
const QUANTITY = ["quantity", "qty", "tradedquantity", "tradedqty", "tradeqty"]
const PRICE = ["price", "tradeprice", "tradedprice", "rate", "avgprice", "averageprice"]
// A P&L report (Groww) lists lots instead: each row is a buy, plus its sell when the lot was sold
const BUY_DATE = ["buydate"], BUY_PRICE = ["buyprice"], SELL_DATE = ["selldate"], SELL_PRICE = ["sellprice"]
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
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/)
    const trades: TradeRow[] = []
    const skipped: string[] = []
    // A file can hold several tables (a P&L report has realised and unrealised lots), each under its own header
    let at: Record<string, number> | null = null
    let lots = false
    for (const [i, line] of lines.entries()) {
        if (!line.trim()) continue
        const c = splitCsvLine(line)
        const names = c.map(norm)
        const find = (wanted: string[]) => wanted.map(n => names.indexOf(n)).find(j => j >= 0) ?? -1
        const has = (...groups: string[][]) => groups.every(g => find(g) >= 0)
        if (has(SYMBOL, DATE, SIDE, QUANTITY, PRICE) || has(SYMBOL, QUANTITY, BUY_DATE, BUY_PRICE)) {
            lots = !has(SIDE)
            at = { sym: find(SYMBOL), day: find(DATE), kind: find(SIDE), qty: find(QUANTITY), px: find(PRICE),
                buyDay: find(BUY_DATE), buyPx: find(BUY_PRICE), sellDay: find(SELL_DATE), sellPx: find(SELL_PRICE) }
            continue
        }
        if (!at) continue
        const symbol = cleanSymbol(c[at.sym] ?? "")
        if (!symbol) continue
        const where = `row ${i + 1} (${symbol})`
        const quantity = parseNumber(c[at.qty])
        if (!/^[A-Z0-9&.^-]{1,20}$/.test(symbol)) { skipped.push(`${where}: not a ticker symbol`); continue }
        if (!(quantity > 0)) { skipped.push(`${where}: no quantity`); continue }
        const legs: [string | undefined, "buy" | "sell" | null, string | undefined][] = lots
            ? [[c[at.buyDay], "buy", c[at.buyPx]]]
            : [[c[at.day], side(c[at.kind] ?? ""), c[at.px]]]
        if (lots && at.sellDay >= 0 && c[at.sellDay]) legs.push([c[at.sellDay], "sell", c[at.sellPx]])
        for (const [rawDate, s, rawPrice] of legs) {
            const date = parseTradeDate(rawDate ?? "")
            const price = parseNumber(rawPrice)
            if (!date) skipped.push(`${where}: unreadable date`)
            else if (!s) skipped.push(`${where}: not a buy or sell`)
            else if (!(price >= 0) || rawPrice === undefined || rawPrice === "") skipped.push(`${where}: no price`)
            else trades.push({ symbol, date, side: s, quantity, price })
        }
    }
    if (!trades.length && !skipped.length && !at) {
        throw new Error("Couldn't find a header row with symbol, date, buy/sell type, quantity and price columns, or a P&L report's buy date and buy price columns.")
    }
    return { trades, skipped }
}
