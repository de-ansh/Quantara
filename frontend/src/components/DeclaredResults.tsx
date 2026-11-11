import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { cleanTickerDisplay } from "@/lib/currency"
import DayChange from "@/components/DayChange"

interface Result {
    ticker: string; name: string | null; sector: string | null; market_cap: number | null
    quarter_end: string; filed_at: string; consolidated: boolean
    revenue: number | null; profit: number | null; eps: number | null
    revenue_yoy_pct: number | null; profit_yoy_pct: number | null; revenue_qoq_pct: number | null; profit_qoq_pct: number | null
    pdf_url: string | null
}

const crore = (v: number | null) => (v === null ? "—" : `₹${(v / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`)
const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
const head = "p-3 text-left font-normal text-xs text-muted-foreground"
// Tiny bases make huge percentages meaningless for a leaderboard
const MIN_LEADER_PROFIT = 10 * 1e7

function Leaders({ title, rows }: { title: string; rows: Result[] }) {
    return (
        <div className="bg-q-surface border border-q-border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-foreground mb-2">{title}</h3>
            {rows.length === 0 && <p className="text-xs text-muted-foreground">None yet.</p>}
            <ul className="space-y-1">
                {rows.map(r => (
                    <li key={r.ticker} className="flex items-center justify-between gap-2 text-sm">
                        <span className="min-w-0 truncate"><Link to={`/research/${r.ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(r.ticker)}</Link> <span className="text-xs text-muted-foreground">{crore(r.profit)}</span></span>
                        <DayChange pct={r.profit_yoy_pct} className="text-xs shrink-0" />
                    </li>
                ))}
            </ul>
        </div>
    )
}

/** Results declared this season: leaderboards, sectors and every company's growth. */
export default function DeclaredResults({ only }: { only: Set<string> | null }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["market", "earnings"],
        queryFn: async () => (await apiClient.get<Result[]>("/market/earnings")).data,
        staleTime: 10 * 60 * 1000,
    })
    if (isLoading) return <p className="p-4 text-sm text-muted-foreground">Loading declared results…</p>
    if (isError || !data) return <p role="alert" className="p-4 text-sm text-muted-foreground">Could not load declared results.</p>

    const rows = only ? data.filter(r => only.has(r.ticker)) : data
    const ranked = rows.filter(r => r.profit_yoy_pct !== null && (r.profit ?? 0) >= MIN_LEADER_PROFIT)
        .sort((a, b) => (b.profit_yoy_pct ?? 0) - (a.profit_yoy_pct ?? 0))
    const sectors = new Map<string, { n: number; up: number; growth: number[] }>()
    for (const r of rows) {
        if (!r.sector) continue
        const s = sectors.get(r.sector) ?? { n: 0, up: 0, growth: [] }
        s.n++
        if (r.profit_yoy_pct !== null) { s.growth.push(r.profit_yoy_pct); if (r.profit_yoy_pct > 0) s.up++ }
        sectors.set(r.sector, s)
    }
    const median = (v: number[]) => { const s = [...v].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null }
    const sectorRows = [...sectors.entries()].map(([name, s]) => ({ name, ...s, median: median(s.growth) }))
        .sort((a, b) => (b.median ?? -Infinity) - (a.median ?? -Infinity))

    if (rows.length === 0) {
        return <p className="p-4 text-sm text-muted-foreground">No declared results yet. Results are collected for about 2,600 NSE stocks over a day, so this fills in as they're checked.</p>
    }
    return (
        <div className="space-y-4 p-4">
            <p className="text-xs text-muted-foreground">{rows.length} companies declared in the last 45 days. Growth compares the quarter with the same quarter last year (YoY) and the quarter before (QoQ). Leaderboards skip companies with profit under ₹10 Cr.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Leaders title="Biggest profit growth (YoY)" rows={ranked.slice(0, 8)} />
                <Leaders title="Biggest profit declines (YoY)" rows={ranked.slice(-8).reverse().filter(r => (r.profit_yoy_pct ?? 0) < 0)} />
            </div>
            {sectorRows.length > 0 && (
                <div className="bg-q-surface border border-q-border rounded-lg overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead><tr><th scope="col" className={head}>Sector</th><th scope="col" className={head}>Declared</th><th scope="col" className={head}>Profit up YoY</th><th scope="col" className={head}>Median profit growth</th></tr></thead>
                        <tbody>{sectorRows.map(s => (
                            <tr key={s.name} className="border-t border-border/50">
                                <th scope="row" className="p-3 text-left font-normal text-foreground">{s.name}</th>
                                <td className="p-3 text-muted-foreground">{s.n}</td>
                                <td className="p-3 text-muted-foreground">{s.growth.length ? `${s.up} of ${s.growth.length}` : "—"}</td>
                                <td className="p-3"><DayChange pct={s.median} className="text-xs" /></td>
                            </tr>
                        ))}</tbody>
                    </table>
                </div>
            )}
            <div className="bg-q-surface border border-q-border rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead><tr>
                        <th scope="col" className={head}>Filed</th><th scope="col" className={head}>Stock</th><th scope="col" className={head}>Quarter</th>
                        <th scope="col" className={head}>Revenue</th><th scope="col" className={head}>YoY</th><th scope="col" className={head}>Profit</th>
                        <th scope="col" className={head}>YoY</th><th scope="col" className={head}>QoQ</th><th scope="col" className={head}><span className="sr-only">Filing</span></th>
                    </tr></thead>
                    <tbody>{rows.slice(0, 400).map(r => (
                        <tr key={r.ticker} className="border-t border-border/50">
                            <td className="p-3 whitespace-nowrap text-muted-foreground">{day(r.filed_at)}</td>
                            <td className="p-3"><Link to={`/research/${r.ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(r.ticker)}</Link><div className="text-xs text-muted-foreground truncate max-w-[180px]">{r.name}</div></td>
                            <td className="p-3 whitespace-nowrap text-muted-foreground">{day(r.quarter_end)}{r.consolidated ? "" : " · standalone"}</td>
                            <td className="p-3 whitespace-nowrap font-mono text-foreground">{crore(r.revenue)}</td>
                            <td className="p-3"><DayChange pct={r.revenue_yoy_pct} className="text-xs" /></td>
                            <td className="p-3 whitespace-nowrap font-mono text-foreground">{crore(r.profit)}</td>
                            <td className="p-3"><DayChange pct={r.profit_yoy_pct} className="text-xs" /></td>
                            <td className="p-3"><DayChange pct={r.profit_qoq_pct} className="text-xs" /></td>
                            <td className="p-3">{r.pdf_url && <a href={r.pdf_url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline">PDF</a>}</td>
                        </tr>
                    ))}</tbody>
                </table>
            </div>
        </div>
    )
}
