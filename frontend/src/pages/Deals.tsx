import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cleanTickerDisplay } from "@/lib/currency"
import { cn } from "@/lib/utils"

interface Deal {
    ticker: string; company: string | null; deal_date: string; kind: "bulk" | "block"; client: string
    side: "BUY" | "SELL"; quantity: number; price: number; value: number
}

const RANGES = [[1, "Today"], [7, "7 days"], [30, "30 days"], [90, "90 days"]] as const
const KINDS = [[null, "All"], ["bulk", "Bulk"], ["block", "Block"]] as const
const crore = (v: number) => `₹${(v / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 2 })} Cr`
const day = (s: string) => new Date(`${s}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" })

/** NSE bulk and block deals: who bought or sold large stakes, kept day by day. */
export default function Deals() {
    const [days, setDays] = useState<number>(7)
    const [kind, setKind] = useState<"bulk" | "block" | null>(null)
    const [side, setSide] = useState<"BUY" | "SELL" | null>(null)
    const [query, setQuery] = useState("")
    const [mineOnly, setMineOnly] = useState(false)
    const { data: watchlist = [] } = useWatchlist()
    const { data, isLoading, isError } = useQuery({
        queryKey: ["deals", days],
        queryFn: async () => (await apiClient.get<Deal[]>("/market/deals", { params: { days } })).data,
        refetchInterval: 30 * 60_000,
    })
    const watched = useMemo(() => new Set(watchlist.map(w => w.ticker)), [watchlist])
    const q = query.trim().toLowerCase()
    const rows = (data ?? []).filter(d =>
        (!kind || d.kind === kind) && (!side || d.side === side)
        && (!mineOnly || watched.has(d.ticker))
        && (!q || d.ticker.toLowerCase().includes(q) || (d.company ?? "").toLowerCase().includes(q) || d.client.toLowerCase().includes(q)))
    const totals = rows.reduce((t, d) => ({ ...t, [d.side]: t[d.side] + d.value }), { BUY: 0, SELL: 0 })

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-4 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Bulk &amp; block deals</h1>
                <p className="text-sm text-muted-foreground">
                    Large trades reported to NSE: bulk deals (at least 0.5% of a company) and block deals (₹10 Cr+ in one trade). Search by investor name to follow a fund. History builds up from 12 Nov 2026.
                </p>
            </header>
            <div className="flex flex-wrap items-center gap-3">
                <div className="flex gap-1.5" role="group" aria-label="Period">
                    {RANGES.map(([d, label]) => (
                        <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}
                            className={cn("px-3 py-1.5 text-sm rounded-sm border", days === d ? "bg-primary border-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted")}>
                            {label}
                        </button>
                    ))}
                </div>
                <div className="flex gap-1.5" role="group" aria-label="Deal type">
                    {KINDS.map(([k, label]) => (
                        <button key={label} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}
                            className={cn("px-2 py-1 text-xs rounded-sm border", kind === k ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:bg-muted")}>
                            {label}
                        </button>
                    ))}
                </div>
                <div className="flex gap-1.5" role="group" aria-label="Side">
                    {([null, "BUY", "SELL"] as const).map(s => (
                        <button key={s ?? "both"} type="button" aria-pressed={side === s} onClick={() => setSide(s)}
                            className={cn("px-2 py-1 text-xs rounded-sm border", side === s ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:bg-muted")}>
                            {s === null ? "Buys & sells" : s === "BUY" ? "Buys" : "Sells"}
                        </button>
                    ))}
                </div>
                <input aria-label="Search deals" value={query} onChange={e => setQuery(e.target.value)} placeholder="Stock or investor…"
                    className="h-9 w-56 px-3 bg-background border border-border rounded-sm text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} /> Watchlist only
                </label>
            </div>
            {isLoading && <p className="text-sm text-muted-foreground">Loading deals…</p>}
            {isError && <p role="alert" className="text-sm text-muted-foreground">Couldn't load deals.</p>}
            {data && (
                <>
                    <p className="text-xs text-muted-foreground">
                        {rows.length} deals · bought <span className="text-green-500">{crore(totals.BUY)}</span> · sold <span className="text-red-500">{crore(totals.SELL)}</span>
                    </p>
                    <div className="bg-q-surface border border-q-border rounded-lg overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="text-xs text-muted-foreground text-left">
                                <tr className="border-b border-border">
                                    <th className="p-3 font-medium">Date</th><th className="p-3 font-medium">Stock</th><th className="p-3 font-medium">Investor</th>
                                    <th className="p-3 font-medium">Side</th><th className="p-3 font-medium text-right">Quantity</th>
                                    <th className="p-3 font-medium text-right">Price</th><th className="p-3 font-medium text-right">Value</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/50">
                                {rows.length === 0 && <tr><td colSpan={7} className="p-4 text-muted-foreground">No deals match.</td></tr>}
                                {rows.slice(0, 500).map((d, i) => (
                                    <tr key={`${d.deal_date}${d.ticker}${d.client}${d.side}${i}`} className={cn(watched.has(d.ticker) && "bg-primary/5")}>
                                        <td className="p-3 whitespace-nowrap text-muted-foreground">{day(d.deal_date)}</td>
                                        <td className="p-3">
                                            <Link to={`/research/${d.ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(d.ticker)}</Link>
                                            <span className="ml-2 text-[11px] uppercase text-muted-foreground">{d.kind}</span>
                                            <div className="text-xs text-muted-foreground">{d.company}</div>
                                        </td>
                                        <td className="p-3 text-foreground">{d.client}</td>
                                        <td className={cn("p-3 font-semibold", d.side === "BUY" ? "text-green-500" : "text-red-500")}>{d.side === "BUY" ? "Buy" : "Sell"}</td>
                                        <td className="p-3 text-right font-mono">{d.quantity.toLocaleString("en-IN")}</td>
                                        <td className="p-3 text-right font-mono">₹{d.price.toLocaleString("en-IN")}</td>
                                        <td className="p-3 text-right font-mono text-foreground whitespace-nowrap">{crore(d.value)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {rows.length > 500 && <p className="text-xs text-muted-foreground">Showing the first 500 of {rows.length}. Narrow by search or type.</p>}
                </>
            )}
        </div>
    )
}
