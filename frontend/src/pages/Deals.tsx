import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cleanTickerDisplay } from "@/lib/currency"
import { chipClass } from "@/lib/utils"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"

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
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Bulk & block deals"
                description="Large trades reported to NSE: bulk deals (at least 0.5% of a company) and block deals (₹10 Cr or more in one trade). Search by investor name to follow a fund. History starts 12 Nov 2026." />
            <div className="flex flex-wrap items-center gap-3">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Period">
                    {RANGES.map(([d, label]) => (
                        <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}
                            className={chipClass(days === d)}>
                            {label}
                        </button>
                    ))}
                </div>
                <div className="flex gap-1.5" role="group" aria-label="Deal type">
                    {KINDS.map(([k, label]) => (
                        <button key={label} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}
                            className={chipClass(kind === k)}>
                            {label}
                        </button>
                    ))}
                </div>
                <div className="flex gap-1.5" role="group" aria-label="Side">
                    {([null, "BUY", "SELL"] as const).map(s => (
                        <button key={s ?? "both"} type="button" aria-pressed={side === s} onClick={() => setSide(s)}
                            className={chipClass(side === s)}>
                            {s === null ? "Buys & sells" : s === "BUY" ? "Buys" : "Sells"}
                        </button>
                    ))}
                </div>
                <input aria-label="Search deals" value={query} onChange={e => setQuery(e.target.value)} placeholder="Stock or investor…"
                    className="h-9 w-56 px-3 bg-background border border-border rounded-md text-sm text-foreground outline-none focus:border-primary" />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} className="accent-primary" /> Watchlist only
                </label>
            </div>
            <Panel id="deal-list" title={data ? `${rows.length} deal${rows.length === 1 ? "" : "s"}` : "Deals"}
                description={data ? <>Bought <span className="font-mono tabular-nums text-q-risk-low">{crore(totals.BUY)}</span>, sold <span className="font-mono tabular-nums text-q-risk-high">{crore(totals.SELL)}</span>{rows.length > 500 ? ". Showing the first 500; narrow by search or type." : ". Your watchlist stocks are highlighted."}</> : undefined}>
            {isLoading && <PanelSkeleton rows={6} />}
            {isError && <PanelMessage alert>Couldn't load deals.</PanelMessage>}
            {data && (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="text-xs text-muted-foreground text-left">
                                <tr>
                                    <th scope="col" className="px-4 py-2 font-medium">Date</th><th scope="col" className="px-2 py-2 font-medium">Stock</th><th scope="col" className="px-2 py-2 font-medium">Investor</th>
                                    <th scope="col" className="px-2 py-2 font-medium">Side</th><th scope="col" className="px-2 py-2 font-medium text-right">Quantity</th>
                                    <th scope="col" className="px-2 py-2 font-medium text-right">Price</th><th scope="col" className="px-4 py-2 font-medium text-right">Value</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {rows.length === 0 && <tr><td colSpan={7} className="px-4 py-4 text-muted-foreground">No deals match.</td></tr>}
                                {rows.slice(0, 500).map((d, i) => (
                                    <tr key={`${d.deal_date}${d.ticker}${d.client}${d.side}${i}`} className={watched.has(d.ticker) ? "bg-primary/5" : undefined}>
                                        <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(d.deal_date)}</td>
                                        <td className="px-2 py-2">
                                            <Link to={`/research/${d.ticker}`} className="font-medium text-foreground hover:text-primary">{cleanTickerDisplay(d.ticker)}</Link>
                                            <span className="ml-2 text-xs text-muted-foreground">{d.kind === "bulk" ? "Bulk" : "Block"}</span>
                                            <div className="text-xs text-muted-foreground">{d.company}</div>
                                        </td>
                                        <td className="px-2 py-2 text-foreground">{d.client}</td>
                                        <td className={d.side === "BUY" ? "px-2 py-2 font-medium text-q-risk-low" : "px-2 py-2 font-medium text-q-risk-high"}>{d.side === "BUY" ? "Buy" : "Sell"}</td>
                                        <td className="px-2 py-2 text-right font-mono tabular-nums">{d.quantity.toLocaleString("en-IN")}</td>
                                        <td className="px-2 py-2 text-right font-mono tabular-nums">₹{d.price.toLocaleString("en-IN")}</td>
                                        <td className="px-4 py-2 text-right font-mono tabular-nums text-foreground whitespace-nowrap">{crore(d.value)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
            )}
            </Panel>
        </div>
    )
}
