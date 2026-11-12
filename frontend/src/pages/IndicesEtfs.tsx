import { Fragment, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import DayChange from "@/components/DayChange"
import { cleanTickerDisplay } from "@/lib/currency"
import { cn } from "@/lib/utils"

interface IndexSummary {
    name: string; category: string; last: number | null; change_pct: number | null; pe: number | null; pb: number | null
    dividend_yield: number | null; year_high: number | null; year_low: number | null; return_30d: number | null
    return_1y: number | null; advances: number | null; declines: number | null
}
interface IndexMember {
    ticker: string; name: string | null; sector: string | null; price: number | null; change_pct: number | null
    pe: number | null; market_cap: number | null; return_1y_pct: number | null
}
interface Etf {
    symbol: string; underlying: string | null; category: string; price: number | null; change_pct: number | null
    nav: number | null; premium_pct: number | null; traded_value: number | null; year_high: number | null
    year_low: number | null; return_30d: number | null; return_1y: number | null
}

const num = (n: number | null, digits = 2) => (n === null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: digits }))
const pct = (n: number | null) => (n === null ? "—" : <span className={n > 0 ? "text-green-500" : n < 0 ? "text-red-500" : ""}>{n > 0 ? "+" : ""}{n.toFixed(2)}%</span>)
const crore = (n: number | null) => (n === null ? "—" : `₹${(n / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`)
const chip = (active: boolean) => cn("px-2 py-1 text-xs rounded-sm border", active ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:bg-muted")
const Unavailable = ({ what }: { what: string }) => <p role="alert" className="text-sm text-muted-foreground">{what} unavailable from NSE right now.</p>

function Constituents({ name }: { name: string }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["index", name],
        queryFn: async () => (await apiClient.get<{ members: IndexMember[] | null }>(`/market/indices/${encodeURIComponent(name)}`)).data,
        staleTime: 5 * 60 * 1000,
    })
    if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading constituents…</p>
    if (isError) return <p role="alert" className="text-sm text-muted-foreground">Couldn't load constituents.</p>
    if (!data?.members) return <p className="text-sm text-muted-foreground">NSE doesn't publish a constituent list for this index.</p>
    const moves = data.members.map(m => m.change_pct).filter((c): c is number => c !== null)
    const up = moves.filter(c => c > 0).length
    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">{data.members.length} stocks, largest first · {up} up, {moves.length - up} down today among those with prices</p>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="text-xs text-muted-foreground text-left">
                        <tr><th className="py-1.5 pr-3 font-medium">Stock</th><th className="py-1.5 px-2 font-medium">Sector</th><th className="py-1.5 px-2 font-medium text-right">Price</th>
                            <th className="py-1.5 px-2 font-medium text-right">Today</th><th className="py-1.5 px-2 font-medium text-right">P/E</th><th className="py-1.5 pl-2 font-medium text-right">1Y</th></tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                        {data.members.map(m => (
                            <tr key={m.ticker}>
                                <td className="py-1.5 pr-3"><Link to={`/research/${m.ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(m.ticker)}</Link> <span className="text-xs text-muted-foreground">{m.name}</span></td>
                                <td className="py-1.5 px-2 text-xs text-muted-foreground">{m.sector ?? "—"}</td>
                                <td className="py-1.5 px-2 text-right font-mono">{m.price === null ? "—" : `₹${num(m.price)}`}</td>
                                <td className="py-1.5 px-2 text-right font-mono">{m.change_pct === null ? "—" : <DayChange pct={m.change_pct} />}</td>
                                <td className="py-1.5 px-2 text-right font-mono text-muted-foreground">{num(m.pe, 1)}</td>
                                <td className="py-1.5 pl-2 text-right font-mono">{pct(m.return_1y_pct)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function Indices() {
    const [category, setCategory] = useState<string | null>(null)
    const [open, setOpen] = useState<string | null>(null)
    const { data, isLoading, isError } = useQuery({
        queryKey: ["indices"],
        queryFn: async () => (await apiClient.get<IndexSummary[] | null>("/market/indices")).data,
        refetchInterval: 120_000,
    })
    const categories = useMemo(() => [...new Set((data ?? []).map(i => i.category))], [data])
    if (isLoading) return <p className="text-sm text-muted-foreground">Loading indices…</p>
    if (isError || !data) return <Unavailable what="Indices" />
    const rows = data.filter(i => !category || i.category === category)
    return (
        <div className="space-y-3">
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Index category">
                <button type="button" aria-pressed={category === null} onClick={() => setCategory(null)} className={chip(category === null)}>All</button>
                {categories.map(c => <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)} className={chip(category === c)}>{c}</button>)}
            </div>
            <div className="bg-q-surface border border-q-border rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="text-xs text-muted-foreground text-left">
                        <tr className="border-b border-border">
                            <th className="p-3 font-medium">Index</th><th className="p-3 font-medium text-right">Level</th><th className="p-3 font-medium text-right">Today</th>
                            <th className="p-3 font-medium text-right">1M</th><th className="p-3 font-medium text-right">1Y</th><th className="p-3 font-medium text-right">P/E</th>
                            <th className="p-3 font-medium text-right">P/B</th><th className="p-3 font-medium text-right">Div. yield</th><th className="p-3 font-medium text-right">Adv / Dec</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                        {rows.map(i => (
                            <Fragment key={i.name}>
                                <tr className="hover:bg-muted/30">
                                    <td className="p-3">
                                        <button type="button" aria-expanded={open === i.name} onClick={() => setOpen(open === i.name ? null : i.name)} className="font-semibold text-foreground hover:text-primary text-left">
                                            {i.name}
                                        </button>
                                    </td>
                                    <td className="p-3 text-right font-mono">{num(i.last)}</td>
                                    <td className="p-3 text-right font-mono">{pct(i.change_pct)}</td>
                                    <td className="p-3 text-right font-mono">{pct(i.return_30d)}</td>
                                    <td className="p-3 text-right font-mono">{pct(i.return_1y)}</td>
                                    <td className="p-3 text-right font-mono text-muted-foreground">{num(i.pe, 1)}</td>
                                    <td className="p-3 text-right font-mono text-muted-foreground">{num(i.pb, 1)}</td>
                                    <td className="p-3 text-right font-mono text-muted-foreground">{i.dividend_yield === null ? "—" : `${i.dividend_yield}%`}</td>
                                    <td className="p-3 text-right font-mono text-muted-foreground">{i.advances === null ? "—" : `${i.advances} / ${i.declines}`}</td>
                                </tr>
                                {open === i.name && (
                                    <tr><td colSpan={9} className="p-3 bg-muted/20"><Constituents name={i.name} /></td></tr>
                                )}
                            </Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

type EtfSort = "traded_value" | "return_1y" | "change_pct"

function Etfs() {
    const [category, setCategory] = useState<string | null>(null)
    const [query, setQuery] = useState("")
    const [sort, setSort] = useState<EtfSort>("traded_value")
    const { data, isLoading, isError } = useQuery({
        queryKey: ["etfs"],
        queryFn: async () => (await apiClient.get<Etf[] | null>("/market/etfs")).data,
        refetchInterval: 120_000,
    })
    const categories = useMemo(() => {
        const counts = new Map<string, number>()
        for (const e of data ?? []) counts.set(e.category, (counts.get(e.category) ?? 0) + 1)
        return [...counts.entries()].sort((a, b) => b[1] - a[1])
    }, [data])
    if (isLoading) return <p className="text-sm text-muted-foreground">Loading ETFs…</p>
    if (isError || !data) return <Unavailable what="ETFs" />
    const q = query.trim().toLowerCase()
    const rows = data
        .filter(e => (!category || e.category === category) && (!q || e.symbol.toLowerCase().includes(q) || (e.underlying ?? "").toLowerCase().includes(q)))
        .sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity))
    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
                <input aria-label="Search ETFs" value={query} onChange={e => setQuery(e.target.value)} placeholder="Symbol or underlying…"
                    className="h-9 w-56 px-3 bg-background border border-border rounded-sm text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">Sort
                    <select aria-label="Sort ETFs" value={sort} onChange={e => setSort(e.target.value as EtfSort)} className="h-9 px-2 bg-background border border-border rounded-sm text-sm text-foreground">
                        <option value="traded_value">Most traded</option><option value="return_1y">1-year return</option><option value="change_pct">Today</option>
                    </select>
                </label>
            </div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="ETF category">
                <button type="button" aria-pressed={category === null} onClick={() => setCategory(null)} className={chip(category === null)}>All <span className="opacity-60">{data.length}</span></button>
                {categories.map(([c, n]) => <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)} className={chip(category === c)}>{c} <span className="opacity-60">{n}</span></button>)}
            </div>
            <div className="bg-q-surface border border-q-border rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="text-xs text-muted-foreground text-left">
                        <tr className="border-b border-border">
                            <th className="p-3 font-medium">ETF</th><th className="p-3 font-medium text-right">Price</th><th className="p-3 font-medium text-right">Today</th>
                            <th className="p-3 font-medium text-right" title="Price vs the fund's net asset value; negative is a discount">vs NAV</th>
                            <th className="p-3 font-medium text-right">Traded</th><th className="p-3 font-medium text-right">1M</th><th className="p-3 font-medium text-right">1Y</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                        {rows.length === 0 && <tr><td colSpan={7} className="p-4 text-muted-foreground">No ETFs match.</td></tr>}
                        {rows.slice(0, 300).map(e => (
                            <tr key={e.symbol}>
                                <td className="p-3">
                                    <span className="font-mono font-bold text-foreground">{e.symbol}</span>
                                    <span className="ml-2 text-[11px] text-muted-foreground">{e.category}</span>
                                    <div className="text-xs text-muted-foreground max-w-[360px] truncate">{e.underlying}</div>
                                </td>
                                <td className="p-3 text-right font-mono">{e.price === null ? "—" : `₹${num(e.price)}`}</td>
                                <td className="p-3 text-right font-mono">{pct(e.change_pct)}</td>
                                <td className={cn("p-3 text-right font-mono", e.premium_pct !== null && Math.abs(e.premium_pct) >= 1 ? "text-amber-500" : "text-muted-foreground")}>
                                    {e.premium_pct === null ? "—" : `${e.premium_pct > 0 ? "+" : ""}${e.premium_pct.toFixed(2)}%`}
                                </td>
                                <td className="p-3 text-right font-mono text-muted-foreground">{crore(e.traded_value)}</td>
                                <td className="p-3 text-right font-mono">{pct(e.return_30d)}</td>
                                <td className="p-3 text-right font-mono">{pct(e.return_1y)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="text-xs text-muted-foreground">"vs NAV" is the price against the fund's last published net asset value; a gap of 1% or more is highlighted, since buying at a premium costs you that gap.</p>
        </div>
    )
}

/** NSE indices (valuation, returns, constituents) and every NSE ETF. */
export default function IndicesEtfs() {
    const [tab, setTab] = useState<"indices" | "etfs">("indices")
    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-4 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Indices &amp; ETFs</h1>
                <p className="text-sm text-muted-foreground">Every NSE index with its valuation and constituents, and every NSE-listed ETF. Updates every 2 minutes.</p>
            </header>
            <div className="flex gap-1 border-b border-border" role="tablist">
                {(["indices", "etfs"] as const).map(t => (
                    <button key={t} role="tab" aria-selected={tab === t} type="button" onClick={() => setTab(t)}
                        className={cn("px-4 py-2 text-sm font-semibold border-b-2", tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>
                        {t === "indices" ? "Indices" : "ETFs"}
                    </button>
                ))}
            </div>
            {tab === "indices" ? <Indices /> : <Etfs />}
        </div>
    )
}
